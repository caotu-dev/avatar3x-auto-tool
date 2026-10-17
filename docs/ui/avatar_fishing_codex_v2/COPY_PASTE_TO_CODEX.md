# Copy/paste this into Codex (from the Python repository root)

```text
Implement the approved Avatar Fishing Bot desktop UI redesign v2 in this repository, not just a plan or mockup.

Read these files completely, in order, before touching code:
- docs/ui/avatar-fishing-v2/CODEX_MASTER_PROMPT.md (BEGIN PROMPT → END PROMPT)
- docs/ui/avatar-fishing-v2/UI_INTERACTION_FLOW.md
- docs/ui/avatar-fishing-v2/DESIGN_TOKENS_V2.json
- docs/ui/avatar-fishing-v2/CODEX_ASSET_MAPPING.md
- docs/ui/avatar-fishing-v2/assets/references/dashboard_main.png
- docs/ui/avatar-fishing-v2/assets/references/dashboard_settings_popup.png

Treat v2 as authoritative over older specs. Inspect the actual Python GUI toolkit, bot engine callbacks, session states, settings persistence, target model, threading, and packaging first. Write a short IMPLEMENTATION_PLAN.md, then IMPLEMENT all safe UI phases and run the available tests. Do not stop after planning.

Mandatory layout changes: settings modal; horizontal top session control bar; three main columns 35%/40%/25%; three mode tabs; custom-target table only Chọn/Loại cá/Khu câu, with all rows visible (no nested table scroll); target quantity/reorder/reset actions moved to progress card; 6 real overview metrics and 4 truthful ticket states; matching checkbox styles and concise Vietnamese labels. Keep existing automation/OCR/coordinates/behavior untouched. Use assets/fish-icons-clean/ instead of miscropped legacy icons. Do not hardcode mockup fish counts, ticket statuses, countdowns, fishing locations or shortcut keys.

At the end report changed files, real functional wiring, test commands/results, any screenshots and implementation limitations. If the bundle is in another folder, locate its real path and use it.
```
