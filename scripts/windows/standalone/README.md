# Full Windows iOS preview installer

This installs the complete AdbAutoPlayer app, Python 3.13, normal game assets,
and iOS USB/Wi-Fi dependencies. No official app, patch, separate Python
installation or second iOS runtime is required.

The Windows workflow builds from source, installs into a clean temporary
directory, and checks the installed runtime and app startup before upload.
build-info.json records the source commit and installer checksum.

The app is named **AdbAutoPlayer iOS Support**, version **12.13.7+ios.4**.
Its default installation directory differs from the official app. It retains
the existing profile/settings namespace; close other AdbAutoPlayer instances
before running it. Local profiles, pairing records, captures and logs are
never included in the build.

The upstream automatic updater is disabled in this preview so it cannot replace
iOS support with a stock build. Download future full installers from this fork's
Releases page. This preview has no signed automatic-update feed.

After installation:

1. Install Apple's device support (Apple Devices) if needed.
2. Connect and unlock one iPhone/iPad by USB, accept Trust This Computer, and
   enable Developer Mode. Open AFK Journey in English portrait mode.
3. In ADB Settings, enable Enable iOS and leave iOS Python Path blank.
4. Customize tasks through the original Game Settings.
5. For Wi-Fi, also enable Allow iPhone / iPad over Wi-Fi, save, and run
   Capture Debug Screenshot once over USB. Stop automation, unplug USB,
   and keep both devices on the same home network.

Experimental Windows x64 preview. Packaging does not expand the modes verified
in the mode-validation report. Fishing and Matching Cards remain unverified.
Apple developer support may download on first use. Apple drivers are installed
separately, not bundled.

