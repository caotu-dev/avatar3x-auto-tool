# Inventory, tickets and wallet preparation

Implemented in the primary release: `dist/AvatarFishingBot/AvatarFishingBot.exe`.

## Behavior

- Every Start prepares the selected task's area before fishing. Ecological ponds
  return to the ecological center; dock tasks navigate to the dock.
- A progress popup shows current preparation work and lets the user cancel.
  Duplicate Start and Pause are disabled during preparation. The session timer starts
  after the first successful preparation. A complete chest scan runs once per Start. Area changes and reconnection reuse
  the session cache; a new Start obtains fresh observations.
- MENU → basket opens the chest. A bounded scan verifies the top, examines full
  overlapping rows, handles selected white slots, and verifies a stable bottom.
  Selected item details and stack counts are read twice. Verified ticket sprites
  remain active even if their date is unreadable. Unreadable quantities remain
  unknown. Incomplete scans never prove absence.
- Four ticket cards show possession/validity and the observed expiry date.
  An observed ticket is active, including its expiry day: expired tickets disappear
  from the chest. The displayed date does not cause a replacement purchase.
- Ecological Mồi Trùng and dock Mồi Câu Cá Trâm are separate stock observations.
  Preparation buys required bait if zero, regardless of the existing in-session refill
  checkbox; that checkbox continues to govern later refill after game reports no bait.
- Four ticket auto-buy checkboxes default off and persist with Save/Cancel semantics:
  perch 1,000 xu, snakehead 10,000 xu, shark 2 spendable lượng, dock 12,000 xu.
  Only the required area's ticket is purchased, in its appropriate shop.
  A complete Start observation is passed to the purchase guard; active tickets skip
  payment. Direct callers without a cache obtain one scan themselves.
- Xu and lượng are located from currency glyphs and read twice outside
  obscuring dialogs. The external HUD can combine spendable and locked gold;
  before buying a ticket the shop balance is read again, using separate locked-gold
  glyphs to delimit spendable currency. Malformed large xu
  readings with missing thousands separators are rejected.
- Purchases validate currency, product, price, payment control and receipt; confirmed
  receipts update and persist possession, quantities and money before popup cleanup.
  No second full chest scan is performed after purchases. Insufficient money or unknown
  inventory stops preparation. An ambiguous submitted purchase remains pending across
  launches to avoid duplicate charges. No invented remaining hours are displayed.

## Modified code and assets

- `gui.py`: money display, actual ticket statuses, preparation popup/timer/control state.
- `ui/settings_dialog.py`: four draft ticket settings with Save/Cancel and running lock.
- `ui/runner.py`: preparation before area entry, inventory integration, funds checks,
  purchase events and preparation-aware timer.
- `fishing/inventory.py`: new chest scanning, item/expiry/quantity/wallet recognition,
  guarded ticket purchases and dock-bait purchase path.
- `vision/windows_ocr.ps1`, `fishing/quest.py`: optional positioned OCR for identifying
  the gold payment button; the existing quest OCR result format is preserved.
- `vision/templates/inventory/`: real game sprites from supplied images/existing fixtures.
- `tests/test_inventory.py`, `tests/test_ui_updates.py`, `tests/fixtures/inventory/`:
  parser, safety, preparation, UI and grid-scanning acceptance coverage.
- `fishing/detector.py`, `fishing/dock.py`, `fishing/navigation.py`,
  `fishing/travel.py`, `fishing/session.py`, `fishing/rooms.py`: verified dock routes,
  daytime scenes, boats, timer, popup dismissal and room switching.
- `fishing/catch.py`, `fishing/quest.py`, `ui/assets/fish_*.png`,
  `vision/templates/fish/`, dock/navigation templates and fixtures: four observed
  dock species and real daytime visual references.
- `ui/fish_catalog.py`: compact row images and checkbox padding for thirteen rows.
- `tests/test_dock.py`, `tests/test_world.py`, `tests/test_quest.py`: dock detection,
  all catalog name recognition and updated dock quest routing.
- `README.md`, this report and local UI capture/validation artifacts.

Fishing solver, quest OCR parsing, pond geometry and ecological room/sale behavior
are preserved. Dock scene/control recognition is extended from live captures;
the existing solver is reused. The UI accepts a verified READY dock state.

## Validation

- Full suite and final targeted results are saved in `validation/tests-live.txt` and
  `validation/tests-cache-reconnect-final.txt`;, including real daytime dock states, name recognition,
  ticket possession, purchase guards, inventory scanning and unchanged pond fixtures.
  See `validation/tests-live.txt`. The final catalog-spacing adjustment additionally
  passed the GUI/preparation tests in `validation/tests-ui-final.txt`.
- Live full character chest scan confirmed existing snakehead and dock tickets.
  A direct dock-ticket purchase request rescanned the chest and skipped payment.
- Live dock navigation, boat selection, the existing fishing solver, success dismissal,
  and two purchases of exactly 50 dock bait have been exercised. Each purchase cost
  2,500 xu. The external gold total stayed 264; the shop separately showed 260 spendable and 4 locked.
- Four dock fish were established from actual success popups: Cá vàng, Cá chép,
  Cá hề, Cá lia thia. Their names, area routing, templates and UI icons were added.
  This is the observed catalog, not a claim that every possible dock fish was sampled.
- The live fishing harness durably counts each verified cast before sending it and
  refuses cast 101 or a third bait purchase. See `validation/live-results.json` for
  current/final audited results and preserved per-round screenshots.
- Stocks are reconciled from chest observations rather than assuming every cast
  consumes bait. After the second purchase the chest showed **62**, not the estimate 50.
