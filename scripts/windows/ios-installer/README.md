# Windows iOS Support installer for AdbAutoPlayer 12.13.0

This is an **add-on installer** for the official Windows x64 12.13.0 release.
It includes a private Python 3.11 runtime and iOS connection dependencies.
Users do not need Python, a terminal, or a Mac to install the add-on.
The installer is unsigned; no publisher certificate is included.

## For new users

1. Install [Apple Devices from Microsoft](https://apps.microsoft.com/detail/9np83lwlpz9k)
   for the Apple USB drivers.
2. Download and install `AdbAutoPlayer_12.13.0_x64-setup.exe` from the
   [official 12.13.0 release](https://github.com/AdbAutoPlayer/AdbAutoPlayer/releases/tag/12.13.0).
3. Close AdbAutoPlayer and any running tasks.
4. Run `AdbAutoPlayer-iOS-Support-12.13.0-Setup.exe`. Confirm the app folder
   (normally `%LOCALAPPDATA%\AdbAutoPlayer`) and click **Install iOS Support**.
5. Connect one iPhone by USB, unlock it, and accept **Trust This Computer**.
   Open AFK Journey in English, portrait orientation. Keep the phone unlocked.
6. Open AdbAutoPlayer, select **ADB Settings > iPhone / iOS > Enable iOS**.
   Leave **iOS Python Path** blank to use the bundled runtime.
7. Customize tasks in the normal **Game Settings**, then start a task.

The installer checks the official 12.13.0 executable and the files it replaces.
Other versions and unexpected modifications are rejected before changes begin.
It does not modify game settings, Apple pairing data, or the original UI executable.
Wireless debugging and Union Campaign from 12.13.0 remain present. Their presence
does not imply those tasks have been validated on iOS.

Tested phone layout: iPhone 17 Pro Max, iOS 27, English portrait. Other devices,
especially iPads, still require layout testing. An upstream app update may replace
the iOS add-on; do not assume this installer works on a different version.

## Restore

Close the app, rerun this installer, select the same app folder, and choose
**Restore previous files**. It validates and restores its saved files and runtime.
It refuses to overwrite files changed by a subsequent app update. Backups live in
`ios-support-backups` inside the app folder; keep them if you want to restore.
If restoring the stock app, turn Enable iOS off before restoring. Settings are
preserved, including any previously selected device options.

## Building

Use `build.py --help`. Inputs are the merged fork source, an extracted official
12.13.0 Windows installer, and a prepared portable Python 3.11 runtime. The build
compares the fork with tag `12.13.0`, includes only changed backend files, and hashes
the actual official executable and replaced files. Do not use a modified stock input.

The portable runtime has `Scripts/python.exe`, its Python DLLs and standard-library
ZIP beside it, and dependencies in `Lib/site-packages`. It must import OpenCV,
psutil, and pymobiledevice3's userspace tunnel without a system Python installation.
The Python embeddable distribution comes from python.org. Install the pinned iOS
requirements into the target site-packages using a matching Python 3.11 x64 build.
Include Python's license and the dependencies' distribution metadata/licenses.

Compile `Setup.cs` using the Windows .NET Framework C# compiler with references to
System.Windows.Forms, System.Drawing, System.IO.Compression, and
System.IO.Compression.FileSystem, embedding the generated ZIP as `payload.zip`.
The included build script does this on Windows.

For automated testing, the EXE accepts `--check`, `--install`, or `--restore`,
followed by the app directory and an optional output log filename. Check returns
without changing the app. Test installation/restore only on a disposable copy.
