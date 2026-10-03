# Windows iOS Support installer for AdbAutoPlayer 12.13.0

This is an **add-on installer** for the official Windows x64 12.13.0 release.
Version 2 adds iOS dependencies to the app's existing Python 3.13 runtime.
It does not install a second Python runtime. All add-on files are included for
offline installation; downloading the base app and Apple drivers requires internet.
Users do not need Python, a terminal, or a Mac to install the add-on.
The installer is unsigned; no publisher certificate is included.

## For new users

1. Install [Apple Devices from Microsoft](https://apps.microsoft.com/detail/9np83lwlpz9k)
   for the Apple USB drivers.
2. Download and install `AdbAutoPlayer_12.13.0_x64-setup.exe` from the
   [official 12.13.0 release](https://github.com/AdbAutoPlayer/AdbAutoPlayer/releases/tag/12.13.0).
3. Close AdbAutoPlayer and any running tasks.
4. Run `AdbAutoPlayer-iOS-Support-12.13.0-v2-Setup.exe`. Confirm the app folder
   (normally `%LOCALAPPDATA%\AdbAutoPlayer`) and click **Install iOS Support**.
5. Connect one iPhone by USB, unlock it, and accept **Trust This Computer**.
   Open AFK Journey in English, portrait orientation. Keep the phone unlocked.
6. Open AdbAutoPlayer, select **ADB Settings > iPhone / iOS > Enable iOS**.
   Leave **iOS Python Path** blank to use the app's runtime. Clear any old custom path.
7. Customize tasks in the normal **Game Settings**, then start a task.

The installer checks the official 12.13.0 executable and the files it replaces.
Other versions and unexpected modifications are rejected before changes begin.
It does not modify game settings, Apple pairing data, or the original UI executable.
Wireless debugging and Union Campaign from 12.13.0 remain present. Their presence
does not imply those tasks have been validated on iOS.

Tested phone layout: iPhone 17 Pro Max, iOS 27, English portrait. Other devices,
especially iPads, still require layout testing. An upstream app update may replace
the iOS add-on; do not assume this installer works on a different version.

## Updating the first iOS installer

Close AdbAutoPlayer. Run this v2 installer and choose **Restore previous files**
first, then **Install iOS Support**. The v2 installer understands the original
preview's backup format. Your game settings are preserved. If the app itself was
updated or its original backups were removed, install a clean official 12.13.0 copy
and apply the add-on there instead.

## Restore

Close the app, rerun this installer, select the same app folder, and choose
**Restore previous files**. It validates and restores the saved app files and
removes the dependencies it added.
It refuses to overwrite files changed by a subsequent app update. Backups live in
`ios-support-backups` inside the app folder; keep them if you want to restore.
If restoring the stock app, turn Enable iOS off before restoring. Settings are
preserved, including any previously selected device options.

## Building

Use `build.py --help`. Inputs are `--stock` (an extracted official 12.13.0 Windows
installer), `--prepared` (a copy with the iOS dependencies installed), `--bootstrap`
(a temporary installer helper), and `--output` (the resulting EXE).

Keep the stock input unmodified. In the prepared copy, install `pymobiledevice3==11.19.4`
with uv, using `scripts/windows/ios-runtime-overrides.txt` and constraints pinning
every dependency already shipped in stock. The override excludes `lzfse`; the
tested CoreDevice screenshot/HID path does not need it. Firmware and DDI operations
are outside this add-on's scope. The build compares the fork with tag `12.13.0`,
includes changed backend files and additional dependencies, and records hashes of
the official executables and every replaced file.

The temporary helper has `Scripts/python.exe` (Python 3.11 x64 embeddable), its
DLLs and standard-library ZIP, and psutil in `Lib/site-packages`. It runs the
installer only, is extracted to a temporary folder, and is removed afterward.
It is never installed into AdbAutoPlayer. Include Python's license and dependency
distribution metadata/licenses. The Python embeddable distribution is from python.org.

Compile `Setup.cs` using the Windows .NET Framework C# compiler with references to
System.Windows.Forms, System.Drawing, System.IO.Compression, and
System.IO.Compression.FileSystem, embedding the generated ZIP as `payload.zip`.
The included build script does this on Windows.

For automated testing, the EXE accepts `--check`, `--install`, or `--restore`,
followed by the app directory and an optional output log filename. Check returns
without changing the app. Test installation/restore only on a disposable copy.
