# Inventory recognition assets

Derived from the user-provided screenshots of MENU, chest, ecological tickets,
and the dock ticket/bait, plus the existing `tests/fixtures/worm_selected.png`.
The runtime requires Android 1600×900. Slight sprite scale differences are supported.

- `basket`, `chest_title`: identify the inventory entry and open chest.
- `ca_ro`, `ca_noc`, `ca_map`, `dock`: ticket sprites. Verified presence in the chest
  means active: expired tickets disappear, as confirmed by the user.
- `ecological_bait`, `dock_bait`: known bait sprites; unreadable details keep stock unknown.
- Day/night coin and gold glyphs locate balances. Subsequent gold symbols delimit
  locked currency; only the first spendable gold balance is used.

Expiry and quantity come from selected-item details and repeated OCR observations.
The fixed stack-font digit masks provide a verified fallback when Windows OCR
cannot read a lone digit. Masks come from live chest captures, not generated fonts.
No generated UI icon is used for game detection. Missing states require a completed,
bounded scan from the verified top to a stable bottom of the item list.
