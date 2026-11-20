#!/usr/bin/env python3
"""
test-chinese-input.py — 验证 FlickOS 的中文字输入（Rime 引擎）能否真正上屏。

原理：直接调用 librime C API，把拼音按键送进 Rime 引擎，读取 commit（上屏文本）。
      这绕过了图形前端，专测"引擎+词库+配置"是否能把拼音正确转成汉字。

用法：
  python3 test-chinese-input.py            # 输入 nihao，期望出现汉字
  python3 test-chinese-input.py -i "zhongguo"
  python3 test-chinese-input.py --keep     # 保留临时部署目录（调试）
退出码：0=上屏了中文，1=没有，2=环境缺件。
"""
import argparse, ctypes, glob, os, shutil, subprocess, sys, tempfile
from ctypes import c_char_p, c_int, c_uint, c_void_p, c_bool, POINTER, Structure, byref

# ---------- librime C API 结构（对应 rime_api.h） ----------
class RimeTraits(Structure):
    _fields_ = [
        ("data_size", c_int),
        ("shared_data_dir", c_char_p),
        ("user_data_dir", c_char_p),
        ("distribution_name", c_char_p),
        ("distribution_code_name", c_char_p),
        ("distribution_version", c_char_p),
        ("app_name", c_char_p),
        ("modules", POINTER(c_char_p)),
        ("min_log_level", c_int),
        ("log_dir", c_char_p),
        ("prebuilt_data_dir", c_char_p),
        ("staging_dir", c_char_p),
    ]

class RimeCommit(Structure):
    _fields_ = [("data_size", c_int), ("text", c_char_p)]

# ---------- 默认配置：与 FlickOS ISO 的 default.custom.yaml 一致 ----------
DEFAULT_CUSTOM = """\
# Rime 默认补丁：简体中文输出 + 中文标点（与 FlickOS ISO 一致）
patch:
  "schema_list":
    - schema: luna_pinyin_simp
  "menu/page_size": 7
"""

def find_librime():
    pats = ["/lib/x86_64-linux-gnu/librime.so.1", "/usr/lib/*/librime.so.1",
            "/usr/lib/librime.so.1", "/lib/*/librime.so.1"]
    for p in pats:
        hits = glob.glob(p)
        if hits:
            return hits[0]
    return None

def find_shared_data():
    for d in ("/usr/share/rime-data", "/usr/lib/rime-data"):
        if os.path.isdir(d):
            return d
    return None

def has_chinese(s):
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", default="nihao", help="要输入的拼音（默认 nihao）")
    ap.add_argument("--keep", action="store_true", help="保留临时部署目录")
    args = ap.parse_args()

    libpath = find_librime()
    shared = find_shared_data()
    if not libpath or not shared:
        print("ENV-FAIL: 找不到 librime.so.1 或 /usr/share/rime-data；请先装 fcitx5-rime")
        return 2

    lib = ctypes.CDLL(libpath)
    lib.RimeSetup.argtypes = [POINTER(RimeTraits)]
    lib.RimeInitialize.argtypes = [POINTER(RimeTraits)]
    lib.RimeCreateSession.restype = c_void_p
    lib.RimeProcessKey.argtypes = [c_void_p, c_uint, c_uint]
    lib.RimeProcessKey.restype = c_bool
    lib.RimeGetCommit.argtypes = [c_void_p, POINTER(RimeCommit)]
    lib.RimeGetCommit.restype = c_bool
    lib.RimeDestroySession.argtypes = [c_void_p]
    lib.RimeFinalize.argtypes = []

    # 全新临时目录，模拟用户首次登录时 Rime 的自动部署
    userdir = tempfile.mkdtemp(prefix="rime-test-")
    rime_dir = os.path.join(userdir, "rime")
    os.makedirs(rime_dir, exist_ok=True)
    with open(os.path.join(rime_dir, "default.custom.yaml"), "w", encoding="utf-8") as f:
        f.write(DEFAULT_CUSTOM)

    # 首次登录时 fcitx5 会自动部署；这里用 librime 自带的 rime_deployer
    # 预编译 schema/词库，模拟同样的部署过程（全新目录也能工作）。
    staging = os.path.join(userdir, "staging")
    os.makedirs(staging, exist_ok=True)
    deployer = shutil.which("rime_deployer")
    if deployer:
        try:
            subprocess.run([deployer, "--build", rime_dir, shared, staging],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            build_dir = os.path.join(rime_dir, "build")
            if os.path.isdir(build_dir):
                shutil.rmtree(build_dir)
            shutil.move(staging, build_dir)
        except Exception as e:
            print(f"[warn] rime_deployer 部署失败: {e}")

    t = RimeTraits()
    t.data_size = ctypes.sizeof(RimeTraits)
    t.shared_data_dir = shared.encode()
    t.user_data_dir = rime_dir.encode()
    t.app_name = b"rime.chinese-input-test"
    t.min_log_level = 3  # ERROR only

    print(f"[env] librime: {libpath}")
    print(f"[env] shared data: {shared}")
    print(f"[env] user data:  {rime_dir}")
    lib.RimeSetup(byref(t))
    lib.RimeInitialize(byref(t))  # 首次会自动部署 schema
    sess = lib.RimeCreateSession()

    def commits():
        out = []
        while True:
            c = RimeCommit()
            c.data_size = ctypes.sizeof(RimeCommit)
            if lib.RimeGetCommit(sess, byref(c)) and c.text:
                out.append(c.text.decode("utf-8", "replace"))
            else:
                break
        return out

    text = ""
    for ch in args.input:
        lib.RimeProcessKey(sess, ord(ch), 0)
        text += "".join(commits())
    text += "".join(commits())
    lib.RimeProcessKey(sess, 0x20, 0)          # 空格：选第一个候选
    text += "".join(commits())

    print(f"[input]  {args.input}")
    print(f"[commit] {text!r}")
    ok = has_chinese(text)
    print("RESULT:", "PASS — 中文可正常上屏 ✅" if ok else "FAIL — 未上屏中文 ❌")

    lib.RimeDestroySession(sess)
    lib.RimeFinalize()
    if not args.keep:
        shutil.rmtree(userdir, ignore_errors=True)
    else:
        print(f"[keep] 部署目录保留在 {userdir}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
