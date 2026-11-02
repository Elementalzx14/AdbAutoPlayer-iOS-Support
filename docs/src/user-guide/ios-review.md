# iOS maintainer review — 2026-10-03

> This is the historical October review. Current 12.13.7 iPad layout/video work
> and its unfinished mode validation are tracked in the
> [Apple mode validation report](ios-mode-validation.md). The current runtime
> uses the official `lzfse==0.4.2.post1` Windows wheel; the old exclusion described
> below no longer applies to current source.

This branch builds on upstream 12.13.0 and retains the original game menu and settings.
The `v12.13.0-ios.3` add-on installer includes this review and uses the app's existing
Python 3.13. The older `v12.13.0-ios.1` installer remains available for reference.

## Installer correction after a user report

The v2 clean-install and marked-preview upgrade tests missed a real condition:
installing upstream over the earlier manual iOS setup left 49 added iOS files and
no installer marker. V2 rejected even an identical `device/ios/__init__.py` because
it expected every added file to be absent. Those tests did not cover every upgrade
state, and their passing result must not be described that way.

V3 accepts files identical to its payload and fingerprinted additions from the
early fork revisions. JSON template manifests are compared by canonical contents
to tolerate formatting changes. Unknown changes and modified stock files remain
protected. Every replaced existing file is backed up, including accepted leftovers;
rollback and Restore preserve those previous contents. The game backend and runtime
dependencies are unchanged from v2. Nineteen installer regression tests cover the
original checks and these additional upgrade/restore cases.

## Runtime integration

Windows builds can install `src-tauri[ios]` into the application's existing Python
3.13 interpreter. The controller prefers this interpreter when pymobiledevice3 is
present. An explicitly configured Python path takes precedence; legacy add-on
installations can still fall back to `ios-runtime/Scripts/python.exe`.

The Windows build passes `scripts/windows/ios-runtime-overrides.txt` to uv. This
excludes lzfse, whose 0.4.2 release has no CPython 3.13 Windows wheel. This is a
narrow CoreDevice HID/screenshot configuration, not a fully functional installation
of every pymobiledevice3 command. Importing pyimg4 or using firmware/DDI operations
can fail without lzfse. Do not advertise those operations as supported.

An alternative is to build a CPython 3.13 Windows lzfse wheel using MSVC on a build
machine, then install it and remove the override. This has not been built/tested
in this review. End users should not need a compiler or another Python runtime.

Reproduce the tested setup in an isolated environment (PowerShell, repository root):

```powershell
uv venv --python 3.13 .venv-ios
uv pip install --python .venv-ios/Scripts/python.exe --override scripts/windows/ios-runtime-overrides.txt './src-tauri[ios]' pytest
```

The publish workflow includes the iOS extra and override only on Windows. The Python package installation with the iOS extra was built and tested locally,
including launch, the real running bundle ID and five captures without PYTHONPATH.
A full packaged desktop executable still needs CI verification before an upstream release.

## Changes from the review

- A shared DeviceController Protocol describes the methods used by the game engine.
- Game lifecycle comparisons now use the actual Apple bundle ID. A per-game mapping
  table replaces the fake Android identifier inside the worker.
- AFK navigation/battle differences live in layout policies. Shared battle, retry,
  formation and navigation routines no longer branch on `using_ios`.
- Removed the obsolete 12.12.2 `coming_soon` image-loading workaround.
- Screenshots fit uniformly inside the 1080 x 1920 canvas. Letterbox bars retain the
  entire native screen, including both safe areas. Taps invert that exact viewport
  and reject points in the bars. Width-only scaling followed by cropping was avoided
  because it would discard top/bottom controls on tall phones.
- Template regions and hero search regions are relative to the viewport. Legacy iOS
  assets are rescaled into it. Hero icon variants now scale equally on both axes; the vertical distortion factor
  has been removed.
  Android templates are not assumed to become compatible solely from uniform scaling.
- Mode-card searches tolerate vertical movement from event banners.
- A local temporary BMP replaces normalized PNG compression and base64 text transport.
  The device still supplies its native PNG. Per-session temporary frames are deleted
  on close; manual debug captures are retained separately.
- Startup logs include model code, iOS version, native size and canvas size, excluding
  account names, UDIDs and pairing records.
- Capture Debug Screenshot saves native PNG, normalized BMP and JSON with viewport,
  device information and raw match scores/color differences for every iOS manifest
  template. These are visual scores; victory/selected-formation guards still apply.
- Windows-only status and task verification limits appear in settings. Unverified
  tasks/custom routines emit warnings while preserving their original settings.
