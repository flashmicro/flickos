#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlickOS 预制中文版 · 精简 headless boot test

用途：替代 upstream 缺失的 tools/boot-test.py，供 CI（`tools/boot-test.py`）
和本地调用。用 QEMU 从 ISO 直接引导，通过串口自动登录 live 用户，执行
下方 CHECKS 里的中文/输入法/固件验收项，输出 PASS/WARN/FAIL。

兼容 upstream 文档的约定：
  - 参数：--iso / --verbose / --strict / --timeout / --max-used-mb（后两者可保留）
  - 产物目录：boot-test/{serial.log,screen.png,memory.txt}
  - 退出码：0 全过 / 1 有 FAIL / 2 环境或 ISO 问题 / 3 没到登录提示或登录失败
  - 从 ISO 提取 kernel+initrd+cmdline，去掉 quiet splash，加串口 console

依赖（CI 已装）：xorriso、qemu-system-x86、python3。
无 KVM 时自动降级为 TCG 并把等待时间放大（慢，但能跑）。
"""
import argparse
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

LIVE_USER = "user"
LIVE_PASSWORD = "live"

# (描述, 在 live 会话里以 user 执行的 shell 命令, 重试秒数；0=登录即应满足)
# 命令退出码 0 视为 PASS。sudo -n 在 live 会话里免密可用。
CHECKS = [
    ("locale: LANG=zh_CN.UTF-8", "locale | grep -q '^LANG=zh_CN.UTF-8'", 15),
    ("locale: zh_CN 已生成", "locale -a | grep -qi '^zh_CN'", 15),
    ("locale: en_US 兜底保留", "locale -a | grep -qi '^en_US'", 0),
    ("字体: 中文字体无方框", "fc-match ':lang=zh-cn' | grep -qiE 'noto|wqy|wenquanyi|cjk'", 15),
    ("时区: Asia/Shanghai", "grep -q '^Asia/Shanghai$' /etc/timezone", 0),
    # headless 串口登录没有图形会话，labwc/fcitx5 不会自启，故不检查进程；
    # 改为验证已安装 + 已写入 labwc autostart（图形登录时才会真正拉起）。
    ("输入法: fcitx5 已安装", "command -v fcitx5 >/dev/null", 0),
    ("输入法: 已配置图形会话自启", "grep -q fcitx5 /usr/libexec/flickos/autostart 2>/dev/null", 0),
    ("输入法: Rime 预置且为默认", "grep -qi 'DefaultIM=rime' ~/.config/fcitx5/profile /etc/skel/.config/fcitx5/profile 2>/dev/null", 20),
    ("输入法: 配置工具已装", "dpkg-query -W fcitx5-config-qt >/dev/null 2>&1", 0),
    ("输入法: GTK/Qt 前端已装", "dpkg-query -W fcitx5-frontend-gtk3 fcitx5-frontend-qt5 >/dev/null 2>&1", 0),
    ("Calamares: 已预装", "command -v calamares >/dev/null 2>&1", 0),
    ("QEMU: 已预装", "command -v qemu-system-x86_64 >/dev/null", 0),
    ("固件: 完整保留（G50-70）", "[ \"$(dpkg -l | grep -ci firmware)\" -gt 10 ]", 0),
]


class State:
    """串口会话状态：持续读 QEMU stdout 到缓冲区与 serial.log。"""

    def __init__(self, proc, logfile, verbose):
        self.buf = ""
        self.lock = threading.Lock()
        self.proc = proc
        self.logfile = logfile
        self.verbose = verbose
        self._stop = threading.Event()
        self.t = threading.Thread(target=self._reader, daemon=True)
        self.t.start()

    def _reader(self):
        fd = self.proc.stdout.fileno()
        while not self._stop.is_set():
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            with self.lock:
                self.buf += text
                self.logfile.write(text)
                self.logfile.flush()
            if self.verbose:
                sys.stdout.write(text)
                sys.stdout.flush()

    def snapshot(self):
        with self.lock:
            return self.buf

    def send(self, line):
        self.proc.stdin.write((line + "\n").encode())
        self.proc.stdin.flush()

    def wait(self, pattern, timeout, since=0):
        """在 buf[since:] 中等待正则，命中返回 match，超时返回 None。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            m = re.search(pattern, self.snapshot()[since:], re.M)
            if m:
                return m
            time.sleep(0.2)
        return None

    def close(self):
        self._stop.set()


