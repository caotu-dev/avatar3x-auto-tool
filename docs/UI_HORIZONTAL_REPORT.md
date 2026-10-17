# Horizontal dialogs and left-column controls — 2026-10-17

Settings is a two-column, four-group modal with fixed horizontal layout and no scroll canvas. Mission selection retains its three modes and Save/Cancel behavior, while all thirteen fish are split into two side-by-side lists. Reordering hit-testing now checks both x and y for the two-column catalog.

Start/Pause/Stop and timer moved below Tickets in overview column 1, arranged 2x2: Start/Pause, Stop/Timer. Buttons fill half-column width. Timer uses the supplied ui/assets/clock.png. Navbar contains only Settings, Mission selection, Log folder, Xu and Lượng. Activity fills column 3. Compact overview spacing and inline metric values allow the added controls to fit without page scrolling.

Geometry checks with complete ticket expiry text and long ecological/dock bait labels passed at 1536x960, 1440x900, 1280x800 and 1024x720. At the smallest size, content requires 516 of 522 available pixels. Settings fits 1020x620; mission popup fits 1040x600 with no catalog scroll. Preview images: ui-layout-preview.png, ui-settings-preview.png, ui-missions-preview.png. Full suite: 275 tests passed in 112.064 seconds.

Modified gui.py, ui/settings_dialog.py, ui/fish_catalog.py, ui/theme.py and layout assertions in tests/test_dashboard_v3.py. Supplied clock.png is included in the existing asset bundle. No engine/OCR/navigation/session-state changes. Initial release copy was blocked by the old running executable; the app subsequently closed and the build was retried. Temporary preview script and staging are cleaned after completion.