- Connection errors explain USB, trust and lock problems. Reads may reconnect once
  to the same device; taps/swipes are never automatically replayed after failure.
  Cleanup is bounded and reconnecting cannot silently select another iPhone.

## Live evidence and limitations

Test device: iPhone 17 Pro Max (`iPhone18,2`), iOS 27.0, English portrait,
1320 x 2868. Python 3.13.9, pymobiledevice3 11.19.4, lzfse absent.

Verified in this review:

- Imports, USB connection, app launch, repeated screenshots and taps.
- Uniform viewport: x=98, y=0, width=884, height=1920.
- Battle Modes > AFK Stages recognition and entry despite the Guild Duel banner.
- Season/Phantimal selection, Records formation copy, Battle start, defeat recognition
  and return to the formation screen through the original handlers.
- Mid-capture USB unplug stops with an actionable error. A fresh connection after
  reconnecting the same device captures normally.
- Local debug report contains both frames and per-template scores.

Keeping ScreenCaptureService open across captures was tested and caused a timeout
on a subsequent capture. Reopening it restored reliable captures. The implementation
therefore retains one tunnel/HID session but reopens the screenshot service. Do not
claim this suggestion improved performance: the reliable updated worker measured
about 0.68–0.84 seconds per screenshot in the sampled runs. No controlled end-to-end
speedup benchmark has been completed.

The CoreDevice `getlockstate` action reports "not implemented" on this phone;
we do not depend on it. The lockdown PasswordProtected indicator was verified true
while locked and false after unlocking. It is checked before capture/input, and
unit tests verify locked devices cannot receive taps. Trust revocation has not been tested by deleting pairing
records. Automatic recovery from a brief transient is implemented but has not been physically validated;
resuming an interrupted battle without user review is not promised.

Historical USB build validation: ordinary AFK victories/advancement, Season AFK
433→434, and Lightbearer Legend victories/Next. Those historical observations must
not be represented as new live victory tests of this refactor. Dura was tested only
for navigation and its already-cleared/limit state, not a fresh battle. Other Legend
towers, other modes, hero skins, fresh computer setup and iPads remain unverified.

## Automated validation

- The v2 EXE was tested on a disposable copy extracted from the official Windows
  12.13.0 installer: install, shared Python 3.13 imports without lzfse, restoration,
  and restoration of the older v1 preview. All 10,827 payload files were verified;
  all 39 original dependency versions were preserved. Restoration matched 5,941
  original files byte-for-byte (excluding regenerable Python caches), preserved
  the test settings, and removed every newly added payload file.
  The full v1-to-v2 upgrade also passed. After upgrading, the installed backend
  captured three AFK Journey frames from the test iPhone in 0.69–0.84 seconds each.
  A final restore returned the disposable app to stock. The user's main installed
  app was not modified by these installer tests.
- 11 installer regression tests passed, including failed-write recovery, corrupt
  backups, later app changes, and legacy restoration with an isolated module path.
- 105 focused device/layout/navigation/battle/Union Campaign and installer tests passed.
- 159 AFK mixin tests passed in the broader suite (some overlap with the focused suite).
- 63 iOS-specific tests passed in the actual isolated Python 3.13 environment, including
  the locked-device input guard and uniform hero matching.
- Set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for this environment: pymobiledevice3's xonsh
  dependency registers a pytest plugin that otherwise tries to open a Windows console.
- The new iOS compatibility workflow reproduces package installation and regression
  tests on Windows/Python 3.13 without needing a physical phone.

## Tester request

Start with Face ID iPhones 12–17 in English portrait. Their similar aspect ratios
make them useful first candidates, not guaranteed supported devices. Include model,
iOS version, native screenshot size, mode and the failed action in reports. Use
Capture Debug Screenshot and review the images for account/chat details before
sharing. Do not send device-cache directories or pairing records.

SE and iPad layouts require separate game-layout validation. Geometry tests cover
their aspect ratios and inverse taps, but passing those tests does not validate the
positions/appearance of game controls on real devices. A different viewport alone
cannot correct a game UI that rearranges itself.

## M1 iPad connection check (2026-11-01)

Physical device: `iPad13,16`, iPadOS 18.0.1, English portrait, 1640 x 2360.
Developer Mode was enabled. Initially the developer disk image was not mounted,
so CoreDevice screenshot and input services were absent. Mounting the developer
image with the existing Python 3.11 setup tools exposed those services, and the
Python 3.13 backend captured an AFK Journey screenshot. The fitted viewport was
x=0, y=183, width=1080, height=1554.

