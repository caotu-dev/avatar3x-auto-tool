# Avatar Fishing Bot UI Redesign v2 — delivery

## Implementation

- Reused Tkinter 8.6/ttk. Offline v2 token adapter, continuous supplied banner scenery with native branding, rounded live cards and buttons.
- One top session bar: Settings, Start, Pause/Resume, Stop, log folder, existing elapsed clock. At narrow/DPI-adjusted widths, timer moves to a second line to keep labels visible.
- Dashboard uses 35/40/25 weights after gutters. Below a DPI-adjusted 1200px breakpoint, overview/tickets move below the first two columns. Main page scrolls vertically; no fish-table inner scroller.
- All three original modes, exclusivity, active-session edit locks and callbacks preserved. Existing session options remain immutable during a worker run. Pause still takes effect at the engine's existing checkpoint and elapsed time still includes pauses.
- Native catalog checkboxes share settings styling. Selection is independent of inclusion. Quantity (1..9999), move arrows, drag order and reset use the original model/order/reset behavior. Toolbar lives under progress and is hidden outside Custom. Arrow limits/no-selection/run locks enforced. Changes persist through the existing preference schema.
- Progress updates stable species IDs and rows, uses corrected species icons, retains selection/input, expands to all rows. Preview reads matching saved custom progress when available.
- Six metrics wired to existing counters and bait stocks. Sinh thái/Bến tàu represent actual ecological/dock bait stocks, not guessed locations. Four read-only tickets show Chưa xác định / — because no authoritative ticket presence/expiry reader exists.
- Settings modal has dim backdrop, grab/focus, Cancel/X/Escape, draft variables, 1..50 validation, atomic disk commit before applying values, and save failure feedback. Selling time remains fixed at 23:57. Settings lock during sessions and unlock after completion. Unsupported mockup toggles/default-reset omitted.
- Existing queue/main-thread updates and bounded log history retained. Poll is one scheduled job, cancelled on disposal; folder-open failures display an error.
- Core engine, automation, OCR, coordinates, navigation, inventory, and scheduling source were not changed.

## Modified/added source files

| File | Purpose |
|---|---|
| gui.py | Layout, callback routing, responsive behavior, target preview, lifecycle cleanup |
| ui/theme.py | V2 token adapter and primary blue button style |
| ui/fish_catalog.py | Full-height native-checkbox catalog; stable existing target model API |
| ui/settings_dialog.py | Draft settings modal and validation/atomic commit |
| ui/assets/design_tokens_v2.json | Offline tokens copied from approved bundle |
| ui/assets/fish_*.png | Corrected crops mapped to existing fish IDs |
| ui/assets/header_*.png | Continuous v2 scenery with raster branding/title buttons removed |
| ui/assets/blue*.png, PROVENANCE_V2.md | Primary Save surfaces, asset provenance |
| build_gui.ps1 | Reproducible isolated PyInstaller onedir build |
| tests/test_ui_redesign_v2.py | Seven UI acceptance tests, including single timer |
| tests/test_gui_error_recovery.py | Update old always-enabled toolbar assertion for contextual v2 rules |
| tests/test_ui_updates.py | Give mocked device a valid numpy screenshot for existing reconnect guard |
| docs/ui/avatar_fishing_codex_v2/IMPLEMENTATION_PLAN.md | Audit, model/callback map and plan |
| docs/ui/avatar_fishing_codex_v2/capture_ui.py, screenshots/* | Isolated visual capture and layout evidence |

## Validation

Regression and acceptance: `python -m unittest discover -s tests`. Final result: 154 tests passed in 67.999 seconds (OK), recorded in `validation/redesign-tests.txt`.

Executable: `dist/AvatarFishingBot/AvatarFishingBot.exe`. PyInstaller build successful. Both `--ui-check` and `--smoke-test` exited 0; 49 assets loaded, three tabs, no worker started; 10 dock templates and packaged OCR script confirmed. Build log: `validation/redesign-build.txt`.

Visual comparison: captured real Tk UI at 1536x1024, 1280x800, 1024x720, using Tk scale factors 100/125/150%. All topbar buttons fit in all nine combinations; catalog has all nine supported fish; progress has no yscrollcommand. Screenshots and measurements: `screenshots/layout-checks.json`. This simulates Tk scaling; it does not replace checking Windows display DPI on another machine.

`dashboard-goals.png` and `settings-popup.png` show the actual app using isolated test preferences and goals of one fish each. No game worker ran and no catch/log/metric events were fabricated. Existing user preferences were not saved by the capture script.

## Limitations and visual adaptations

- Nine supported species; cá lia thia is absent from the actual automation catalog and was not injected.
- Four tickets remain unknown until a backend provides ticket_type, presence yes/no/unknown, expires_at optional, read_at.
- Modal has two supported groups rather than four illustrative groups; no unsupported toggles, time picker, restore-default action or F8/F9/F10 hotkeys added.
- Catalog order and zones follow the code rather than illustrative labels/order. Native popup/window decorations retained. Raster art/crops may soften at high DPI.
- Full tables grow naturally; page scrolling may be required to read the log and overview, particularly with full targets or narrow windows.
- Live fishing on LDPlayer/ADB was not executed. Real gameplay and Windows DPI behavior still need user testing. Existing unverified dock-fishing restriction remains.
- Build is onedir: keep the entire AvatarFishingBot folder with the executable. UI v2 is now the main dist release. The promotion retained the latest runtime files and both releases’ session logs; see CLEANUP_REPORT.md.

