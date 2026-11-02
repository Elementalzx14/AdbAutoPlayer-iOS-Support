# AdbAutoPlayer iOS Support

**[Download the full Windows installer — 12.13.7 iOS Preview 4](https://github.com/Elementalzx14/AdbAutoPlayer-iOS-Support/releases/tag/v12.13.7-ios.4).**

This is a complete installer: the app, Python 3.13 runtime, iOS dependencies,
normal game assets, and USB/Wi-Fi support are included. No official app,
separate Python installation, or add-on patch is required. Apple device drivers
are installed separately.

The installer was built from source and passed a clean Windows installation,
bundled-runtime checks, and app-startup verification. Its checksum and source
commit are included in the release.

The original game settings and task engine remain available. Enable iOS in ADB
Settings and leave iOS Python Path blank. For wireless setup, connect by USB once,
enable Allow iPhone / iPad over Wi-Fi, save, and run Capture Debug Screenshot.
Afterward stop automation, unplug USB, and keep both devices on the same network.

**Latest development source:** [ios-all-modes](https://github.com/Elementalzx14/AdbAutoPlayer-iOS-Support/tree/ios-all-modes).
See the [full installer instructions](https://github.com/Elementalzx14/AdbAutoPlayer-iOS-Support/blob/ios-all-modes/scripts/windows/standalone/README.md)
and [mode validation report](https://github.com/Elementalzx14/AdbAutoPlayer-iOS-Support/blob/ios-all-modes/docs/src/user-guide/ios-mode-validation.md).

This is an experimental Windows x64 fork based on upstream 12.13.7, not an
official upstream release. M1 iPad USB/Wi-Fi capture and input were tested.
Some game modes remain unverified; packaging does not make every mode tested.
Fishing and Matching Cards remain unverified.

Close other AdbAutoPlayer instances before starting this build. It uses the
existing settings namespace. Automatic upstream updates are disabled in the full
preview to preserve iOS support; use this fork's future full installers to update.

Older 12.13.0 add-on installers are historical downloads and should not be applied
to this full build. The original MIT license and upstream credits are retained.
Upstream project information follows.

[![codecov](https://codecov.io/github/AdbAutoPlayer/AdbAutoPlayer/branch/main/graph/badge.svg?token=0VCZKXZO9P)](https://app.codecov.io/github/AdbAutoPlayer/AdbAutoPlayer)  

## Modern & Customizable Android Game Bot

AdbAutoPlayer is a powerful tool designed to automate repetitive tasks in Android games using ADB.

### ➜ [Access the Full Documentation & Wiki](https://AdbAutoPlayer.github.io/AdbAutoPlayer/)

![AdbAutoPlayer UI](docs/src/images/app/ui-main.png)

---

## Features
- **Modern UI:** Flexible interface with sidebar navigation and live logs.
- **Customizable:** Change themes, accent colors, and view modes (Cards, Palette, Accordion).
- **Multi-Game:** Support for AFK Journey, Guitar Girl, and more.
- **Cross-Platform:** Works on Windows and macOS.

---

## Development
Interested in contributing or building from source?
### ➜ [Development & Build Guide](https://adbautoplayer.github.io/AdbAutoPlayer/development/dev-and-build.html)

---

## Contact
### AFK Journey
[Discord: Yaphalla](https://discord.gg/yaphalla)  
[Channel: adb-auto-player](https://discord.com/channels/1332082220013322240/1338732933057347655)

### iOS maintainer review

See the current mode validation report for live test evidence and remaining checks.
