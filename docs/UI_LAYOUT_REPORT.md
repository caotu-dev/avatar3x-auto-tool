# Dashboard layout update — 2026-10-17

Moved compact Start/Pause/Stop controls above Activity in the right column. Other actions each occupy a separate navbar card below the banner. Currency cards and timer share that row. Banner rendering now preserves image aspect ratio using centered cover/crop; responsive height is 100–144 pixels instead of 246–290.

Normalized oversized 512px icon sources at display time (original files unchanged). Kept three columns at all supported window sizes, reduced overview/ticket spacing and adapted progress row height to fit all thirteen fish rows. Table changes schedule a layout pass so a previously shown workspace scrollbar is removed correctly. Log text retains its independent scrolling.

Geometry checked at 1536x960, 1440x900, 1280x800 and 1024x720, including complete ticket expiry text: no navbar/banner overlap and no page scrollbar. Thirteen fish rows also fit at 1024x720 (27px rows). Preview: ui-layout-preview.png. Last complete regression run: 275 tests passed. Subsequent compact-height/row-layout refinements passed the 13 dashboard tests and explicit geometry checks. Exe UI/smoke checks passed; final build refreshed afterward.

Modified gui.py, ui/theme.py and the prior overlay-layout assertion in tests/test_dashboard_v3.py. Fishing engine, OCR, navigation, scheduling and persistent settings/state were not changed. Temporary preview script and build staging cleaned; only the main application exe is retained.
