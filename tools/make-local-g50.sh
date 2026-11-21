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
#   显卡只用 Intel Haswell HD4400 (i915)；NVIDIA GF117M/820M 固件去掉
#   （Optimus 屏幕接核显，nouveau 对老卡支持差，去掉不影响图形且省电）
#   无线 Realtek RTL8723BE (rtl8723be) + 蓝牙 RTL8723B (btusb)
#   有线 RTL8111 固件与无线同在 firmware-realtek 包内（几十 KB，无法分离）
# 极简策略（用户机器固定、不换硬件：无线只保留 Realtek，去掉 Intel/Broadcom/Atheros
# 备选无线固件；去掉 NVIDIA/AMD 显卡固件、服务器级固件）。
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

# —— 只保留本机实际在用的固件（用户机器固定、不换硬件）——
# firmware-realtek        : RTL8723BE 无线 + RTL8111 有线 + RTL8723B 蓝牙（含在同包）
# firmware-intel-graphics : Intel HD4400 核显（本机唯一显示输出，保留）
# firmware-intel-sound / -misc : Intel 声卡等
# intel-microcode / amd64-microcode : CPU 微码
# —— 删除：所有本机用不到的固件 ——
# 备选无线（不换卡）：iwlwifi / brcm80211 / atheros
# 独显（只用 Intel 核显）：nvidia-graphics / amd-graphics
# 服务器/企业/大型阵列/老设备：netronome / marvell / tesla / mediatek 等
DROP="firmware-iwlwifi firmware-brcm80211 firmware-atheros
      firmware-nvidia-graphics firmware-amd-graphics
      firmware-netronome firmware-marvell-prestera firmware-nvidia-tesla-535-gsp
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

# 顺手删除 /lib/firmware 里已无包管理的孤立固件文件
# 只删明确用不到的目录：服务器级 + NVIDIA/AMD 独显 + 备选无线卡，不碰 realtek/intel。
rm -rf /lib/firmware/nvidia 2>/dev/null || true
rm -rf /lib/firmware/netronome 2>/dev/null || true
rm -rf /lib/firmware/marvell/prestera* 2>/dev/null || true
rm -rf /lib/firmware/iwlwifi 2>/dev/null || true
rm -rf /lib/firmware/brcm 2>/dev/null || true
rm -rf /lib/firmware/ath10k /lib/firmware/ath6k /lib/firmware/ath9k_htc 2>/dev/null || true

echo "local-g50: remaining firmware packages: $(dpkg -l 2>/dev/null | grep -ci firmware)"

# 保护性重装：确保本机实际在用的固件一定在（autoremove 可能误删）
# 只留 Realtek（无线+蓝牙+有线）+ Intel 核显/声卡/杂项；CPU 微码不属于 firmware 包。
KEEP="firmware-realtek firmware-intel-graphics \
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
