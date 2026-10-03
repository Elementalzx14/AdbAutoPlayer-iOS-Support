# Integrated iPhone support for AdbAutoPlayer

**Source update (2026-10-03):** See [maintainer review and test results](ios-review.md)
for the Python 3.13 integration, uniform layout, diagnostics and current limitations.
The downloadable `v12.13.0-ios.2` add-on includes these changes and uses the app's
existing Python runtime. The older `v12.13.0-ios.1` release is retained for reference.


The full original menu and Game
Settings remain available. Enable iOS selects the USB controller and iPhone visual
profile; the original game engine reads AFKJourney.toml for attempts, formations,
current/suggested formations, manual-formation policy, exclusions, and trial towers.
There is no separate iPhone battle runner or separate game configuration.

## Verified on the connected iPhone

- Original AFK routine: Battle Modes > AFK Stages, Records, copy, battle, victory,
  and advancement to the next stage. Saved settings: 3 attempts, 7 formations.
- Season AFK: recognizes the Phantimal Challenge button after victory and advances
  through the original battle handler. Stage 433 to 434 verified on the iPhone;
  both victory markers are required before this button can be treated as Next.
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

The fork now includes upstream 12.13.0. The add-on installer preserves that
release's UI executable and existing Python dependency versions. The v2 installer
adds iOS dependencies to the existing Python 3.13 runtime. The older navigation-image
fallback has been removed.

## Build and setup

Build this fork using the [development guide](../development/dev-and-build.md).
The Windows add-on installer targets the official **12.13.0 x64** installation.
See [installer instructions](../../../scripts/windows/ios-installer/README.md).
Official upstream installers alone do not contain the iOS changes.

On Windows, install Apple's USB device support (Apple Devices), official AdbAutoPlayer
12.13.0, and the v2 add-on. No separate Python installation or terminal is required.
Connect exactly one iPhone, unlock it, and accept Trust This Computer. Enable
Developer Mode if requested during connection setup.

In **ADB Settings > iPhone / iOS**, enable **Enable iOS** and leave **iOS Python Path**
blank. Clear an older custom path to use the app's runtime. Keep the phone unlocked and AFK Journey
in English portrait mode. Choose tasks and their settings through the normal UI.
No Mac was used for the tested USB connection.

For source builds, use the Python 3.13 instructions in the [maintainer review](ios-review.md).
`setup-ios.ps1` is retained only for the older standalone Python 3.11 setup.

An official upstream app update can replace these changes. Keep a backup of your
installation and use builds from this fork when retaining iOS support. Disabling
Enable iOS returns device selection to the original Android controller.
