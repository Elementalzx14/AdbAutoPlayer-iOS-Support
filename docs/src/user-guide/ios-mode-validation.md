# Apple mode validation — work in progress

Source base: upstream **12.13.7**. Test device: M1 iPad Air (`iPad13,16`),
iPadOS 27.2, English portrait, 1640 × 2360 native pixels. These changes are
under development; they have not been packaged into a new public installer.
This report distinguishes shared code support from completed live tests.

## Shared implementation

- The existing commands, task settings, formations, attempts, exclusions, and
  custom-routine engine remain in use. No settings pages are replaced.
- Apple recognition is composed into `AppleLayout`, rather than inherited as
  a front-of-MRO game mixin. Android keeps its original layout policy.
- Fixed UI points are explicitly marked `ReferencePoint`; the input layer
  projects them into the visible viewport. Template/OCR results stay in
  screenshot coordinates. Fixed swipes have the same explicit distinction.
- Verified iPad image profiles take precedence. Other original assets can be
  searched with uniform scale variants, a minimum 92% score, caller crop
  constraints, and rejection of dimmed controls. This fallback is not proof
  that an untested task works. Repeated-control searches use the same policy.
- The worker can consume continuous local USB HEVC video instead of requesting
  a PNG for each frame. It reuses the pinned pymobiledevice3 RTP/recovery
  implementation without opening a VNC/HTTP server, audio, or clipboard.
  HID shares the active media authorization session.
- Decoder input and pending frame delivery are bounded. Reads require a newly
  decoded frame. Geometry changes or stream failures return to native screenshot
  capture; input is never replayed. Debug captures still save a matching native
  PNG and normalized BMP from one capture.
- The M1 iPad prototype decoded approximately 60 fps after removing conversion
  of every incoming frame to BGRA. Integrated game reads measured approximately
  30–50 ms per fresh normalized frame. These are local observations, not a
  guarantee for other hardware or every game screen.
- A 36-second live keepalive test retained video for every read. Closing the
  local media receiver then produced a clear fallback warning, released the
  old HID session, captured a native screenshot, and re-established touch
  authorization without sending a tap. This simulates receiver failure; it
  does not replace physical unplug/lock testing of the new streaming path.
- The input benchmark skips off-screen test taps on controllers that reject
  them. It explicitly reports that input latency was not measured.
- Reaction-based tasks require the video path and stop if it falls back to
  screenshots, including mid-task. Normal battle tasks can continue using
  fresh screenshots. This prevents treating slow fallback as a usable fishing
  or matching-card input loop.
- Held input now leaves capture requests available. A live 0.8-second hold
  on an unused header allowed 22 fresh captures during the contact and released
  afterward. A worker deadline also releases the contact if a capture stalls;
  cancellation replies are identified so they cannot acknowledge a later input.
  This validates transport concurrency, not fishing gameplay or reaction timing.

## Coverage inventory

| Existing task | M1 iPad evidence / remaining work |
| --- | --- |
| AFK Stages | Previously verified entry through Battle Modes, Records, copy, battle, victory and progression; image regressions retained. Repeat full flow with the new video path before release. |
| Season AFK Stages | Previously verified entry, Records/copy, battle, defeat/retry. Seasonal victory/progression still needs a live test. |
| Season Legend Trial | Original Lightbearer selection, challenge, formation copy, battle, victory, and advancement to the next floor's formation verified. Other factions were closed; their unavailable icons and tower labels have recognition coverage. |
| Dura's Trials | Original navigation and already-cleared stop verified. No active entries were available. **No Sweep was pressed and no sweep tokens were used.** Active battle/progression remains unverified. |
| Dream Realm | Original menu entry and daily-completion stop verified without starting a battle or purchasing attempts. The daily marker matched at about 95% and the original policy returned stop. Exhaustion, battle/skip, rewards and purchase-policy paths remain unverified live. |
| Arena | One original opponent-selection, Battle, Skip and completion flow verified using one existing attempt. Purchases and Sweep were blocked. Exhaustion/free-attempt claiming remains unverified live. |
| Supreme Arena | Off Season observed; active-season flow remains unverified. |
| Arcane Labyrinth | Original navigation reached an existing run's gate screen without choosing a gate or starting a new run. Both gate controls matched original assets at approximately 99% through the shared repeated-control search. Gate selection, battles and rewards still need validation. |
| Union Campaign | Original menu entry, formation copy, Battle, defeat and Retry returning to formation verified. No Sweep was pressed. Victory/progression remains unverified. |
| Ravaged Realm | Shared layout work applies; full event flow still needs validation. |
| Frostfire Showdown | Fixed inputs/swipes marked for viewport projection; full event flow still needs validation. |
| Sunlit Showdown | Fixed inputs/swipes marked for viewport projection; full event flow still needs validation. |
| Titan Reaver Proxy Battle | Fixed swipe marked for viewport projection; full event flow still needs validation. |
| Dailies | Fixed inputs and repeated-control matching adapted. Individual settings, OCR regions, rewards and purchase/exhaustion paths still need validation. Sweeps and purchases are not used for live smoke tests. |
| Run Quests | Fixed inputs adapted; quest-specific navigation/OCR still needs validation. |
| Assist Synergy & CC | Read-only chat opening and World channel selection verified. Difference-based profile search now shares uniform scaling/crop offsets; actual assistance navigation and battles remain unverified. No chat messages or requests are sent during testing. |
| Homestead Orders Helper | Fixed inputs/swipes adapted; OCR, order/crafting geometry and resource policies still need validation. |
| Guild Manager Scan | Fixed scrolling adapted; OCR and rankings/activeness layouts still need validation. No member exports or reports are published during testing. |
| Hero Scanner | Fixed inputs adapted; roster/filter/scanning geometry still needs validation. Hero/skin exclusion recognition is not exhaustively verified. |
| Fishing | Video transport and off-screen benchmark issue addressed; fishing regions, reaction timing and catch handling still need live validation. |
| Matching Cards | Fixed tap and crop boxes project through the layout policy; board-size/target matching still needs live validation. |
| Start Game | Existing Apple launch and shared Android lifecycle regressions retained. |
| Custom Routine / 2 / 3 | Original settings/dispatch retained; a routine inherits the verification limits of its selected tasks. |
| Capture Debug Screenshot | Captured native PNG, normalized BMP and 48 template reports while video was active. Re-rendering the native PNG produced exactly the saved normalized pixels. No screenshots are uploaded automatically. |

The goal remains all existing modes. A passing synthetic-image test, successful
menu entry, or shared fallback must not be described as completion of that goal.
Unavailable events, exhausted entries, and closed factions remain explicit gaps.
Full-frame device captures stay local. Only reviewed generic control crops belong
in the repository.
