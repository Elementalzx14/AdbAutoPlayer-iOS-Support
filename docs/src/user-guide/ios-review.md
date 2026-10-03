# iOS maintainer review — 2026-10-03

This branch builds on upstream 12.13.0 and retains the original game menu and settings.
The existing downloadable `v12.13.0-ios.1` installer predates this review. It has not
been replaced by these source changes.

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