- UI snapshots use isolated preferences and actual saved observations, with no worker.
  All thirteen fish rows are visible at 1536×960 without internal catalog scrolling.
  Smaller windows can scroll the whole workspace. Settings has extra ticket controls
  and scrolls when needed; Save/Cancel behavior is retained.

## Limits

The reader is calibrated for Android **1600×900**. Tickets expose an expiry date,
not an exact expiry hour, so the UI displays the date rather than inventing hours.
Some live rounds showed only Xong without reliable success/failure evidence; these
remain RESULT/unknown and never inflate confirmed catches or the miss metric.
The live sample does not establish an exhaustive dock fish list. Gold ticket payment
and the overnight dock sell/return schedule have not been exercised in this daytime
session. These guarded paths retain unknown/error states when evidence is incomplete.

The primary EXE was rebuilt; `--ui-check` and `--smoke-test` both exited **0**.
The final build compares current runtime files against `validation/runtime-final-before.json`;
  these include the user's latest settings/progress, preserved across the update.
See `validation/exe-live-check.json` and `validation/build-live.txt`.

The bounded live test completed **exactly 100 casts**, across resumed batches:
**51 confirmed catches**, **49 unclassified results**, no claimed confirmed misses.
Confirmed fish: Cá vàng **11**, Cá chép **15**, Cá hề **18**, Cá lia thia **7**.
One dropped Xong transition stopped the session safely at 95; inspection and resume
completed the final five casts without resetting the ledger or buying again.
The final full chest showed dock bait **23**, ecological bait **0**, wallet
**1,609,861 xu / 264 lượng**, snakehead ticket expiry **13-10-2026** and dock ticket
expiry **16-10-2026**. Total bait spend: **5,000 xu**, exactly two purchases of 50.

The missing perch-ticket purchase was confirmed by its receipt and a fresh full
chest scan: **active, expiry 14-10-2026**. A second direct purchase request skipped
payment after finding it owned. Final wallet: **1,608,861 xu**, external total
**264 lượng**; shop observation: **260 spendable + 4 locked**. Total test spending:
**6,000 xu**, zero gold. No shark, snakehead or replacement dock ticket was bought.
The UI shows the observed external balance; ticket payments recheck the shop's
spendable amount before the Buy button and final payment.

## Follow-up: one scan per Start and lost-session recovery

- The reported 14:32:46 recovery tap was correctly located, but the button stayed
  visible. The old recovery waited only for a world map and never retried. Its error
  diagnostic then raised SessionLost again while reading the login screenshot,
  leaving the worker's final status RUNNING. Diagnostic handling and terminal status
  were fixed; recovery failure now emits ERROR.
- Continue retries require fresh stable logo/button recognition, wait at least
  three seconds, stop after three attempts, and never send input during loading.
  Recovery accepts a verified world map or a known game area; Stop remains honored.
- A live test intentionally dropped the first Continue tap. The second request sent
  one actual tap, returned to the world map, kept the inventory cache/progress and
  restored session guarding. No cast or payment was sent. See
  `validation/live-recovery.json` and `screenshots/reconnect-before.png` / `reconnect-after.png`.
- A second live test prepared perch and snakehead with **one full chest scan**,
  purchases/casts forbidden by the test device. See `validation/live-cache.json`.
  Its inventory reflects the user's later game state, separate from the earlier
  bounded 100-cast audit.
- Successful ticket/bait receipts are persisted before closing dialogs, so a
  disconnect during cleanup does not cause another purchase. Pending/unconfirmed
  payments still stop rather than guessing success.
- Bait tracked after casts is labelled **≈**, and an estimated zero does not trigger
  a purchase. The game's actual OUT_OF_BAIT state governs in-session refills.
- Files additionally changed: `fishing/reconnect.py`, `ui/runner.py`,
  `fishing/inventory.py`, `gui.py`, `tests/test_reconnect.py`, inventory tests,
  real recovery fixtures, README and this report.

Cache is scoped to one Start. If inventory is changed manually during a running
session, Stop and Start again obtains fresh chest observations.

Final release checks: UI and smoke diagnostics exited 0; all **8** current runtime
files retained their hashes. The redundant build staging directory was removed after
checking its EXE matched the primary release. Audit screenshots and logs are retained.

### Login cooldown follow-up

Reproduced through World map → Menu → Thoát → Chơi tiếp. The real modal reads
“Đăng nhập lại sau: 14 giây nữa”. Added a template for its static label, excluding
the changing seconds. Session-loss recognition remains active while the modal
obscures login. Recovery sends no taps until it disappears and the Continue button
is recognized in two fresh frames. Waiting does not consume attempts; Stop remains
available, with the existing 45-second total timeout and three-tap limit.

Live recovery completed in 19.41 seconds, observing 15 blocked frames and sending
three verified Continue taps, none during the modal. No purchases or fishing casts
were sent. Evidence: `validation/live-countdown.json` and
`screenshots/reconnect-countdown.png`. Added three regression tests for recognition,
a 15-second wait without consuming retries, and cancellation while blocked.
Modified `fishing/reconnect.py`, `ui/runner.py`, `tests/test_reconnect.py`, template
and real screenshot fixture. Rebuilt the primary EXE; UI/smoke checks both exited 0
and all current runtime files retained their hashes.
Full regression suite: **193 tests passed** in 90.375 seconds; see
`validation/tests-countdown.txt`.

### ADB screenshot timeout follow-up

The supplied round_0097 report records a 15-second `exec-out screencap -p`
timeout before any cast in that round. `AdbDevice.screenshot` now retries this
read twice, returning a newly decoded frame and refreshing its resolution cache.
Each attempt retains the 15-second limit, with a half-second delay between retries.
The GUI logs retry progress and checks Stop before/after each attempt. Persistent
timeouts stop with an explicit three-attempt error. Input commands are never retried;
offline/missing-device errors still stop immediately. Existing session/inventory
state is preserved. Files: `adb/device.py`, `ui/runner.py`, `tests/test_adb.py`.

