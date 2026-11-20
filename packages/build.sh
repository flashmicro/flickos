#!/bin/sh
# 重建脚本（公开仓库缺此文件）：构建 packages/ 下每个含 debian/ 的本地包，
# 在 packages/.build/ 副本里构建，把 .deb 收进 config/packages.chroot/。
set -e

cd "$(dirname "$0")/.."
ROOT=$(pwd)
BUILD_DIR="$ROOT/packages/.build"
OUT_DIR="$ROOT/config/packages.chroot"

mkdir -p "$BUILD_DIR" "$OUT_DIR"

# 构建前的关键检查：FlickOS apt 仓库公钥必须存在。
if [ ! -f "$ROOT/packages/flickos-archive-keyring/keyrings/flickos-archive-keyring.asc" ]; then
    echo "ERROR: missing FlickOS repository public key" >&2
    exit 1
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

for srcdir in "$ROOT"/packages/*/; do
    [ -d "$srcdir/debian" ] || continue
    pkg=$(basename "$srcdir")
    echo "==> building $pkg"
    cp -a "$srcdir" "$BUILD_DIR/$pkg"
    (
        cd "$BUILD_DIR/$pkg"
        dpkg-buildpackage -us -uc -b
    )
done

# 收集所有 .deb
find "$BUILD_DIR" -maxdepth 1 -name '*.deb' -exec cp -f {} "$OUT_DIR/" \;

echo "==> built packages in $OUT_DIR:"
ls -1 "$OUT_DIR"/*.deb 2>/dev/null | xargs -r -n1 basename
