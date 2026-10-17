# Storage cleanup — 2026-10-17

Before: 16,062,349,955 bytes. After cleanup: approximately 493,747,925 bytes (97% reclaimed; small report changes may alter the final total).

The main source of growth was dist/AvatarFishingBot/debug (~14.82 GB), followed by old development captures and generated validation images. Removed redundant diagnostic images/logs, kept five latest error_screen.png examples, small per-round result records used by recovery, reusable Python tools, docs/design references, test fixtures and all production assets. Preserved runtime state and settings. Protected-file hash verification: no changes. All 275 tests passed in 125.933 seconds; packaged UI/smoke returned zero.

Exactly one application executable remains: dist/AvatarFishingBot/AvatarFishingBot.exe. The root .lnk is a verified shortcut to that file. Python/build tools in .venv are dependencies, not duplicate bot releases. The builder now deletes its staging/work directory after success.

Future growth controls: automatic event screenshots in debug/ui, runs, trials, navigation, dock, tours and missions use three rotating JPEG slots per folder. Logged image names reflect the actual saved slot. Live screen arrays, OCR inputs and matching templates remain untouched. Debug cleanup runs at most once per ten minutes, preserving Python code, recovery result.json records and files modified in the last ten minutes; older diagnostics obey 24-hour/128-MB retention. Manual screenshot exports remain lossless PNG. No automation, OCR matching, coordinate, session scheduling or persistent character-state logic was changed.

Modified: adb/screenshot.py; fishing/bot.py, session.py, travel.py (diagnostic filenames only); ui/runner.py (periodic pruning); build_gui.ps1; README.md. Added debug/retention.py and tests/test_debug_retention.py.
