# Main release promotion and cleanup

UI Redesign v2 is now the main release: `dist/AvatarFishingBot/AvatarFishingBot.exe`.
The existing root shortcut targets this executable. Only `build_gui.ps1` remains.

## Refactor

Removed obsolete sidebar navigation/toggle handlers, unused combined stats variables,
the old quantity-widget alias, unused navigation/notebook styles, and unused theme tokens.
Updated the recovery test to check the real settings button. No fishing, OCR, coordinates,
state machine, shop, inventory, navigation or scheduling source was changed.

The canonical build stages the package, updates package-owned files using `release-files.json`,
removes stale managed files, and excludes runtime/debug from replacement. Verified with Windows
PowerShell 5: rebuilding preserved all eight runtime files by SHA-256. UTF-8 BOM is retained in
this PowerShell script for Vietnamese strings on Windows PowerShell.

## Deleted

`CLEANUP_MANIFEST.json` records 5,313 files totaling 815,644,286 bytes (about 816 MB):

- Duplicate build/release outputs and PyInstaller caches; separate dist-v2 package/build script.
- Three obsolete UI design packs; kept the approved current v2 references, interaction specs and capture tool.
- One-off patch scripts, old previews and superseded UI validation outputs.
- 21 runtime PNGs not loaded by the app, including sidebar, timer artwork and unsupported cá lia thia.
- Source __pycache__ directories. The Python environment and build requirements remain.

The earlier replaced main package was also removed after data migration. Current v2 validation
logs are consolidated in `validation/`. Application/source runtime, gameplay session logs,
recognition templates, test fixtures and reusable CLI recording/analysis tools were retained.

## Data migration

`RELEASE_MIGRATION.json` records the latest runtime file chosen by modification time and verified
copy hash. All 6,953 files of session evidence from both releases were moved into main debug/
(5,279,175,144 bytes before path updates). Three diagnostic JSON paths pointing at dist-v2 were
rewritten to the canonical release. The latest session log directory was verified to exist.
No progress, inventory, coordinates, counts or scheduling values were rewritten.

## Validation

- Post-refactor, post-asset cleanup: 154 tests passed in 77.197 seconds; `validation/main-tests.txt`.
- Executable GUI check and smoke test: exit 0 before and after final cleanup. 47 assets loaded,
  three mode tabs, no worker started; OCR script and dock templates present.
- Actual canonical build script succeeded; `validation/rebuild-check.txt`. Runtime hashes unchanged.
- No live ADB fishing run was started during promotion/cleanup.

The unit-test log includes one Tcl ThemeChanged teardown diagnostic when a hidden test window was
destroyed; it did not fail any test. This was not observed in executable smoke checks.