Five regression cases cover recovered timeout, bounded repeated timeout, Stop after
timeout, no repeated payment input, and immediate offline failure. All 11 focused
ADB tests pass. Live verification could not obtain a frame because the emulator
was disconnected (`device emulator-5554 not found`); no game inputs were sent.
Full suite: **198 tests passed** in 72.068 seconds (`validation/tests-adb-timeout.txt`).
Primary EXE rebuilt; UI/smoke diagnostics exit 0 and runtime hashes remain unchanged.

### Slow post-catch confirmation follow-up

The user's 21:02 crab catch was correctly recorded and its popup dismissed. The
first FINISH observation arrived about four seconds after the dismiss tap; the
six-second confirmation deadline expired before the second observation. The real
error image contains a valid Xong button, classified RESULT with a confirmed scene.
Post-round cleanup now allows at least 12 seconds per transition (48-second total
bound), retaining two-frame verification and one tap per dismiss/finish step. Initial
entry timing and fishing solver/automation logic remain unchanged.

Changed `fishing/session.py` and `tests/test_session.py`. New slow-capture regression
covers delayed popup disappearance, confirmed finish, and READY without another
cast. All 24 focused session tests passed. Live cleanup on the actual failed screen
clicked Xong once and reached READY in 3.2 seconds; zero casts/purchases. Evidence:
`validation/live-slow-finish.json`, `debug/slow-finish-live/events.jsonl`.
Full regression suite: **204 tests passed** in 111.775 seconds. Primary EXE rebuilt;
UI/smoke diagnostics exit 0 and runtime hashes remain unchanged.

### Shop entrance hidden by players after selling

The user report's error image shows players covering the entrance arrow and the
bottom of the SHOP lettering. The original full lettering template failed, so
opening the shop again after selling timed out. `WorldDetector.match(shop_sign)`
now falls back to the static upper 65% of the lettering at the same strict .98
threshold, restoring the full template geometry for the existing interaction
point. Opening the shop does not depend on the hidden arrow. `open_shop` confirms
fresh sign frames, retries a dropped open up to three times, and verifies the menu
before returning; these retries never perform sales or payments.

Changed `fishing/world.py`, `fishing/travel.py`, world/travel regression tests, and
added the actual occluded entrance fixture. Tests cover recognition/location on the
reported image and a dropped open without any payment. Live test opened the actual
shop menu at (1011,425), confirmed it and closed it afterward. No sale, purchase or
cast was sent. Evidence: `validation/live-occluded-shop.json`, `debug/occluded-shop-live/`.
Full suite: **218 tests passed** in 130.059 seconds. Primary EXE rebuilt;
UI/smoke diagnostics exit 0 and runtime hashes remain unchanged.

### Continue auto after uncertain in-round recognition

The user requested recognition failures during fishing to keep auto running.
Round_0054 had one confirmed drag followed by a changed source/target signature.
The old bot ended the session immediately. Added a GUI-enabled recovery mode:
after a cast, recognition-related STOPPED/TIMEOUT outcomes enter observation-only
recovery. No uncertain drag plan or new cast is sent. The bot waits for verified
SUCCESS, RESULT/FAILED, OUT_OF_BAIT or two confirmed READY frames. Result/finish
cleanup resumes the next round normally; an already-reset READY round is recorded
ABORTED with its original cast count and as unclassified, without inventing fish.
Verified exit questions can still be dismissed with Không once per visible popup.

While the screen remains unknown, the session stays alive with a status log every
30 seconds; Dừng remains honored on each device read. Actual device errors and
purchase validation errors still stop, and standalone diagnostic runs retain their
old bounded behavior. This mode does not blindly send inputs to unknown screens.

Changed `fishing/bot.py`, `fishing/session.py`, `ui/runner.py` and related tests.
Regressions cover changed plan after a confirmed drag, unknown→result, unknown→READY,
user Stop during recovery, and the session completing its abandoned round.
Live test replayed two recorded uncertain-board frames, observed actual RESULT,
clicked Xong once and confirmed READY. No additional casts/purchases. Evidence:
`validation/live-auto-recovery.json`, `debug/auto-recovery-live/`.
Full suite: **216 tests passed** in 82.660 seconds. Primary EXE rebuilt;
UI/smoke diagnostics exit 0 and runtime hashes remain unchanged.

### Own avatar obscuring snakehead entrance

The 21:23:10 report shows the center's right exit covered by the user's avatar
wings. Three camera pans could not reveal an arrow hidden by that avatar. Real
test moved onto clear pavement at (1300,710), exposing the exit at (1535,609),
then entered verified ca_noc at its freshly detected arrow (1535,603). No cast or
purchase was sent.

After a failed pan, entry now verifies the center and an empty stone-pavement patch
before moving away from the exit; it then searches again for the actual arrow.
Unknown maps or occupied/non-pavement patches permit no movement. Also fixed the
loop boundary: an arrow found after the third pan is used immediately. Existing
three-pan limit and map confirmation remain. Changed `fishing/travel.py`,
`tests/test_travel.py`, and added real blocked/uncovered center fixtures.
Regression tests cover the real occlusion, no movement on unknown maps, and a
successful last-pan discovery. Evidence: `validation/live-entry-recovery.json`.
Full suite: **211 tests passed** in 99.552 seconds. Primary EXE rebuilt;
UI/smoke diagnostics exit 0 and runtime hashes remain unchanged.