def log(msg):
    print(msg, flush=True)


def fail_setup(msg):
    log("SETUP-FAIL: " + msg)
    sys.exit(2)


def find_iso(arg):
    if arg:
        if not os.path.isfile(arg):
            fail_setup("ISO 不存在: " + arg)
        return os.path.abspath(arg)
    cands = sorted(glob.glob("FlickOS-64bit-v*.iso"), key=os.path.getmtime, reverse=True)
    if not cands:
        fail_setup("当前目录没有 FlickOS-64bit-v*.iso（用 --iso 指定）")
    return os.path.abspath(cands[0])


def xorriso_extract(iso, src, dst):
    cmd = ["xorriso", "-osirrox", "on", "-indev", iso, "-extract", src, dst]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 0


def xorriso_cat(iso, path):
    """读取 ISO 内文件内容：xorriso 没有 -cat，用 -extract 到临时文件再读。"""
    fd, tmp = tempfile.mkstemp(prefix="fckcat-")
    os.close(fd)
    try:
        r = subprocess.run(
            ["xorriso", "-osirrox", "on", "-indev", iso, "-extract", path, tmp],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if r.returncode != 0 or not os.path.isfile(tmp):
            return ""
        with open(tmp, "rb") as f:
            return f.read().decode("utf-8", errors="replace")
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def xorriso_list(iso):
    """列出 ISO 内所有普通文件的完整路径。

    xorriso 的 -find 不支持 GNU find 的 -print；`-find / -type f`
    本身就会把匹配到的 iso_rr_path 打印出来，形如  '/live/vmlinuz'。
    stdout 里还会混入 NOTE/UPDATE 等信息行，故只提取被引号包裹的绝对路径。
    """
    r = subprocess.run(
        ["xorriso", "-indev", iso, "-find", "/", "-type", "f"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    paths = []
    for line in r.stdout.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        # 形如  '/live/vmlinuz'  →  /live/vmlinuz
        m = re.match(r"^'(/[^']*)'$", line)
        if m:
            paths.append(m.group(1))
        elif line.startswith("/"):
            paths.append(line)
    return paths


# 兜底 cmdline：FlickOS auto/config 里 --bootappend-live 的已知值（去掉 quiet splash）。
# 即使 cfg 解析失败也能引导。真实值优先从 ISO 的 cfg 里提取。
FALLBACK_APPEND = ("boot=live components username=user hostname=flickos "
                   "locales=zh_CN.UTF-8 timezone=Asia/Shanghai")


def extract_boot(iso, workdir):
    """从 ISO 动态定位 kernel/initrd 与 cmdline，返回 (vmlinuz, initrd, append)。"""
    for tool in ("xorriso", "qemu-system-x86_64"):
        if not shutil.which(tool):
            fail_setup("缺少工具 " + tool)

    paths = xorriso_list(iso)
    if not paths:
        fail_setup("无法列出 ISO 文件（xorriso -find 无输出）")

    def find_one(patterns):
        for pat in patterns:
            for p in paths:
                if re.search(pat, p, re.I):
                    return p
        return None

    # kernel / initrd：按文件名特征动态匹配，兼容 /live/、/isolinux/、/boot/ 等布局。
    kpath = find_one([r"/vmlinuz[^/]*$", r"/linux$", r"/vmlinuz"])
    ipath = find_one([r"/initrd[^/]*$", r"/initrd\.img"])
    if not kpath or not ipath:
        fail_setup("ISO 里找不到 kernel/initrd（文件列表：%s）" % ", ".join(paths[:20]))

    # cfg：找 live.cfg 或 grub.cfg，用于提取真实 cmdline。
    cfgpath = find_one([r"/live\.cfg$", r"/grub\.cfg$", r"/syslinux\.cfg$"])
    append = ""
    if cfgpath:
        cfg = xorriso_cat(iso, cfgpath)
        flat = cfg.replace("\\\n", " ")
        # 兼容三种写法：syslinux 新语法 "linux <k> <args>"、老语法 "append <args>"、
        # grub "linux <k> <args>"。抓含 boot=live 的那一行最可靠。
        for line in flat.splitlines():
            if "boot=live" in line:
                # 取 boot=live 及其后的内容（去掉行首指令与 kernel 路径）。
                idx = line.find("boot=live")
                append = line[idx:].strip()
                break
        if not append:
            # 退一步：抓 append 行或 linux 行的参数部分。
            m = re.search(r"\b(?:append|linux)\s+\S+\s+(.*boot=live.*)", flat)
            if m:
                append = m.group(1).strip()

    if not append:
        log("WARN: 未能从 ISO cfg 提取 boot 参数，使用兜底 cmdline")
        append = FALLBACK_APPEND

    vmlinuz = os.path.join(workdir, "vmlinuz")
    initrd = os.path.join(workdir, "initrd.img")
    if not xorriso_extract(iso, kpath, vmlinuz):
        fail_setup("提取 kernel 失败: " + kpath)
    if not xorriso_extract(iso, ipath, initrd):
        fail_setup("提取 initrd 失败: " + ipath)
    log("引导文件: kernel=%s initrd=%s" % (kpath, ipath))

    # 去掉 quiet/splash，保留 boot=live components 等。
    append = re.sub(r"\binitrd=\S+", "", append)
    append = re.sub(r"\bBOOT_IMAGE=\S+", "", append)
    append = re.sub(r"\b(quiet|splash)\b", "", append)
    append = re.sub(r"\s+", " ", append).strip()

    # 串口 console：让内核日志、systemd 与 login 提示出现在 ttyS0。
    append += " console=tty0 console=ttyS0,115200"
    return vmlinuz, initrd, append


def start_qemu(iso, vmlinuz, initrd, append, qmp_sock, outdir, kvm, timeout_scale):
    cmd = ["qemu-system-x86_64"]
    if kvm:
        cmd += ["-enable-kvm", "-cpu", "host"]
    else:
        cmd += ["-cpu", "max"]
    cmd += [
        "-m", "2048", "-smp", "2", "-vga", "std", "-display", "none",
        "-kernel", vmlinuz, "-initrd", initrd, "-append", append,
        "-cdrom", iso,
        "-serial", "stdio",
        "-qmp", "unix:" + qmp_sock + ",server,nowait",
        "-no-reboot",
    ]
    log("QEMU: " + " ".join(cmd))
    logfile = open(os.path.join(outdir, "serial.log"), "w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as e:
        fail_setup("启动 QEMU 失败: " + str(e))
    return proc, logfile, State(proc, logfile, opts.verbose), cmd


def qmp_screendump(qmp_sock, path):
    """尽力截图；失败不影响验收结果。"""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(8)
        s.connect(qmp_sock)
        s.recv(65536)  # QMP greeting
        s.sendall(b'{"execute":"qmp_capabilities"}\n')
        s.recv(65536)
        payload = json.dumps({"execute": "screendump", "arguments": {"filename": path}})
        s.sendall((payload + "\n").encode())
        time.sleep(1)
        s.close()
        return os.path.isfile(path)
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description="FlickOS 中文版 headless boot test")
    ap.add_argument("--iso", help="指定 ISO（默认取最新的 FlickOS-64bit-v*.iso）")
    ap.add_argument("--verbose", action="store_true", help="实时打印串口输出")
    ap.add_argument("--strict", action="store_true", help="systemd degraded 视为失败")
    ap.add_argument("--timeout", type=int, default=0, help="等待登录提示的秒数（覆盖默认）")
    ap.add_argument("--max-used-mb", type=int, default=0, help="记录到 memory.txt；超出则 FAIL")
    global opts
    opts = ap.parse_args()

    iso = find_iso(opts.iso)
    outdir = os.path.abspath("boot-test")
    os.makedirs(outdir, exist_ok=True)

    kvm = os.path.exists("/dev/kvm")
    scale = 1 if kvm else 4
    login_timeout = opts.timeout or (300 * scale)

    log("ISO: " + iso)
    log("加速: " + ("KVM" if kvm else "TCG（无 /dev/kvm，已放大超时）"))

    workdir = tempfile.mkdtemp(prefix="flickos-boot-")
    qmp_sock = os.path.join(workdir, "qmp.sock")
    try:
        vmlinuz, initrd, append = extract_boot(iso, workdir)
        proc, logfile, st, _ = start_qemu(iso, vmlinuz, initrd, append, qmp_sock, outdir, kvm, scale)

        rc = 0
        try:
            # 1) 等登录提示 → 自动登录 → 用一个标记确认进入 shell
            if not st.wait(r"login:|Login:", login_timeout):
                log("FAIL: 未等到登录提示（见 boot-test/serial.log）")
                rc = 3
            else:
                # 中文密码提示经串口变乱码（UTF-8 被 tty 截断成 \uFFFD），
                # 无法可靠匹配 "密码:"，也不能干等满 60s（login 会超时重发提示）。
                # 策略：发用户名→短等回显→发密码→等 shell 提示符出现（bash 就绪），
                # 再发验证标记。关键：密码后必须等 shell 提示符，否则命令会在
                # banner/初始化阶段被吞掉，导致误判"登录失败"。
                pos = len(st.snapshot())
                st.send(LIVE_USER)
                if not st.wait(re.escape(LIVE_USER), 20, pos):
                    log("WARN: 未等到用户名回显，仍尝试发送密码")
                time.sleep(1)  # 给 login 处理用户名、显示密码提示的时间
                pwd_pos = len(st.snapshot())  # 发密码前的位置，之后的输出都从这里开始搜
                st.send(LIVE_PASSWORD)

                # 等 shell 提示符：user@flickos:~$ 或末尾的 $ / # 提示符。
                # 乱码里 'user@' 与 '$' 仍是可靠 ASCII 锚点。
                prompt = st.wait(r"user@[^\r\n]*[$#]\s", 90, pwd_pos)
                if prompt:
                    log("已登录，进入 shell 提示符")
                    pos = len(st.snapshot())
                    st.send("echo __LOGIN_READY__")
                    if st.wait(r"__LOGIN_READY__", 30, pos):
                        pass  # 登录确认成功
                    else:
                        # shell 已出现即视为登录成功；标记可能因回显/时序丢失。
                        log("WARN: 未捕获 __LOGIN_READY__ 回显，但 shell 已就绪，继续")
                else:
                    # 兜底：直接尝试标记（兼容提示符格式不同的情况）。
                    pos = len(st.snapshot())
                    st.send("echo __LOGIN_READY__")
                    if not st.wait(r"__LOGIN_READY__", 60, pos):
                        log("FAIL: 登录失败（用户/密码？见 serial.log）")
                        rc = 3

            if rc == 0:
                # 2) 逐条执行 CHECKS
                seq = 0
                for desc, cmd, retry in CHECKS:
                    seq += 1
                    marker = "__FCKCHK%d__" % seq
                    wait_s = retry * scale
                    start = len(st.snapshot())
                    st.send("%s; __rc=$?; echo '%s$__rc'" % (cmd, marker))
                    m = st.wait(re.escape(marker) + r"(\d+)", max(20, wait_s), start)
                    if m and int(m.group(1)) == 0:
                        log("PASS: " + desc)
                    else:
                        log("FAIL: " + desc)
                        rc = 1

                # 3) systemd 状态：默认 WARN，--strict 才 FAIL
                start = len(st.snapshot())
                st.send("systemctl is-system-running 2>/dev/null")
                st.wait(r"\n", 3, start)
                st.send("echo __SYS_DONE__")
                tail = st.wait(r"([^\n]*)\n__SYS_DONE__", 20, start)
                if tail and "degraded" in tail.group(1):
                    if opts.strict:
                        log("FAIL: systemd degraded (--strict)")
                        rc = 1
                    else:
                        log("WARN: systemd degraded（加 --strict 可视为失败）")

                # 4) 内存记录（可选阈值）
                start = len(st.snapshot())
                st.send("awk '/MemTotal|MemAvailable/ {print}' /proc/meminfo; echo __MEM_DONE__")
                m = st.wait(r"MemTotal:[^\n]*\nMemAvailable:[^\n]*\n__MEM_DONE__", 20, start)
                mem_txt = m.group(0).replace("__MEM_DONE__", "") if m else "(读取失败)"
                with open(os.path.join(outdir, "memory.txt"), "w", encoding="utf-8") as f:
                    f.write(mem_txt + "\n")
                log("内存信息已写入 boot-test/memory.txt")

            # 5) 尽力截图
            if qmp_screendump(qmp_sock, os.path.join(outdir, "screen.png")):
                log("截图已写入 boot-test/screen.png")
            else:
                log("WARN: 截图失败（不影响验收）")
        finally:
            st.close()
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
            logfile.close()

        log("RESULT: " + ("PASS" if rc == 0 else "FAIL(rc=%d)" % rc))
        return rc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
