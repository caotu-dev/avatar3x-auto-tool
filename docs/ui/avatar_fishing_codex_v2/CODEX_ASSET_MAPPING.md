# Avatar Fishing — Codex Asset Mapping
This bundle is optimized for Codex implementation. It contains the cropped asset pack plus a mapping file that explains where each asset belongs in the UI.
## How Codex should use this bundle
1. Use `assets/references/dashboard_main.png` as the primary reference for the main dashboard layout.
2. Use `assets/references/dashboard_settings_popup.png` as the primary reference for the settings modal.
3. For simple controls (buttons, tabs, tiles), **prefer recreating them in code** using the approved design tokens and styles. Use the crops to match spacing, icon placement, rounding, and proportions.
4. For fish illustrations and complex decorative art, it is acceptable to use the PNG crops directly, or replace later with cleaner/redrawn assets.
5. Keep business logic untouched. This bundle is for UI implementation only.
## Banners
Header / branding visuals
| Asset | Suggested target in UI | Notes |
|---|---|---|
| `banners/header_banner_full.png` | Header area | Use as full or sliced header background. |
| `banners/header_left_scene.png` | Header area | Use as full or sliced header background. |
| `banners/header_right_scene.png` | Header area | Use as full or sliced header background. |
| `banners/title_block.png` | Header area | Use as full or sliced header background. |

## Top Bar Controls
Top action bar below header
| Asset | Suggested target in UI | Notes |
|---|---|---|
| `controls/button_settings.png` | Top action bar | Recreate button styling in code; use crop for reference. |
| `controls/button_start.png` | Top action bar | Recreate button styling in code; use crop for reference. |
| `controls/button_pause.png` | Top action bar | Recreate button styling in code; use crop for reference. |
| `controls/button_stop.png` | Top action bar | Recreate button styling in code; use crop for reference. |
| `controls/button_open_log.png` | Top action bar | Recreate button styling in code; use crop for reference. |
| `controls/time_display_card.png` | Top action bar | Recreate button styling in code; use crop for reference. |

## Mode Tabs
Three mode tabs in column 1
| Asset | Suggested target in UI | Notes |
|---|---|---|
| `controls/tab_game_task.png` | Mode switcher | Selected/unselected visual state reference. |
| `controls/tab_free_fish.png` | Mode switcher | Selected/unselected visual state reference. |
| `controls/tab_custom_goal_active.png` | Mode switcher | Selected/unselected visual state reference. |

## Main Cards
Main content panels/cards
| Asset | Suggested target in UI | Notes |
|---|---|---|
| `cards/custom_goal_card.png` | Main columns card containers | Use for padding, title, and border reference. |
| `cards/fish_progress_card.png` | Main columns card containers | Use for padding, title, and border reference. |
| `cards/activity_card.png` | Main columns card containers | Use for padding, title, and border reference. |
| `cards/session_overview_card.png` | Main columns card containers | Use for padding, title, and border reference. |
| `cards/activity_log_textarea.png` | Main columns card containers | Use for padding, title, and border reference. |

## Overview Tiles
Small metric tiles in session overview
| Asset | Suggested target in UI | Notes |
|---|---|---|
| `cards/overview_tile_quang.png` | Session overview metrics | Use as card style reference; text should stay dynamic. |
| `cards/overview_tile_can_cau.png` | Session overview metrics | Use as card style reference; text should stay dynamic. |
| `cards/overview_tile_truot.png` | Session overview metrics | Use as card style reference; text should stay dynamic. |
| `cards/overview_tile_moi_mua.png` | Session overview metrics | Use as card style reference; text should stay dynamic. |
| `cards/overview_tile_sinh_thai.png` | Session overview metrics | Use as card style reference; text should stay dynamic. |
| `cards/overview_tile_ben_tau.png` | Session overview metrics | Use as card style reference; text should stay dynamic. |

## Ticket Cards
Ticket status cards in column 3
| Asset | Suggested target in UI | Notes |
|---|---|---|
| `cards/ticket_status_card.png` | Ticket status section | Contains yes/no state examples and time-left layout. |
| `cards/ticket_ro.png` | Ticket status section | Contains yes/no state examples and time-left layout. |
| `cards/ticket_ca_map.png` | Ticket status section | Contains yes/no state examples and time-left layout. |
| `cards/ticket_ca_loc.png` | Ticket status section | Contains yes/no state examples and time-left layout. |
| `cards/ticket_ben_tau.png` | Ticket status section | Contains yes/no state examples and time-left layout. |

## Fish Icons
Fish-specific icons for lists/tables
| Asset | Suggested target in UI | Notes |
|---|---|---|
| `fish-icons/ca_chep_vang.png` | Fish rows or option lists | Can be used directly as PNG assets. |
| `fish-icons/ca_loc.png` | Fish rows or option lists | Can be used directly as PNG assets. |
| `fish-icons/ca_chim.png` | Fish rows or option lists | Can be used directly as PNG assets. |
| `fish-icons/ca_ngua.png` | Fish rows or option lists | Can be used directly as PNG assets. |
| `fish-icons/ca_long_tong.png` | Fish rows or option lists | Can be used directly as PNG assets. |
| `fish-icons/ca_noc.png` | Fish rows or option lists | Can be used directly as PNG assets. |
| `fish-icons/ca_duoi.png` | Fish rows or option lists | Can be used directly as PNG assets. |
| `fish-icons/ca_lia_thia.png` | Fish rows or option lists | Can be used directly as PNG assets. |
| `fish-icons/cua.png` | Fish rows or option lists | Can be used directly as PNG assets. |
| `fish-icons/ca_ro.png` | Fish rows or option lists | Can be used directly as PNG assets. |