### Xin chờ → random exit confirmation

The user's round_0005 briefly reached FISHING then showed the real “Xin chờ” modal.
It was classified UNKNOWN and hit the three-second post-bite unknown limit before
the exit question appeared. Added explicit LOADING recognition from the modal's
static label, separate from unknown screens and its animated spinner. Mid-round
loading waits without input for up to 30 seconds, within the existing round limit.
The existing two-frame EXIT_CONFIRM recognition then clicks only the verified
Không button; its closure has a 12-second bound and no repeated click.

If Không returns WAITING/FISHING, tracking continues. If it returns confirmed READY
before any drag, one bounded recast is allowed even if a brief bite frame preceded
the loading; a second popup cannot cause endless recasts. No solver actions are
sent while loading or inside the exit modal. Session cleanup also recognizes loading.

Changes: `fishing/states.py`, `fishing/detector.py`, `fishing/bot.py`,
`fishing/session.py`, `vision/templates/loading_vi.png`, actual loading/exit fixtures
and regression tests. Focused bot suite: 26 passed. Regressions cover loading after
a bite, waiting through it without input, cancellation of the exit, bounded loading,
and a recast only after two verified READY observations.

Live test replayed three actual loading screenshots before the real exit popup,
clicked Không at (958,557) once and confirmed the game resumed WAITING. Zero casts
or purchases. The cleanup-only helper did not return READY because the game was
still waiting for its existing fish; the actual mid-round loop handles that state.
Evidence: `validation/live-loading-exit.json`, `debug/loading-exit-live/events.jsonl`.
Full suite: **208 tests passed** in 106.583 seconds. Primary EXE rebuilt;
UI/smoke diagnostics exit 0 and runtime hashes remain unchanged.

### Initial chest selection follow-up

The 19:20:32 user report reached the bottom but failed to confirm the selection
border for its first snakehead-ticket tap. Other tickets/bait were read. That single
unconfirmed cell invalidated the entire scan. Selection now polls for the amber
border and retries the same slot up to three times, verifying the chest title each
time. A fingerprint is marked visited only after selection succeeds; unconfirmed
cells still prevent missing-item conclusions or purchases.

Real-game test intentionally dropped the first item tap. Recovery read the snakehead
ticket (expires 2026-10-13), completed the full scan, found three active tickets,
8 ecological bait, zero dock bait and wallet 1,642,471 xu / 264 gold. No purchase or
cast was sent. Evidence: `validation/live-chest-selection.json` and
`screenshots/chest-selection-recovered.png`. Changed `fishing/inventory.py` and
`tests/test_inventory.py`; two regression cases verify dropped-tap recovery and
bounded failure. All 28 inventory tests passed.
Full suite: **200 tests passed** in 91.493 seconds. Primary EXE rebuilt; UI/smoke
checks exit 0 and current runtime hashes remain unchanged.

### Snakehead room camera follow-up

User round_0011 had crowded chairs. Rooms 12/11/6 then showed a pier shifted
into the center of the viewport, with visible unoccupied seats. The fixed chair
ROIs still searched the original right-edge positions and missed these seats.
For ca_noc, chair search regions now follow the recognized KHU sign, covering both
sides and three rows. The original strict chair-template threshold, pond/scene
checks, stable-frame requirement and three-room limit remain. Crops outside the
viewport are excluded; absent signs retain the existing fixed regions.

Real test on the same room 6 view entered the verified chair at (653,679) and
confirmed READY/Quăng câu. Zero casts/purchases were sent. Evidence:
`validation/live-shifted-seat.json`, `screenshots/shifted-seat-ready.png`.
Changed `fishing/detector.py`, `tests/test_world.py` and added the actual shifted
room regression fixture `tests/fixtures/puffer_shifted_room.png`.
Full suite: **201 tests passed** in 86.624 seconds. Primary EXE rebuilt; UI/smoke
checks exit 0 and runtime files remain unchanged.

### Return-to-center camera follow-up

The 19:46:29 user error screenshot shows the snakehead middle pier after leaving
the chair, with no exit arrow visible. `TravelController.center` now pans toward
the appropriate map edge for perch/snakehead (up to five swipes), verifying the
current area before each swipe. It taps only a detected exit arrow confirmed across
fresh frames, tolerating arrow animation. Missing arrows still stop without an
exit tap. Files: `fishing/travel.py`, `tests/test_travel.py`.

Live test from the user's actual failed position needed one pan, detected the
left exit at (12,597), and returned to verified center. No casts/purchases.
Evidence: `validation/live-return-center.json`, `debug/return-center-live/events.jsonl`.
Ten focused travel tests passed, including new successful-pan and bounded-failure
regression cases.
Primary EXE rebuilt; UI/smoke diagnostics exit 0 and runtime hashes remain unchanged.


### Shark ticket purchase confirmation OCR (2026-10-11)

The real confirmation OCR misread Cá Mập as Cé M$p and lượng as luqng, preventing payment. Added observed exact product/price lettering, independent 2-gold price, quantity-one and Mua lượng button templates. The receipt also supports exact product lettering while still requiring OCR success. Existing complete-scan, owned-ticket skip, spendable-funds, pending-payment and receipt persistence safeguards remain.

Live validation scanned the full chest once, found ca_map missing, bought exactly one ticket for 2 spendable gold (260 → 258), confirmed the receipt and updated the cache without rescanning. No fishing casts or bait purchases. Expiration was not included in the receipt; remains unknown until the next normal start scan. Evidence: validation/live-shark/before.json, after.json, events.jsonl, after.png and ticket_receipt.png.

