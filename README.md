# FlickOS（简体中文定制版）

> **本仓库是 FlickOS 2.2 的简体中文定制分支**：预制中文界面、Noto CJK 字体、
> fcitx5 + Rime（luna_pinyin_simp）输入法，开箱即用。
>
> - **下载 ISO**：从本仓库 [Releases](https://github.com/flashmicro/flickos/releases)
>   下载 `FlickOS-64bit-v2.2-zhcn.iso`（约 1.56 GiB），用附带的 `SHA256SUMS` 校验。
> - **中文输入**：进入桌面后按 **Ctrl+Space** 唤醒 Rime，打拼音选汉字（如 nihao → 你好）。
> - **固件**：打包时保留完整固件（含 non-free-firmware），适配更多硬件。
> - **账号密码 / 锁屏 / 关机重启**：见下方「使用问答」。
> - **主要软件版本**：见下方「版本一览」（下载前可查看）。
>
> 下方为上游 FlickOS 原始说明。

---

## 简体中文定制版 · 使用问答

**Q1：用户名和密码是多少？**

- **图形界面**：开机自动登录，用户名 `user`，**不需要输入密码**。
- **文本终端 / 串口登录**（Ctrl+Alt+F2 或虚拟机串口）：用户名 `user`，密码 `live`。
- **管理员权限（sudo）**：live 会话里免密可用；个别弹窗若要求密码，输入 `live`。

**Q2：会自动锁屏吗？**

- **不会。** live 会话刻意关闭了自动锁屏与自动休眠——`swayidle` 只在装机后的系统里才
  启动，所以试用 ISO 时用着用着不会突然黑屏要密码。
- 装机后的系统默认 **5 分钟**锁屏、**15 分钟**休眠；在「设置 → 电源与空闲」里都调成
  “从不”即可关闭。

**Q3：为什么 `poweroff` / `reboot` 不能直接用？怎么关机重启？**

- 现象：直接敲 `poweroff`、`reboot`、`shutdown` 会报 `command not found`。
- 原因：这些命令在 `/usr/sbin/`，普通用户的 `$PATH` 不包含该目录。
- **方法一（推荐，最简单）**：图形界面点菜单里的「关机 / 重启」，不用敲命令、不用密码。
- **方法二**：命令行用绝对路径加 sudo：

  ```sh
  sudo /usr/sbin/poweroff   # 关机
  sudo /usr/sbin/reboot     # 重启
  ```

  live 会话 sudo 免密；若提示密码，输入 `live`。
- **方法三**：先 `sudo -i` 切到 root，再直接敲 `poweroff` 或 `reboot`。

**Q4：软件源是国内源还是国外源？**

- **制作 ISO 时**：用 Debian 官方源（`deb.debian.org`），从海外 CI 下载包最快最稳，
  与国内源无关。
- **安装到硬盘后**：`/etc/apt/sources.list` 会自动写成**清华 TUNA 国内镜像**
  （`mirrors.tuna.tsinghua.edu.cn`，含 main / updates / security），日常更新、
  装软件在国内速度更快。FlickOS 自己的软件源（GitHub Pages）保持不变。
- **想切回官方源**（例如出国后）：把国内镜像地址替换回官方，再更新索引：

  ```sh
  sudo sed -i \
    -e 's#https://mirrors.tuna.tsinghua.edu.cn/debian-security#http://security.debian.org/debian-security#g' \
    -e 's#https://mirrors.tuna.tsinghua.edu.cn/debian#http://deb.debian.org/debian#g' \
    /etc/apt/sources.list
  sudo apt update
  ```

## 版本一览（下载前可查看）

以下为 **v2.2 中文版 ISO 内实际安装**的版本（取自该次构建的 `build.log`，非仓库候选版本）。
每次重新构建会随 Debian trixie 更新，此处以当次 release 为准。

| 软件 | 版本 |
|---|---|
| 基础系统 | Debian 13 (trixie)，live-boot 20250815 |
| Linux 内核 | 6.12.117-1 |
| 桌面 | labwc（Wayland） |
| 安装器 | Calamares 3.3.14 |
| 输入法框架 | fcitx5 5.1.12 |
| Rime 引擎 | librime 1.13.1（fcitx5-rime 5.1.10） |
| 简体词库 | rime-data-luna-pinyin（luna_pinyin_simp） |
| 中文字体 | Noto CJK 20240730 |
| 浏览器 | Firefox ESR 153.7.0esr |
| 办公套件 | LibreOffice 25.2.3 |
| 虚拟化 | QEMU 10.0.13 |

> 完整清单（`flickos-amd64.packages`，含每个包及精确版本）在构建时生成；
> 未来计划把它作为 release 资产上传，便于下载前逐项核对。

---

FlickOS is a lightweight Linux distribution. Version **2.0** is based on
Debian 13 (trixie) with a Wayland desktop built on [labwc](https://labwc.github.io/),
and ships as a bootable live ISO with the Calamares graphical installer.
(FlickOS 1.x was based on Ubuntu 20.04 and LXLE.)

- **Downloads:** https://sourceforge.net/projects/flickos/files/
- **Package repository:** https://dvbondoy.github.io/flickos-apt/
- **Issues:** https://github.com/dvbondoy/FlickOS/issues
- **Community:** https://www.reddit.com/r/flickos/
- **Website:** https://flickos.net
- **License:** GPL-3.0-or-later ([LICENSE](LICENSE)). Some files have their own
  license (wallpapers from Unsplash, installer settings from Debian): see each
  package's `debian/copyright`.
- **Name and logo:** a changed FlickOS you share needs its own name and logo;
  see [TRADEMARKS.md](TRADEMARKS.md).

This repository contains everything needed to build it:

- the **live-build configuration** that turns Debian packages into an ISO,
- the **FlickOS Debian packages** (desktop meta-package, default settings, repo keyring),
- the **apt repository tooling** that publishes those packages so installed systems get updates,
- the **CI workflow** that builds the ISO on GitHub.

## Contributors

Package Tester and Community Manager
- **Ryan Hines** [rthines81@gmail.com](rthines81@gmail.com)

Translator
- **kurkimusic_74955**


## Documentation

Read these in order the first time. Afterwards, use them as reference.

| Doc | What it covers |
|---|---|
| [01 – Overview](docs/01-overview.md) | How the pieces fit together, repository layout, boot flow |
| [02 – Building and testing](docs/02-building-and-testing.md) | Building the ISO locally, testing in QEMU (BIOS and UEFI), installing to a VM disk |
| [03 – live-build configuration](docs/03-live-build-config.md) | `auto/config`, package lists, hooks, boot menu, adding files to the image |
| [04 – Packages](docs/04-packages.md) | The FlickOS packages, changing them, versioning, creating a new package |
| [05 – Apt repository](docs/05-apt-repository.md) | Signing key, publishing to SourceForge, moving the repository, key backup and rotation |
| [06 – CI and releases](docs/06-ci-and-releases.md) | Version number, GitHub Actions workflow, SourceForge uploads, release checklist |
| [07 – Troubleshooting](docs/07-troubleshooting.md) | Common failures and how to fix them |
| [08 – Reference](docs/08-reference.md) | Command cheat sheet, file index, glossary, external manuals |
| [09 – Customizing](docs/09-customizing.md) | How FlickOS is put together and how to change it: desktop, apps, menus, keybindings, installer, boot menu, boot splash, OS name, firewall |
| [10 – Custom builds](docs/10-custom-builds.md) | Building a variant for someone else: site defaults, a variant meta-package, rebranding, a client apt suite, unattended and OEM installs |
| [Design guidelines (HIG)](docs/hig/README.md) | How FlickOS programs look, behave, read and are built: principles, windows, writing, style, accessibility, performance, packaging, code. Every package follows them; review changes with its checklist |