The first attempted tap failed before any touch report was sent: Apple's media
stream service returned CoreDevice error 9021, "Remote control requires iOS 27.0
or later on this device." Thus successful capture does not establish remote-input
compatibility. No navigation, formation copy, battle, or victory was validated on
this iPad. An OS update and another live input test are needed before layout and
battle validation can continue; do not describe this device as supported yet.

The source now gives this OS restriction its own error, including model and OS,
and shares the same session-opening path between taps and swipes. It preserves
unrelated CoreDevice failures and still checks screen lock before using an existing
input session. Three new regression tests cover those cases. The connection,
settings, and review suite passed all 32 tests. These source changes have not yet
been packaged into a new installer.

The developer-image setup used above remains a separate setup step: the shipped
Python 3.13 environment excludes lzfse and cannot import the image-mounter module.
The successful screenshot therefore does not validate automatic developer-image
setup on a fresh computer or after the device restarts.

## M1 iPad follow-up on iPadOS 27.2 (2026-11-01)

The same iPad was updated to 27.2. USB screenshot capture and remote taps worked
after loading Apple developer support. The tablet now selects its own measured
image profile by model, with viewport-relative regions and undistorted templates.
The iPhone profile remains separate. Unsupported tablet controls do not fall back
to Android or phone images. Existing menu items, settings files, retries and battle
handlers remain shared.

Live checks through the original engine:

- Battle Modes > AFK Stage, formation selection and Records formation copy.
- Ordinary AFK battle victory, followed by Next opening the following formation
  screen. Recognition assets contain no stage numbers.
- Season/Phantimal selection, Records copy, battle start, defeat detection
  and Retry returning to formation setup. No seasonal victory was observed.
- Back navigation and native/logical coordinate mapping at 1640 x 2360.
- Original navigation engine returned to the world and re-entered AFK Stages
  through Battle Modes; ordinary AFK entry handled the daily-limit confirmation.
- Offline hero matching recognized Mehira in the captured Records row. This is not
  exhaustive exclusion coverage; other heroes/skins and manual-formation filtering
  remain unverified on the tablet.

Dependency status changed since the October review: lzfse 0.4.2.post1 now has an
official CPython 3.13 Windows x64 wheel on PyPI (released October 16). The iOS extra
and override now pin that wheel instead of excluding lzfse. Automatic developer
support loading runs through the same Python 3.13 runtime and RSD tunnel; no second
Python runtime is installed. A physical test unloaded only the temporary developer
image, used an empty cache, then passed automatic image loading, screenshot capture
and input authorization. A closed setup reply is checked against the resulting
service state before reporting failure; image installation is not blindly replayed.

Current scope: experimental M1 iPad Air AFK progression. Seasonal victory/Next,
manual formation labels, full hero/skin coverage, Dura, Legend and other modes need
separate tablet validation. Other iPad models and aspect ratios remain unverified.
The maintainer's separate installer/update feeds and removal of IOSLayoutMixin
remain follow-up work; this change does not claim to complete that upstream review.

Validation: 134 focused tablet/phone, navigation, battle and installer tests passed.
The normal Python wheel build includes the tablet manifest and image files.
Public tests construct synthetic black canvases from independently measured button
positions. No device screenshots, account names, chat, or player avatars are added
to the repository. The 18 tablet image assets contain only generic UI labels and
button icons.
The v4 installer upgrade/restore test verified all 10,871 installed payload files
and recovered all 5,990 original disposable-app files, including legacy additions
and settings, byte-for-byte.

## Installed 12.13.7 integration (2026-11-01)

The real app had auto-updated to 12.13.7 while retaining the older add-on marker.
The 12.13.0 restore guard correctly refused to overwrite changed files. Upstream
tag 12.13.7 was merged instead. Its resumed-app and installed-package discovery
methods are implemented by the Apple controller, and shared lifecycle lookups use
the mapped bundle identifiers. Android retains upstream's multi-display behavior.

A local overlay audited all 108 target files against upstream tag 12.13.7, the
recorded previous add-on hashes, or the new payload; no unknown modifications were
accepted. It preserved the 12.13.7 executable and bundled Python, archived the stale
marker, and created a new format-2 rollback journal and per-file backups. Both
profile settings files remained byte-for-byte unchanged. The installed app's own
Python then passed screenshot capture and tablet Records/Battle recognition.

The merged source passed 137 targeted iOS/navigation/battle, startup-interface and
installer recovery tests after updating the version-specific error assertion. A live
12.13.7 startup test discovered and launched the real iOS game bundle successfully.
The older 12.13.0 v4 EXE remains a tested artifact of its own source revision; it
must not be used on 12.13.7. The current installer build configuration targets
12.13.7, but a public installer for that version has not yet been built and released.