Validation: 221 full-suite tests passed; final focused inventory suite 31 passed; packaged --ui-check and --smoke-test returned 0; runtime hashes unchanged after build (0 changed files). Primary exe updated in dist/AvatarFishingBot.


### Dropped finish acknowledgement (2026-10-12)

The reported ca_map round 0009 dismissed the catch popup and sent Xong once, but its final screenshot still contained a verified RESULT and the same Xong button. Automatic post-round cleanup now allows at most three finish taps, at least three seconds apart, with two fresh confirmed result observations and unchanged button coordinates before a retry. It stops immediately at verified READY and never casts during cleanup. Standalone diagnostics retain single-tap behavior.

Modified fishing/session.py, tests/test_session.py and added tests/fixtures/shark_finish_stalled.png. Focused suite: 28 tests passed, including dropped first input, bounded all-input failure and recognition of the actual reported screenshot. Live game had already returned READY; verified two fresh frames with a device wrapper forbidding all inputs (zero casts/purchases). Actual dropped-input recovery was simulated, not reproduced live. Packaged UI/smoke checks both returned 0; runtime hashes unchanged.

Full regression suite: 224 tests passed. Updated primary exe: dist/AvatarFishingBot/AvatarFishingBot.exe.


### Shark-area no-bait navigation (2026-10-12)

The reported round_0034 correctly detected OUT_OF_BAIT, but navigation subsequently waited for an outside map with the bait dialog still visible. leave_chair now checks freshly observed no-bait dialogs during its outside-map wait and performs one bounded re-entry through the existing verified OK/seat-close flow. Added the observed hamburger-menu variant to WorldDetector so the outside map remains recognizable. No purchase or cast retries were added.

Modified fishing/travel.py, fishing/world.py, tests/test_travel.py; added the reported shark popup fixture and menu_hamburger template. Live test closed OK, left the seat, clicked the verified center arrow, opened the center shop, and closed its menu: zero purchases/casts. Evidence: validation/live-shark-refill/events.jsonl, shop-open.png, result.json.

Validation: 16 focused travel tests and 226 full regression tests passed. Packaged UI/smoke checks returned 0; runtime files unchanged after build. Primary exe updated.


### Long-run OpenCV allocation failure (2026-10-12)

The overnight session stopped around 01:41 after round 86, with OpenCV unable to allocate 9,257,808 bytes while the game was still waiting for a catch. Historical logs do not distinguish system memory pressure from application growth. Reduced transient allocations: template matching now computes strips of at most 96 response rows with overlap, preserving all candidate placements and global best match; replaced np.std full-image float64 temporaries with pooled cv2.meanStdDev channel statistics. Persistent solver refinement cache is limited to 20 entries (under 8 MB even for precise variants). No fishing inputs or purchase logic changed.

Modified vision/matcher.py and fishing/solver.py; added tests/test_matcher_memory.py. Regression compares full OpenCV response versus strips in gray/color and both matching modes, checks response size <=614,400 bytes on 1600x900, and fills refinement cache across 24 angles to verify fixed bounds. Replayed 100 observations from actual overnight error_screen.png and recorded process private memory in validation/memory-replay.json; this is not an overnight live soak.

Small repeated anchors retain the original whole-response tie behavior (<=20 high and <=64 wide). OpenCV is limited to one native thread for the sequential bot worker. Final 100-frame replay private-memory change: +360448 bytes (~0.34 MiB); no allocation errors. This is a short replay, not proof of overnight stability.

Final validation: 229 regression tests passed under final single-thread configuration; packaged --ui-check and --smoke-test returned 0; runtime files unchanged. Primary exe rebuilt.


### Dashboard layout and bounded automatic restart (2026-10-12)

Moved the three fishing modes and full fish selection catalog into a modal opened by Chọn nhiệm vụ, with draft Save/Cancel semantics. Dashboard columns remain 35%/40%/25%: overview and ticket cards on the left, fish progress and target actions in the middle, activity on the right. Money is now on the navbar with currency icons; all four tickets have observed game icons. Settings footer Save/Cancel stays visible outside its scrolling content.

Custom-mode progress rows support arrow buttons and drag ordering. The persisted custom plan drives execution order, and reordering the same species/quantities preserves saved counts. Game quests and free fishing cannot be reordered. Misses now equal max(0, casts - bites). Currency reading still requires two agreeing observations; the verified yellow-digit crop supports OCR without tiny thousands dots. Wallet refreshes every 20 rounds or when xu is unknown, retaining previously confirmed values on unavailable observations. The actual overnight image returned 1,657,051 xu and 262 lượng. Current live screenshot had a pet-info overlay and no visible wallet, correctly returning unknown; no game inputs were sent.

Added Tự động tiếp tục tiến trình nếu bị lỗi and a 1–20 attempt limit (default off, limit 3). Errors and failed reconnects can return through verified seat exit/world navigation, clear presentation caches, rescan once for the restarted preparation and continue the same worker with targets/counts/settings intact. A stop request never restarts. Pending payments remain blocked to prevent duplicate spending. Unknown overlays can be dismissed using up to three Android Back actions with fresh screen checks; exit-game confirmation is declined. Failed navigation or persistent errors consume the configured budget and then stop.

Modified gui.py, ui/settings_dialog.py, ui/runner.py, fishing/inventory.py; six new UI icon files; tests/test_dashboard_v3.py, tests/test_ui.py and tests/test_ui_redesign_v2.py. Screenshots: validation/dashboard-v3/dashboard.png, missions.png, settings.png. Validation: 235 full regression tests passed, plus 23 focused tests after final modal transaction/reconnect refinements. Recovery was simulated, including error → world → preparation, budget exhaustion, user stop, pending payment and preserving reordered progress; not live-tested against the user's current game activity.

