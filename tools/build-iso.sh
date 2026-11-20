#!/bin/sh
# 本地/CI 构建 FlickOS ISO 的原生脚本（因公开仓库缺 tools/ 而重建）。
# 步骤严格对应 docs/02-building-and-testing.md 中 build-iso.sh 的记录。
# 用法：在仓库根目录运行；普通用户会 sudo 一次，root(CI/容器)直接跑。
set -e

cd "$(dirname "$0")/.."

# 嵌套容器沙箱：宿主内核禁止 mount，欺骗 debootstrap 跳过 check_sane_mount
# （否则报 "Cannot install into target mounted with noexec"）。
export container=lxc

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
    echo "==> 需要 sudo，请在提示时输入密码"
    $SUDO -v
fi

LOG=build.log
: > "$LOG"

CLEAN_ARGS=""
if [ "${1:-}" = "--purge" ]; then
    CLEAN_ARGS="--purge"
    echo "==> --purge：同时清空 cache"
fi

echo "==> [1/4] lb clean（保留 cache 以加速；--purge 时清空）"
$SUDO lb clean $CLEAN_ARGS

echo "==> [2/4] 构建本地 FlickOS 包 -> config/packages.chroot/"
sh packages/build.sh >> "$LOG" 2>&1 || { echo "ERROR: packages/build.sh 失败，见 $LOG" >&2; exit 1; }

echo "==> [3/4] lb config"
lb config >> "$LOG" 2>&1 || { echo "ERROR: lb config 失败，见 $LOG" >&2; tail -20 "$LOG" >&2; exit 1; }

echo "==> [4/4] lb build"
$SUDO lb build >> "$LOG" 2>&1 || { echo "ERROR: lb build 失败，见 $LOG" >&2; tail -30 "$LOG" >&2; exit 1; }

echo "==> 重命名 ISO 并生成校验和"
. ./packages/flickos-branding/usr/lib/flickos-release
if [ -f "flickos-amd64.hybrid.iso" ]; then
    mv "flickos-amd64.hybrid.iso" "FlickOS-64bit-v${FLICKOS_VERSION}-zhcn.iso"
fi
sha256sum FlickOS-64bit-v*.iso > SHA256SUMS 2>/dev/null || true
echo "==> 完成："
ls -lh FlickOS-64bit-v*.iso SHA256SUMS 2>/dev/null || true