## Section Icons
Small icons used in section headers
| Asset | Suggested target in UI | Notes |
|---|---|---|
| `icons/icon_fish_progress_header.png` | Section headers | Prefer redrawing simple icons if needed. |
| `icons/icon_overview_header.png` | Section headers | Prefer redrawing simple icons if needed. |
| `icons/icon_tickets_header.png` | Section headers | Prefer redrawing simple icons if needed. |
| `icons/icon_activity_header.png` | Section headers | Prefer redrawing simple icons if needed. |
| `icons/icon_custom_goal_header.png` | Section headers | Prefer redrawing simple icons if needed. |

## Actions
Quantity input and action buttons under progress table
| Asset | Suggested target in UI | Notes |
|---|---|---|
| `controls/action_set_quantity_button.png` | Target-setting actions | Quantity input, reorder arrows, reset button. |
| `controls/action_order_up_button.png` | Target-setting actions | Quantity input, reorder arrows, reset button. |
| `controls/action_order_down_button.png` | Target-setting actions | Quantity input, reorder arrows, reset button. |
| `controls/action_reset_button.png` | Target-setting actions | Quantity input, reorder arrows, reset button. |
| `controls/action_quantity_input.png` | Target-setting actions | Quantity input, reorder arrows, reset button. |

## Popup
Settings modal sections and controls
| Asset | Suggested target in UI | Notes |
|---|---|---|
| `popup/settings_modal_full.png` | Settings modal | Includes full modal and section crops. |
| `popup/modal_header.png` | Settings modal | Includes full modal and section crops. |
| `popup/section_bait_purchase.png` | Settings modal | Includes full modal and section crops. |
| `popup/section_sell_fish.png` | Settings modal | Includes full modal and section crops. |
| `popup/section_auto_misc.png` | Settings modal | Includes full modal and section crops. |
| `popup/section_display_log.png` | Settings modal | Includes full modal and section crops. |
| `popup/modal_footer_actions.png` | Settings modal | Includes full modal and section crops. |
| `popup/button_cancel.png` | Settings modal | Includes full modal and section crops. |
| `popup/button_reset_default.png` | Settings modal | Includes full modal and section crops. |
| `popup/button_save.png` | Settings modal | Includes full modal and section crops. |
| `popup/input_bait_quantity.png` | Settings modal | Includes full modal and section crops. |
| `popup/input_sell_time.png` | Settings modal | Includes full modal and section crops. |
| `popup/checkbox_blue_checked.png` | Settings modal | Includes full modal and section crops. |
| `popup/checkbox_blue_unchecked.png` | Settings modal | Includes full modal and section crops. |
| `popup/info_icon.png` | Settings modal | Includes full modal and section crops. |
| `popup/close_icon.png` | Settings modal | Includes full modal and section crops. |
| `popup/icon_modal_settings.png` | Settings modal | Includes full modal and section crops. |
| `popup/icon_section_bait.png` | Settings modal | Includes full modal and section crops. |
| `popup/icon_section_sell.png` | Settings modal | Includes full modal and section crops. |
| `popup/icon_section_misc.png` | Settings modal | Includes full modal and section crops. |
| `popup/icon_section_log.png` | Settings modal | Includes full modal and section crops. |

## Suggested implementation order for Codex
1. Build base shell: header + top action bar + 3-column body.
2. Implement column 1 tabs and one shared card container that swaps content by active mode.
3. Implement column 2 progress + activity blocks.
4. Implement column 3 overview + ticket cards.
5. Implement settings modal and wire the existing settings controls into it.
6. Replace placeholders with the fish icons and final section icons.
7. Final pass: spacing, checkbox consistency, remove redundant text, visual QA against the reference mockups.

## V2 correction — fish icon source of truth
**IMPORTANT: legacy `assets/fish-icons/*` crops were offset and may contain wrong imagery.** Prefer the corrected `assets/fish-icons-clean/` files below, inspected in `FISH_ICONS_PREVIEW.png`. These are still PNG crops with possible light background. Map using real fish IDs/names, not hard-coded table positions.

- `assets/fish-icons-clean/ca_chep_vang.png` — Cá chép vàng
- `assets/fish-icons-clean/ca_loc.png` — Cá lóc
- `assets/fish-icons-clean/ca_chim.png` — Cá chim
- `assets/fish-icons-clean/ca_ngua.png` — Cá ngựa
- `assets/fish-icons-clean/ca_long_tong.png` — Cá lòng tong
- `assets/fish-icons-clean/ca_noc.png` — Cá nóc
- `assets/fish-icons-clean/ca_duoi.png` — Cá đuối
- `assets/fish-icons-clean/ca_lia_thia.png` — Cá lia thia
- `assets/fish-icons-clean/cua.png` — Cua
- `assets/fish-icons-clean/ca_ro.png` — Cá rô
