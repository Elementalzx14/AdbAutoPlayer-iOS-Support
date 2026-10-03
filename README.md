# AdbAutoPlayer iOS Support

Experimental Windows USB support for iPhone, based on
[AdbAutoPlayer/AdbAutoPlayer](https://github.com/AdbAutoPlayer/AdbAutoPlayer).
The original desktop interface, game settings, and task engine are preserved.
**Enable iOS** selects the iPhone controller and visual profile; attempts,
formations, and other game options still come from the existing Game Settings.

**[Download the Windows iOS installer v2 for 12.13.0 (Preview)](https://github.com/Elementalzx14/AdbAutoPlayer-iOS-Support/releases/tag/v12.13.0-ios.2).**
Install official AdbAutoPlayer 12.13.0 first, close it, then run this add-on.
iOS dependencies are bundled and use the app's existing Python 3.13. The installer
preserves game settings and provides backups and restoration. Updating the first
iOS preview? Choose **Restore previous files** in the v2 installer before installing.

See the [iOS setup and validation guide](docs/src/user-guide/ios-setup.md) and
[Windows installer instructions](scripts/windows/ios-installer/README.md).
AFK Stages uses **Battle Modes > AFK Stages**. AFK stage progression and a
Lightbearer Legend Trial cycle were verified on an English portrait iPhone 17 Pro
Max running iOS 27. Dura's already-cleared state was verified; fresh Dura battles,
other towers, other devices, and other task modes need further testing.

This is an independent experimental fork, not an official upstream release.
The source includes upstream **12.13.0**, including its wireless debugging and
Union Campaign features. The original MIT license and credits
are retained. Upstream project information follows.
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

The v2 installer includes the [Python 3.13 integration and device/layout review](docs/src/user-guide/ios-review.md). See the review for live test evidence and remaining upstream release checks.
