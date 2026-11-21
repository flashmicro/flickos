#!/bin/sh
# ============================================================================
# 把完整版源码树改造成「Lenovo G50-70M 本机精简版」配置。
# 只在独立 workflow (iso-local.yml) 里 checkout 之后运行；
# 完整版 (iso.yml / v2.2) 的构建完全不调用本脚本，互不干扰。
#
# 精简项（用户指定）：
#   1) 去掉 LibreOffice 全家桶（flickos-desktop 的 Recommends + 中文语言包）
#   2) 裁剪 G50-70M 用不到的固件（服务器/企业/其它厂商），只保留本机需要的
# 保留项：中文输入法、Firefox、QEMU、arch-install-scripts、完整中文环境、
#         Calamares 安装器、清华源（live + 装机后）。
#
# G50-70M 实际硬件（Linux 探测报告 probe 0b1a40c724）：
#   显卡 Intel Haswell HD4400 (i915) + NVIDIA GF117M/820M (nouveau)
#   有线 Realtek RTL8111 (r8169)，无线 Realtek RTL8723BE (rtl8723be)
#   蓝牙 Realtek RTL8723B (btusb)，声卡 Intel HD Audio (snd_hda_intel)
# 同型号可能换装 Intel 3160 / Broadcom 43142 / Atheros QCNFA335 无线卡，
# 故这四家的无线固件都保留，避免换卡后无法上网。
# ============================================================================
set -e

cd "$(dirname "$0")/.."

echo "==> [local-g50] 1) 去掉 LibreOffice 中文语言包"
# 主因：这个包依赖拉入 libreoffice-core 全家桶（--apt-recommends false 下，
# 仅靠 0050 hook 装 Recommends；但本包被显式列出，会带出整套 LibreOffice）。
sed -i '/^libreoffice-l10n-zh-cn$/d' config/package-lists/cn-l10n.list.chroot

echo "==> [local-g50] 2) 让 0050 hook 安装 Recommends 时跳过 LibreOffice"
# 0050 hook 读取 flickos-desktop 的 Recommends 并安装；过滤掉 libreoffice*，
# 否则 writer/calc/impress/draw/gtk3 会被重新装回来。用完整覆盖避免 sed 转义陷阱。
HOOK050=config/hooks/normal/0050-flickos-recommends.hook.chroot
cat > "$HOOK050" <<'REC'
#!/bin/sh
# local-g50 变体：安装 flickos-desktop 的 Recommends，但跳过 LibreOffice。
set -e
recommends="$(dpkg-query -W -f='${Recommends}' flickos-desktop \
    | sed -e 's/([^)]*)//g' -e 's/,/ /g')"
filtered=""
for r in $recommends; do
    case "$r" in
        libreoffice*) continue ;;
        *) filtered="$filtered $r" ;;
    esac
done
apt-get install -y --no-install-recommends $filtered
REC
chmod 755 "$HOOK050"

echo "==> [local-g50] 3) 注入固件裁剪 hook（purge 用不到的固件包）"
cat > config/hooks/normal/0600-local-g50-trim.hook.chroot <<'TRIMEOF'
#!/bin/sh
# Lenovo G50-70M 本机版：删除用不到的固件包，保留本机 + 常见备选网卡固件。
# 在 packages 安装后、squashfs 打包前运行；用 --purge 连配置文件一起删。
set -e

# —— 必须保留（本机硬件 + 同型号可能换装的网卡）——
# firmware-realtek    : RTL8723BE 无线 + RTL8111 有线 + 蓝牙（本机实际）
# firmware-iwlwifi    : Intel 3160（备选无线卡）
# firmware-brcm80211  : Broadcom BCM43142（备选无线卡）
# firmware-atheros    : Atheros QCNFA335（备选无线卡）
# firmware-nvidia-graphics / firmware-amd-graphics : 显卡（保留两家以防换卡）
# firmware-intel-graphics / -sound / -misc : Intel 核显/声卡/蓝牙等
# intel-microcode / amd64-microcode : CPU 微码
# —— 删除：服务器/企业级/大型阵列/老设备固件，G50-70M 绝无可能用到 ——
DROP="firmware-netronome firmware-marvell-prestera firmware-nvidia-tesla-535-gsp
      firmware-mediatek firmware-qlogic firmware-myricom firmware-netxen
      firmware-bnx2 firmware-bnx2x firmware-cavium firmware-siano
      firmware-zd1211 firmware-ipw2x00 firmware-libertas firmware-misc-nonfree
      atmel-firmware dahdi-firmware-nonfree firmware-ivtv"

# 只 purge 已安装的包，未安装的忽略；失败不阻断构建。
installed=""
for p in $DROP; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q '^install ok installed' && installed="$installed $p"
done
if [ -n "$installed" ]; then
    echo "local-g50: purging firmware:$installed"
    DEBIAN_FRONTEND=noninteractive apt-get purge -y $installed >/dev/null 2>&1 || true
    apt-get autoremove --purge -y >/dev/null 2>&1 || true
    apt-get clean
else
    echo "local-g50: no listed firmware packages installed, skip"
fi

# 顺手删除 /lib/firmware 里已无包管理的孤立大文件（如 nvidia tesla gsp）
# 只删明确的服务器级固件目录，不碰网卡/显卡。
rm -rf /lib/firmware/nvidia/tesla* 2>/dev/null || true
rm -rf /lib/firmware/netronome 2>/dev/null || true
rm -rf /lib/firmware/marvell/prestera* 2>/dev/null || true

echo "local-g50: remaining firmware packages: $(dpkg -l 2>/dev/null | grep -ci firmware)"

# 保护性重装：确保本机 + 备选网卡/显卡固件一定在（autoremove 可能误删）
KEEP="firmware-realtek firmware-iwlwifi firmware-brcm80211 firmware-atheros \
      firmware-nvidia-graphics firmware-amd-graphics firmware-intel-graphics \
      firmware-intel-sound firmware-intel-misc"
need=""
for p in $KEEP; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q '^install ok installed' || need="$need $p"
done
if [ -n "$need" ]; then
    echo "local-g50: re-installing key firmware:$need"
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $need >/dev/null 2>&1 || true
fi
TRIMEOF
chmod 755 config/hooks/normal/0600-local-g50-trim.hook.chroot

echo "==> [local-g50] 4) 放宽 boot-test 固件检查阈值（本机版固件包较少）"
# 完整版检查 >10；本机版保留约 8-10 个固件包，且这才是"精简"的预期，放宽到 >5。
# 用整行更稳妥：匹配包含 firmware 计数且 -gt 10 的那一行
sed -i '/grep -ci firmware/s/-gt 10/-gt 5/' tools/boot-test.py
sed -i 's/固件: 完整保留（G50-70）/固件: 本机关键固件保留（G50-70M）/' tools/boot-test.py

echo "==> [local-g50] 5) 改 ISO 显示名为本机版"
# auto/config 里 --iso-volume 属于ISO元数据，改成可辨识的本机版名称；
# 实际文件名仍由 build-iso.sh 生成，CI 里再 mv 成本机版名。
sed -i 's#--iso-volume             "FlickOS ${FLICKOS_VERSION} amd64"#--iso-volume             "FlickOS ${FLICKOS_VERSION} G50-70M amd64"#' auto/config

echo "==> [local-g50] 配置改造完成"