Packaged --ui-check and --smoke-test returned 0; primary exe rebuilt; runtime hashes unchanged after build.

### App-lifetime inventory cache (2026-10-12)
Added an App-owned in-memory inventory cache shared across workers. Known ticket/bait observations and confirmed purchases/consumption survive Start/Stop and automatic recovery. Preparation rescans only when the selected area's ticket or bait is unknown, or the prior scan was incomplete. A newly opened app discards disk ticket/bait observations and starts unknown, while preserving settings, mission progress, fish stock and pending-payment safeguards. Modified gui.py, ui/runner.py and cache lifecycle regression in tests/test_dashboard_v3.py. No live game inputs used for this change.

Validation: 236 tests passed; packaged UI/smoke exit codes 0; runtime hashes unchanged. Primary exe rebuilt.

### Banner overlay and full-height progress (2026-10-12)
Navbar now overlays the banner using a blurred translucent-look composite from the same banner pixels, with readable opaque controls. Progress card and Treeview fill the available vertical space. Global workspace scrollbar is hidden whenever the content fits; it remains a fallback at small window sizes. Activity retains its own log scrollbar. Modified gui.py, ui/theme.py and layout regression in tests/test_dashboard_v3.py. Visually reviewed validation/dashboard-v3/dashboard.png. 236 full tests plus 15 focused final layout tests passed; exe UI/smoke returned 0; runtime hashes unchanged.


### Miss counter and area-specific bait (2026-10-13)

The worker already computed casts minus bites, but UI replaced this with Chưa rõ whenever a fish result was unclassified. UI now derives and displays max(0, casts - bites), independent of fish identification; session and area-statistics reports use the same formula. Confirmed failed-puzzle counts remain separate.

Ecological Mồi Trùng and dock Mồi Câu Cá Trâm retain independent stocks, consumption, receipts and purchase routes. Added tests where one area has bait but the other is empty: dock purchases only dock bait and ecological purchases only worms, preserving the other balance. Preparation now respects disabled auto-buy instead of buying during initial zero-stock setup. Dock out-of-bait refill closes the verified no-bait dialog/leaves the seat before preparing and opening its shop; direct dock shop entry handles OUT_OF_BAIT too.

Modified gui.py, ui/runner.py, fishing/inventory.py, fishing/session.py, fishing/statistics.py and targeted tests. No new live casts or purchases; validations use existing fixtures and simulated receipts.

Validation: 241 regression tests passed; exe UI/smoke returned 0; runtime hashes unchanged. Primary exe rebuilt and temporary build files removed.

### Daytime dock puzzle recognition (2026-10-13)
Recorded dock rounds showed the matching board but detector returned UNKNOWN because the dark lower edge merged into daytime pier planks. Added a y=550 top-border scan to find_target_board, retaining width, center, slot spacing and scene/timer checks. No confidence threshold or input coordinates were loosened. Six actual puzzle frames from session 2026-10-13_19-54-06_124314 now detect FISHING and produce safe full matching plans; the other two frames show a transition and chat overlay and remain unrecognized. Added fixture tests/fixtures/dock/day_puzzle_planks.png and regression in tests/test_solver.py, asserting five target positions and correct sources [6,2,2,1,3]. Replay evidence: validation/dock-puzzle-replay.json. No extra live casts or purchases.

Validation: 242 tests passed; exe UI/smoke returned 0; runtime hashes unchanged; primary exe rebuilt and temporary build cleaned.

### Dark-background saved-account login (2026-10-13)
The stuck session 2026-10-13_20-12-19_163544 remained in wait_for_result after logout: blue-background logo and Continue templates scored only 0.25/0.74 against the actual black-background login. Added exact observed dark-logo and Chơi tiếp label templates; both must match, the button must be in the expected login region, and coordinates still derive from the matched label. Existing cooldown behavior and old login variant remain supported. New regression verifies dark login raises SessionLost through ControlledDevice and rejects scenes missing either logo or Continue label. Gracefully stopped the stuck worker before updating the exe. Live test tapped Chơi tiếp once at (656,560), confirmed world map after two frames; no casts/purchases/credential entry. Evidence: validation/live-dark-login/result.json and after.png. Modified fishing/reconnect.py, tests/test_reconnect.py; added two templates and actual login fixture.

Validation: 244 tests passed; exe UI/smoke returned 0; runtime hashes unchanged after graceful stop/build; primary exe updated and temporary build cleaned.


### Dock missing-bait dialog during boat entry (2026-10-15)

Logs from 18:51 and 20:09 repeatedly changed rooms/restarted because boat entry displayed the specific Mồi câu cá trâm required dialog, but DockController treated it as an unverified seat. Added the exact observed dock-bait text as an OUT_OF_BAIT template. DockController reports this both before entering a boat and while waiting for READY. Worker marks only dock stock as zero, closes the dialog/leaves the seat and uses the existing dock-specific purchase flow when enabled. A retry is bounded to one refill before refusing another purchase if the game still rejects the bait. Ecological stock remains unchanged.

Modified fishing/detector.py, fishing/dock.py, ui/runner.py; added no_bait_dock template, dock/no_bait_at_seat fixture and three regression tests. 247 tests passed; packaged UI/smoke returned 0.

Live validation completed: navigated from world map to dock, full chest scan confirmed both bait stocks 0 and coins 269749. Auto-buy was enabled with quantity 50. Bought exactly 50 Mồi Câu Cá Trâm (2500 xu), entered a boat and executed one cast; SUCCESS confirmed Cá vàng, cleanup returned READY/Quăng câu. No extra casts or ticket purchases. Evidence: validation/live-dock-seat-bait.txt and live-dock-seat-bait/fishing/summary.json. Runtime hashes unchanged by build. Primary exe updated.


