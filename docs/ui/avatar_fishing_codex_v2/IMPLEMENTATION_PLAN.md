# Implementation plan — Avatar Fishing Bot v2

Actual bundle: docs/ui/avatar_fishing_codex_v2. Tkinter 8.6/ttk, gui.py bootstrap; ui/theme.py owns local rounded assets and DPI-aware fonts. Reuse toolkit.

| Widget | Source | Callback |
|---|---|---|
| Start/Pause/Stop | App.worker; BotWorker stop/pause Events | start/pause/stop |
| Timer | Existing monotonic session clock, includes pause | poll |
| Mode tabs | Notebook view; existing idle exclusivity retained, locked during session | mode_changed/options_changed |
| Mission/free/area | BooleanVars, AREAS_UI -> Options | options_changed/start |
| Settings | runtime/ui_preferences.json; immutable worker Options while running | draft modal -> atomic save_preferences |
| Custom targets | SPECIES filtered through quest.AREAS; Treeview hidden quantity model 1..9999 | custom_click/set_target_quantity/move_target/reset_custom_targets |
| Progress | worker targets/counts queue snapshots | render_progress |
| Metrics | casts/bites/misses/bait_purchased; bait_stocks ecological/dock | poll |
| Tickets | No authoritative presence/expiry source | four unknown cards; no OCR changes |
| Logs | queue -> poll (100 events/100ms), 1500 visible lines; debug/ui | append/open_logs |
| Shutdown | stop Event -> done queue -> wait_close | close |
| Packaging | build_gui.ps1, PyInstaller onedir; ui/assets bundled | frozen relative theme assets |

Implement: topbar and 35/40/25 zero-minsize grid after gutters; right column reflows below at <1200px; full-height catalog/progress and single outer scroller. Keep existing event callbacks and immutable Options; modal uses isolated variables, disables unsafe settings during run, validates and persists atomically before applying. Correct fish crops mapped by species ID. Preserve all engine/OCR/scheduling code. Test regressions and modal errors; capture real UI at three sizes and build executable.

Ticket future contract: ticket_type, presence yes/no/unknown, expires_at optional, read_at; unavailable source currently always unknown. Sinh thái/Bến tàu retain actual bait-stock semantics, not invented location. No restore defaults API or configurable display/other options exists, so omit those mockup controls. No hotkeys exist.
