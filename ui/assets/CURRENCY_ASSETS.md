# Currency icons — 2026-10-18

User requested the existing silver coin and gold ingot from currency_coins.png
and currency_gold.png, with their blue backgrounds removed. These assets replace
the two currency crops previously taken from the dashboard reference. Those
obsolete crops and their extraction/provenance entries were removed, so the
existing loader selects the root assets.

Edited using the built-in image_gen tool with transparent_background=true.
Prompts:

- Coin: "Edit target: the supplied small game currency icon. Remove ONLY the solid cyan/blue square background, making it fully transparent. Keep this exact silver coin with dollar symbol, existing outline, shading, colors, proportions, orientation and details. Do not redesign, add objects, add a backdrop, or change the coin. Produce one centered tight transparent cutout icon for use at 32px in an existing desktop UI."
- Gold: "Edit target: supplied small game currency icon. Remove ONLY the solid cyan/blue square background, making it fully transparent. Keep this exact golden Chinese ingot/yuanbao with existing outline, shading, colors, proportions, orientation and details unchanged. Do not redesign, add objects or backdrop. Produce one centered tight transparent cutout icon for use at 32px in an existing desktop UI."

The transparent outputs were trimmed to alpha bounds and fitted proportionally
into 32x32 RGBA canvases with 1px padding using System.Drawing. Generated source
outputs are retained in the Codex generated_images directory; these final assets
are self-contained project files. Both PNGs have transparent corners. Appearance
was checked at actual UI size in docs/ui/strict-regression/currency-startup.png.
18 existing dashboard/reference tests passed (docs/build/currency-tests.txt).