### Continuous game quest hand-in (2026-10-15)

Game mission mode now returns to the quest hub after internally reaching targets, verifies game progress, acknowledges a fishing-quest reward only after two matching OK-button frames with completion/received wording, reads the new task twice and continues without emitting the final completion popup. If server progress is incomplete, it resumes that task. If opening the completed task again does not produce a new task, it stops after two reads. Unsupported next fish remain blocked. Custom targets retain completion-and-stop behavior.

QuestReader handles either the old current-task menu or a directly opened task/reward popup. Added exact observed OCR aliases from live task 12: ce chep ving, ce 16c and ce n6c map to cá chép vàng, cá lóc and cá nóc. World map drags now avoid the expanded bounds of visible region markers, including the city icon previously under the start point.

Modified fishing/quest.py, fishing/navigation.py and ui/runner.py; added tests/test_quest_cycle.py. Tests cover reward identity, two-frame acknowledgement, a non-reward OK popup, transition to the next task, incomplete server progress, bounded unchanged tasks, unsupported fish and task-12 OCR. Live task-12 reading validated separately; no new fishing casts or purchases. The actual completion/reward transition is simulated because the account already handed in task 11 manually.

Final validation: 254 tests passed; exe UI/smoke returned 0; runtime hashes unchanged after worker stop. Live reader confirmed task 12 requires 30 cá chép vàng, 30 cá lóc and 30 cá nóc. Primary exe rebuilt; temporary build removed.

## 2026-10-16: repeated snakehead shop failure and recovery loop

Latest session 2026-10-16_20-10-08_153080 failed before payment: Windows OCR read the selected snakehead ticket title as "Vé Cäu Cå Låc". Added a narrow observed-title alias in fishing/inventory.py; original TIMEOUT screenshot replay with real Windows OCR now returns ticket/ca_noc. Other product identities and payment price/receipt safeguards remain intact.

ui/runner.py now closes a positively identified fish shop using the established outside dismissal point and verifies disappearance before navigating. After declining an exit dialog it re-observes instead of breaking directly into map navigation. Three identical consecutive recovery failures stop the no-progress loop. Error explanation no longer treats an ordinary shop description containing a ticket name and Buy as proof of a missing/expired ticket.

Regression coverage added in tests/test_inventory.py and tests/test_dashboard_v3.py for the observed OCR spelling, verified shop dismissal without Android Back, repeated recovery failures, and preservation of the original shop error. Initial full suite found a test double missing a mock back method; corrected the test setup. Primary exe rebuilt successfully; --ui-check and --smoke-test both returned 0. No live purchases or fishing casts performed for this fix. Build staging removed to avoid retaining duplicate binaries.
Final validation: 258 tests passed in 100.717 seconds. Primary executable: dist/AvatarFishingBot/AvatarFishingBot.exe.

## 2026-10-16: snakehead purchase confirmation and nested popup recovery

Follow-up session 2026-10-16_20-22-47_818604 got past item selection but failed at confirmation: Windows OCR produced "Vé Cäu Cå L6c (5 Ngäy) vdi giå 10000 xu?". Extended only the observed snakehead-title aliases (l6c/16c), retaining exact product and numeric price checks. Added the actual screenshot as tests/fixtures/loc_ticket_confirmation.png and checks rejecting another ticket or a 1000-xu price.

Recovery now detects the actual coin payment popup through independently matched Cancel and Buy-coins buttons (the older purchase_confirm template does not match this screen), cancels it and verifies Cancel disappears before closing the underlying shop. Purchase-pending transactions remain blocked from recovery. Regression test covers cancellation before shop dismissal without Android Back.

Live validation completed on the emulator: selected snakehead ticket, opened confirmation, verified actual OCR, cancelled without payment, closed shop, verified return to map. Evidence: validation/loc-live/after.png and events.jsonl. No xu spent. 260 tests passed in 106.491 seconds. Primary exe rebuilt; --ui-check and --smoke-test returned 0; duplicate build staging removed.

## 2026-10-17: task 13 seahorse OCR caused world-map restart loop

Latest session 2026-10-17_08-42-02_953550 repeatedly rejected the task-13 target "cé ngVa". Added the exact observed ca ngva -> ca ngua alias. Replay of the actual quest_1.png using Windows OCR now identifies ca_loc/ca_noc, ca_ngua/ca_map and ca_ro/ca_ro correctly (validation/quest13-replay.json).

Added NonRecoverableError for unknown/unsupported mission targets, used both on initial quest loading and advancing a quest. Automatic restart excludes this error so navigation cannot repeatedly re-read the same unsupported target; removed the unrelated dock-level warning. Existing recoverable navigation/session errors still use the configured restart behavior.

Changed fishing/quest.py, ui/runner.py and tests/test_quest_cycle.py. Full suite: 262 tests executed, 261 passed and one newly added test had a frozen-options test setup error. Corrected test setup using dataclasses.replace; all 9 quest-cycle tests then passed. No production-code changes after build. Primary exe rebuilt; UI and smoke diagnostics returned 0. No live fishing or purchases performed in this fix; actual failed quest image replay verified. Build staging removed.

## 2026-10-17: reduce exact OCR dependence

Added vision/game_text.py with conservative unique catalog resolution of known glyph confusions (accent stripping, ce/ca, 0/o, 6/o, 1/l, v/u). This matching is exclusively for labels, never quantities or money, and unknown/ambiguous labels remain unknown. QuestReader retries unidentified targets on a cropped blue-letter mask at 2x resolution, requires unchanged numeric progress, and compares two fresh observations by mission number/species/progress rather than unstable raw OCR spelling.

