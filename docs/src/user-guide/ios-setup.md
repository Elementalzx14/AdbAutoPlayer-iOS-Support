# Integrated iPhone support for AdbAutoPlayer

The full original menu and Game
Settings remain available. Enable iOS selects the USB controller and iPhone visual
profile; the original game engine reads AFKJourney.toml for attempts, formations,
current/suggested formations, manual-formation policy, exclusions, and trial towers.
There is no separate iPhone battle runner or separate game configuration.

## Verified on the connected iPhone

- Original AFK routine: Battle Modes > AFK Stages, Records, copy, battle, victory,
  and advancement to the next stage. Saved settings: 3 attempts, 7 formations.
- Original Legend routine: Lightbearer floor won; a subsequent complete floor
  cycle copied a formation, won, recognized Next, and advanced. Tests were bounded
  so the app was not left running unattended.
- Original Dura task: recognized the current limit/already-cleared state and exited.
  New Dura battles could not be tested because this account has no entries left.
- 68 focused tests passed for iOS images, popup dimming, victory discrimination,
  settings/dispatch, shared retry policy, and existing AFK/navigation behavior.

## What changed

An iPhone image profile supplies visual equivalents to the original template names.
Navigation and battle buttons use their detected locations. The original AFK
post-navigation reward tap is skipped on iOS. Screenshot and touch coordinates use
the same logical canvas. Trial images and Back navigation are supplied separately.
The shared game-mode policy remains responsible for settings and retries.

## Limits

Validated layout: English, portrait iPhone 17 Pro Max, iOS 27 (1320 x 2868 native).
Other iPhones/iPads, unavailable Legend towers, new Dura battles, and the other
menu modes are not fully validated. Manual-formation and hero-exclusion matching
have image regression coverage, not exhaustive live coverage for every hero/skin.
Changing game layouts may require additional recognition images.

The navigation source includes upstream's locked-Dura check and its missing image
for compatibility with the installed v12.12.2 resources. The UI executable and
original Python dependencies are unchanged. The isolated ios-runtime is reused.

## Build and setup

Build this fork using the [development guide](../development/dev-and-build.md).
No prebuilt iOS-support release is published yet. Official upstream installers do
not contain these changes.

On Windows, install Python 3.11 and Apple's USB device support (Apple Devices),
then connect exactly one iPhone, unlock it, and accept Trust This Computer.
Run from this repository in PowerShell, substituting your actual paths:

```powershell
.\scripts\windows\setup-ios.ps1 -AppDirectory "C:\path\to\app" -Python311 "C:\path\to\Python311\python.exe"
```

In **ADB Settings > iPhone / iOS**, enable **Enable iOS**. If running from source
or using a custom runtime location, set **iOS Python Path** to the absolute path
of `ios-runtime\Scripts\python.exe`. Keep the phone unlocked and AFK Journey
in English portrait mode. Choose tasks and their settings through the normal UI.
No Mac was used for the tested USB connection.

An official upstream app update can replace these changes. Keep a backup of your
installation and use builds from this fork when retaining iOS support. Disabling
Enable iOS returns device selection to the original Android controller.
