# FlickOS（简体中文定制版）

> **本仓库是 FlickOS 2.2 的简体中文定制分支**：预制中文界面、Noto CJK 字体、
> fcitx5 + Rime（luna_pinyin_simp）输入法，开箱即用。
>
> - **下载 ISO**：从本仓库 [Releases](https://github.com/flashmicro/flickos/releases)
>   下载 `FlickOS-64bit-v2.2-zhcn.iso`（约 1.56 GiB），用附带的 `SHA256SUMS` 校验。
> - **中文输入**：进入桌面后按 **Ctrl+Space** 唤醒 Rime，打拼音选汉字（如 nihao → 你好）。
> - **固件**：打包时保留完整固件（含 non-free-firmware），适配更多硬件。
>
> 下方为上游 FlickOS 原始说明。

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