Ticket selection now supports exact observed snakehead-name artwork; its confirmation uses exact product-and-price artwork plus an independent quantity-one anchor before any OCR fallback. Added loc_shop_name, loc_confirmation, loc_price templates from observed game screenshots. Other layouts still require the existing OCR checks; shark artwork checks remain. No general approximate price recognition was added.

Live validation found the game dropped the initial worm-selection tap. TravelController.select_worm now retries only item selection up to three times, requires a recognized shop before each tap and confirms worm identity plus 20-xu price. No payment retries. Added tests/test_game_text.py, tests/test_selection_retry.py and visual confirmation regressions in tests/test_inventory.py, including rejecting altered artwork/price/quantity. Existing app-lifetime inventory cache is preserved.

Exe rebuilt; UI/smoke checks both returned zero. Live current task 13 correctly resolved all targets, reused its completed chest observation on retry, confirmed purchase of 50 Mồi Trùng for 1000 xu, and navigated to ca_noc. No fishing tickets purchased. Detailed live log: validation/live-recognition-v3-retry.txt. Initial console test failed only on cp1252 log encoding; retry used UTF-8.
Final suite: 267 tests passed in 129.851 seconds. First live session reached ca_noc but could not verify a free chair; no cast occurred in that attempt. Bounded room-change follow-up initiated without further purchases.
Live follow-up: switched to room 10, verified a chair, cast once, solved the board and caught Cua (confidence 1.00). Session completed after one round; see validation/live-recognition-v3-fishing.txt. No additional purchases.

## 2026-10-17: durable per-device character state

Added ui/state_cache.py and runtime/character_state.json (atomic JSON writes, version 1, device serial). Persists independently observed tickets, ecological/dock bait stocks, wallet, scan metadata and game quest progress. Existing runtime/ui_last.json is migrated when no durable file exists. Corrupt or wrong-device cache is ignored; expired dated tickets become unknown. Pending-transaction state remains protected by the existing ui_inventory.json and is never bypassed by the fast path.

BotWorker loads durable observations before applying its in-memory layer, reuses a validated mission without opening its popup, and updates cached progress after round results. When the required ticket is active and required bait is known positive, prepare_area skips the hub/chest/shop and lets normal navigation go directly to fishing. Unknown required values still trigger observation; known missing tickets still require a complete scan before any purchase. A partial scan with the required owned ticket and known bait can proceed without resolving unrelated items. Mission completion still invokes verified hand-in/new-task reading.

Modified ui/runner.py, gui.py; added ui/state_cache.py and tests/test_state_cache.py. Updated prior app-close-reset test to the new persistence requirement and old active-ticket fixtures to future dates for expiry validation. The first suite exposed these outdated expectations plus a test temp-directory permission issue; corrected fixtures and test workspace paths. Exe rebuilt and UI/smoke checks returned zero. No live purchases or fishing casts were needed for this change.
Validation follow-up: full suite executed 270 tests; the sole remaining failure was an old UI expiry-date assertion after moving its fixture from 2026 to 2099. Corrected that assertion. All inventory tests and all three durable-cache tests then passed. Production exe code unchanged; no rebuild needed for test-only corrections.

## 2026-10-17: missed bites on shifted ca_noc camera

Session 2026-10-17_10-21-28_829512 recorded six casts, zero observed bites, six unclassified RESULT outcomes. No drag actions occurred in these rounds. Actual 003_UNKNOWN.png shows a valid four-cell puzzle and 004_RESULT.png shows Trật rồi: a camera shift obscured chair/name anchors and the background-dependent timer template. Solver independently matches the actual board safely to sources [5,2,2,5].

FishingDetector now recognizes ca_noc/ca_ro active boards via independent board geometry, orange timer (>300px with >=3px height), dark source-panel edge and >80% water sample. It does not lower matching thresholds or change the miss=casts-bites formula. New tests/fixtures/ca_noc_shifted_board.png and regression in tests/test_solver.py verify FISHING, exact source mapping and rejection with timer/panel/board removed.

271 tests passed in 120.570 seconds. Live at the same camera: one cast, bite observed, four drags, caught Cá nóc (1.00), COMPLETE and ready to cast. No purchases. Decremented durable bait stock by the one live-test cast and recorded one unsold puffer. New exe built; UI/smoke returned 0; staging removed. Evidence: validation/shifted-live.txt and validation/shifted-live/.

## 2026-10-17: long loading after chair entry, then decline exit

Latest session round_0087 timed out 24.5 seconds after entering a chair; its final screenshot still showed Xin chờ, classified UNKNOWN by the old text template. Added loading_seated_vi.png from the actual static lettering (excluding animated spinner), plus tests/fixtures/loading_seated.png. Loading recognition precedes all fishing/exit inputs.

FishingSession now waits while verified loading remains visible without a fixed loading duration, and restores fresh transition/chair-entry budgets after it clears. OneRoundBot similarly pauses its round/bite/result timers during recognized loading. App Stop remains available through ControlledDevice checkpoints. Exit confirmation still requires two observations and only presses the recognized No button; after dismissal a chair may be reselected from fresh observations if needed.

Focused bot/session suites passed (30 tests each). Simulated loading lasting beyond both the old 30-second limit and normal round deadline resumes via verified No without blind inputs. Live game was actually on the exit popup: the new _prepare_ready pressed No once and returned (True, Đã thấy Quăng câu). No casts or purchases. Evidence validation/seated-current.png, validation/seated-live.txt, validation/seated-live/after.png. Primary exe rebuilt; UI/smoke returned zero.
Full regression suite: see validation/tests-seated-loading.txt; all tests passed.
