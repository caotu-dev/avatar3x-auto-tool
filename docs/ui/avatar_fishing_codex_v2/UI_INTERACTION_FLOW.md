# Avatar Fishing Bot — UI / Interaction / State Flow v2

**Version:** 2.0 · **Scope:** Python desktop GUI redesign only · **UI language:** Tiếng Việt  
**Source of truth:** Requirements approved in conversation + two reference images (`assets/references/dashboard_main.png`, `dashboard_settings_popup.png`). **Actual business behavior** must be taken from the existing Python code and engine contracts; screenshots contain example values only.

## 0. Core product rules

**R-01.** Exactly **one top action bar** below banner. No permanent left Settings/Timer/Buttons sidebar; no duplicate session controls.  
**R-02.** Three body columns on wide desktop: **35% mode, 40% progress/log, 25% summary/tickets**. Remove old sidebar completely.  
**R-03.** Mode list/table (including custom fish table) should grow to **show every item**; **no inner vertical scroll** for fish tables. Only page-level scrolling is allowed for the whole dashboard. Activity log is the exception and may scroll internally.  
**R-04.** One consistent checkbox component size/style for Settings and custom targets; label remains clickable and keyboard-accessible.  
**R-05.** No redundant `Đang chạy` / `Phiên câu đang hoạt động` labels (timer on topbar); error/safety feedback still allowed.  
**R-06.** Mode tabs change **visible UI panel**; only an explicit existing engine command may change automation mode.  
**R-07.** New four ticket tiles are **read-only**; do not guess availability/countdowns.  
**R-08.** Separate **view state**, **settings draft**, **persisted configuration**, **session runtime state**, and **engine observations**.

### 0.1 Entities and ownership

| Entity | Examples | Owner/source | Update mechanism |
|---|---|---|---|
| `ui.active_tab` | `MISSION`, `FREE`, `CUSTOM` | GUI local state (may mirror saved preference) | Tab click/keyboard |
| `engine.active_mode` | engine enum/mode | Existing engine/config | Existing callbacks only |
| `engine.session_state` | `IDLE`, `RUNNING`, `PAUSED`, etc. | Existing engine (map real states to UI) | Engine events / polled safe snapshot |
| `settings.current` | buy/sell toggles, bait amount | Existing config storage/current settings API | Config load/save |
| `settings.draft` | unsaved modal edits | GUI modal only | User editing, destroyed at exit |
| `targets` | fish id, zone, selected, quantity, order | Existing domain model | Existing target APIs |
| `progress` | catches, goals, mission progress | Existing engine | Engine event/state snapshot |
| `stats` | Quăng, Cắn câu, Trật, Mồi mua | Existing counters | Engine event/state snapshot |
| `zone` | Sinh thái, Bến tàu | Existing engine/vision state | Engine observations |
| `ticket_status` | 4 tickets: presence & expiry | Existing authoritative source if available | Engine events/state snapshot |
| `ui.log_view` | visible entries/scroll position | GUI projection of existing log source | Batched main-thread append |
| `ui.session_clock` | displayed HH:MM:SS | Existing elapsed/timer semantics | One periodic GUI refresh |

**Important:** `ui.active_tab != engine.active_mode` is possible if tab switching is view-only in current app. Never silently equate them. During initial audit, Codex must map original tab selection/checkbox semantics and keep them intact.

### 0.2 Desktop structure

```text
MAIN WINDOW
  ├─ HeaderBanner [decoration, brand title]
  ├─ SessionTopBar
  │    ├─ SettingsButton
  │    ├─ StartButton / PauseOrResumeButton / StopButton
  │    ├─ OpenLogFolderButton
  │    └─ ElapsedTimer
  └─ DashboardBody [single outer vertical scroller when needed]
       ├─ Column1 (35%)
       │    ├─ ModeTabs: Mission | Free | Custom
       │    └─ ModePanel[active tab only]
       ├─ Column2 (40%)
       │    ├─ FishProgressCard
       │    │    ├─ ProgressTable (natural height, no inner scroll)
       │    │    └─ TargetActionToolbar (contextual)
       │    └─ ActivityLogCard (independent log scroll allowed)
       └─ Column3 (25%)
            ├─ OverviewCard (6 tiles)
            └─ TicketsCard (4 ticket statuses)

SETTINGS_MODAL [opened from SettingsButton, overlay above main window]
  ├─ Bait / purchasing group
  ├─ Fish selling group
  ├─ Other *already-supported* settings groups (optional)
  ├─ Validation messages
  └─ Cancel | Save [Restore defaults only if supported]
```

At narrower window, columns can reflow; the **information hierarchy, controls and no-fish-table-scroll rule remain**. Main page scrolling is the acceptable tradeoff.

---

## 1. Session lifecycle / global topbar

### 1.1 UI-facing state mapping

Use *real* state enum/flags and adapt them into the following conceptual states; do not replace the real engine state machine:

| UI state | Meaning | Start | Pause/Resume | Stop | Timer | Note |
|---|---|---|---|---|---|---|
| `IDLE` | No active session | Enabled only if mode/settings valid | Disabled | Disabled | `00:00:00` or retained per existing behavior | Settings available |
| `STARTING` | Launch requested, pending acknowledgement | Disabled | Disabled | Engine-dependent | Existing clock or `00:00:00` | Prevent duplicate launch |
| `RUNNING` | Bot actively working | Disabled | **Pause** if supported | Enabled if supported | Running | Do not add `Đang chạy` prose |
| `PAUSING` | Pause in progress, if engine exposes it | Disabled | Disabled | Engine-dependent | Follows engine semantics | No duplicate pause |
| `PAUSED` | Session suspended | Disabled (unless Start is existing resume control) | **Tiếp tục** if supported | Enabled if supported | Pause/freeze as engine defines | No timer reset |
| `RESUMING` | Resume pending | Disabled | Disabled | Engine-dependent | Existing semantics | No duplicate resume |
| `STOPPING` | Cleanup/cancel in progress | Disabled | Disabled | Disabled | Existing clock | UI remains responsive |
| `STOPPED` | Finished/stopped | Enabled if preconditions pass | Disabled | Disabled | Reset/retain per engine policy | No auto-clear stats unless engine does so |
| `ERROR` | Engine failure | Engine-dependent safe retry | Disabled unless supported | Enabled if cleanup needed | Existing state | Concise error explanation |

Engine may expose fewer states; map conservatively, never invent fake transitional events in logs.

### 1.2 Event/action contracts

| ID | User action | Preconditions | UI behavior | Engine/data effect | Error or blocked behavior |
|---|---|---|---|---|---|
| `ACT-01` | Click `Bắt đầu` | Engine allows start, valid settings, valid mode/target | Immediately disable duplicate Start; show non-intrusive pending affordance | Call **existing** Start once | Display actual reason (e.g. invalid selection/game not ready); no phantom session |
| `ACT-02` | Click `Tạm dừng` | `RUNNING` and pause supported | Disable button until engine acknowledges | Existing pause handler | Restore true state from engine after failure |
| `ACT-03` | Click `Tiếp tục` | `PAUSED` and resume supported | Disable while resuming | Existing resume handler | Never create second run thread |
| `ACT-04` | Click `Kết thúc` | Existing engine allows stop | Pending/disabled conflict buttons | Existing stop/cleanup handler | If engine already stops, do nothing extra |
| `ACT-05` | Click `Mở thư mục log` | Log path known | Invoke OS folder opener without blocking GUI | Existing path/function | Show brief error if folder unavailable |
| `ACT-06` | Observe timer tick | View alive & clock present | Render HH:MM:SS from authoritative elapsed value | No engine command | Prevent duplicate scheduler callbacks |
| `ACT-07` | Window Close | Any | Follow existing safe close/confirm semantics | Existing worker cancellation and teardown | No abandon of active worker/no UI hang |

**Decision rule:** don't infer session state from nonzero timer. A nonzero timer can persist after stop or during pause.

### 1.3 Happy path (start → pause → resume → stop)

```text
Load GUI → load persisted settings, modes, targets → engine snapshot → idle controls
  ↓ click Start (if valid)
Disable repeated Start → existing engine starts → transition to RUNNING on acknowledgement
  ↓ logs/counters/timer arrive via thread-safe GUI dispatcher
Click Pause → engine acknowledges PAUSED → Pause control becomes Resume if supported
  ↓ click Resume
Engine acknowledges RUNNING → continue existing session/clock, not a new session
  ↓ click Stop
Engine acknowledges STOPPING → cleanup → STOPPED → buttons reset per engine policy
```

### 1.4 Topbar layout/states

- Order fixed: `Thiết lập`, `Bắt đầu`, `Tạm dừng/ Tiếp tục`, `Kết thúc`, `Mở thư mục log`, timer right aligned.
- Native visible focus and tooltip/accessible names for icon + text buttons.
- No `Đang chạy`, `Phiên câu đang hoạt động`, extra status badges. Meaningful errors may appear in context.
- If Stop action has unavoidable side effects, preserve existing confirmation behavior; do not invent one that blocks normal operation.
- Settings may remain open while engine changes state; refresh which fields are editable based on authoritative engine status.

---

## 2. Settings modal (`SET-*`)

### 2.1 Entry and dismissal

| ID | Trigger | Result |
|---|---|---|
| `SET-01` | Click topbar `Thiết lập` | Create/open a single modal, copy current config to `settings.draft`, focus first enabled control |
| `SET-02` | Edit checkbox/number | Update **draft**; don't persist yet if deferred-save contract is supported |
| `SET-03` | Click `Hủy` | Discard draft, close; existing saved/current values unchanged |
| `SET-04` | Click `X` | Same behavior as Cancel; if toolkit has unsaved-change confirmation it should be consistent, not a hidden Save |
| `SET-05` | Press `Esc` | Same behavior as Cancel (unless confirmation or unsafe modal state) |
| `SET-06` | Click `Lưu thay đổi` | Validate all editable fields, save via existing config function(s); refresh dependent controls, close on success |
| `SET-07` | Save fails | Keep modal open and draft intact; show actionable error; no partial silent success |
| `SET-08` | Defaults restore | **Only if existing, safe restore-default mechanism**; otherwise omit this button despite mockup |
| `SET-09` | Click settings while already open | Bring existing modal to front; no second instance |

**Popup visuals:** centered 560–650 px preferred width (adapt to native GUI), rounded white card, dim backdrop, blue group headers, spaced inputs, consistent 20–24 px checkbox hit targets, modal footer actions aligned. Modal body can have its **own scrolling** if many settings; background page should not scroll/interact while modal active.

### 2.2 Field-level bindings

| ID | Field | Type | Accepted input & result |
|---|---|---|---|
| `SET-10` | `Mua mồi khi hết` | checkbox | Bind existing auto-buy flag; no behavior change |
| `SET-11` | `Số mồi mỗi lần mua (1–50)` | integer spinner | **1..50 inclusive**, no decimals/text/empty Save; exactly existing purchase-quantity setting |
| `SET-12` | `Bán cá khi về shop` | checkbox | Bind existing sell-at-shop flag |
| `SET-13` | `Bán cá lúc 23:57` | checkbox + fixed time label | Existing timed-sell flag and fixed `23:57`; if real code supports editable time, keep that existing UI/contract, otherwise time is read-only |
| `SET-14` | `Tự động khác` | optional group | Show **only** actual existing configurable properties; do not turn commentary text into settings |
| `SET-15` | `Hiển thị & nhật ký` | optional group | Show **only** options backed by existing model; don't invent auto-open-log/history toggles |

If purchase checkbox is off, the purchase amount spinner may be disabled **if** current semantics permit; preserve value in draft/config. Read-only and disabled field styling must remain readable.

### 2.3 Validation and persistence

| Scenario | Expected behavior |
|---|---|
| Buy amount `0` / `51` / negative | Reject Save, inline `Vui lòng nhập số từ 1 đến 50.` |
| Buy amount text/decimal/empty | Reject Save, focus spinner and show validation |
| Toggling checkboxes then Cancel | Persisted/current values untouched; reopening restores previously saved state |
| Toggle + valid amount + Save | Use existing save API; persisted config survives application restart |
| Runtime disallows changing a field | Disable only affected field, show concise explanation; don't mutate active engine configuration |
| Save during config write failure | Keep dialog open; show error and preserve user edits; no fake success |
| Engine state changes while modal open | Refresh editability/state; avoid corrupting pending settings; don't auto-save |

If original code binds widgets immediately to live values, Codex must design an adapter or document a safe alternative preserving the old semantics; never tell the user Cancel discarded changes if changes were already applied.

---

## 3. Mode panel tabs (`MODE-*`)

### 3.1 Shared tab behavior

| ID | Action / state | Expected |
|---|---|---|
| `MODE-01` | Click `Nhiệm vụ game` | Show mission panel, highlight exactly one active tab, keep other draft/UI states intact |
| `MODE-02` | Click `Câu tự do` | Show free-fishing panel, preserve current zone/checkbox selections |
| `MODE-03` | Click `Tự đặt mục tiêu` | Show fish catalog list, preserve checks/focus and target order |
| `MODE-04` | Keyboard focus tabs | `Tab` / arrows if supported by toolkit; visible focus ring, no accidental Start |
| `MODE-05` | Switch tab while RUNNING | **No automatic engine mode switch.** If existing app explicitly switches mode on tab changes, protect via its existing validation/transition and reflect true result |
| `MODE-06` | Return to previously visited tab | No duplicate callbacks, no discarded values or reloaded fake data |

Tabs are **navigation**, whereas mode activation is governed by the existing engine contract. Audit actual interaction before binding tab click to a domain command.

### 3.2 Mission panel (`MISSION`)

- One principal checkbox: `Tự động đọc và làm nhiệm vụ hiện tại` (existing flag).
- If checkbox controls execution mode, reflect original mode exclusivity/requirements; do not allow contradictory engine activations.
- Remove duplicated long help paragraph; keep a concise hint **only if it communicates true behavior**.
- If engine provides meaningful no-mission/read-error states, show small `Chưa có dữ liệu nhiệm vụ` / actual reason; not a fabricated mission table.
- Do not add extra controls or mission algorithm.

| ID | Event | Result |
|---|---|---|
| `MODE-10` | Check/uncheck mission flag | Route to current existing configuration/mode handler, subject to engine editing rules |
| `MODE-11` | Mission OCR update | Refresh progress card safely; never calculate invented rewards/progress |
| `MODE-12` | Read mission failure | Preserve engine state and expose existing diagnostic when applicable |

### 3.3 Free-fishing panel (`FREE`)

- `Câu tự do` checkbox (if the current app supports it).
- Zone selector `Khu câu tự do` or existing accurate label, with **actual** regions/options and default.
- Remove redundant title/instructions; use a concise label and selection control.

| ID | Event | Result |
|---|---|---|
| `MODE-20` | Toggle free-fish checkbox | Existing mode/flag API only, no new enablement behavior |
| `MODE-21` | Open zone combo | List real configured zones; no sample zones injected |
| `MODE-22` | Select zone | Update actual config/mode based on existing semantics; preserve selection on navigation |
| `MODE-23` | No available zone options | Disabled/read-only control with explanatory state; no blank interactive fake combo |
| `MODE-24` | Switch zone while RUNNING | Allow/deny based on engine policy, not arbitrary UI assumption |

### 3.4 Custom target panel (`CUSTOM`) — catalog list

**Columns exactly:** `Chọn` | `Loại cá` | `Khu câu`. **No `Số con` column**; quantity changes only in Column 2 toolbar. The table is as tall as its available catalog rows, without an inner vertical scroll. If extra species appear, the **entire window page** scrolls.

- Fish icon displayed next to matching species label only when actual ID/name resolves; fallback generic fish icon or no icon.
- Current known visual labels may include: Cá chép vàng, Cá lóc, Cá chim, Cá ngựa, Cá lòng tong, Cá nóc, Cá đuối, Cá lia thia, Cua, Cá rô. **Use authoritative catalog; mockup is not source for species or location assignment**.
- One checkbox per row. Checking/unchecking uses **existing target inclusion semantics**; clicking row content can focus it for Column 2 actions without toggling checkbox. Checkbox checked state and keyboard selected row are different concepts.
- No duplicate quantity action toolbar in Column 1.

| ID | User action | Expected | Edge cases |
|---|---|---|---|
| `GOAL-01` | Check fish row | Include fish via existing target API and update progress card using same model | Reject unsupported fish/locked edits according to engine |
| `GOAL-02` | Uncheck fish row | Remove/deactivate via existing API and update progress accordingly | Do not erase unrelated completed catch stats |
| `GOAL-03` | Click row label/focus | Set focused fish/target id for contextual action toolbar, highlight row | Do not accidentally toggle checkbox |
| `GOAL-04` | Keyboard navigate rows | Move focus with visible indicator and appropriate access keys | Preserve scrollability of page |
| `GOAL-05` | Catalog changes from engine/config | Reconcile rows by **stable fish identifier**, preserve focus and current selections where valid | No index-based wrong-fish updates |
| `GOAL-06` | Empty catalog | Show `Chưa có danh sách cá.` and no misleading selectable rows | Respect actual data source |

### 3.5 Custom goal action toolbar — located in Column 2 (`GOAL-*`)

Layout directly under `Cá đã câu & tiến độ nhiệm vụ` progress list, in this order:  
`[Số lượng] [Đặt số lượng] [↑] [↓] [Reset mục tiêu]`.

- **Target of the action:** selected/focused fish or set of targets according to **current** application semantics. Prefer a single focused fish row for up/down and explicit selection for quantity to prevent ambiguity. If original implementation uses selected checkboxes in bulk, preserve that and make target set visually clear. Never pick an arbitrary first row.
- Quantity is **target fish quantity**, not bait quantity. Read numeric range from existing target model, not settings `1..50`.
- Where useful, concise state such as `Đang chỉnh: Cá lóc` may appear inside toolbar (not as a redundant status label) to avoid editing wrong target.

| ID | Trigger | Preconditions | Expected result | Failure behavior |
|---|---|---|---|---|
| `GOAL-10` | Type fish target quantity | Toolbar applicable, input editable | Update pending numeric input only until Set if existing flow uses explicit apply | Invalid state highlighted, no domain changes |
| `GOAL-11` | Click `Đặt số lượng` | Valid number, clear target set, engine allows edit | Call exact existing quantity update; synchronize model, progress and UI | Show specific validation reason; never update wrong fish |
| `GOAL-12` | Click `↑` | Target row selected/focused, not already first, reorder supported | Existing reorder-up handler and update both lists atomically | Disabled if no target / first row / blocked during run |
| `GOAL-13` | Click `↓` | Target selected, not last, reorder supported | Existing reorder-down handler | Disabled at last row/no target |
| `GOAL-14` | Click `Reset mục tiêu` | Existing reset behavior supported; valid permission | Call existing reset exactly; update target & progress views | Confirm only if old behavior does; never reset session counters unexpectedly |
| `GOAL-15` | Switch from CUSTOM tab | Toolbar no longer applicable | Hide or disable controls; preserve pending values according to existing UX | No auto-apply silently |
| `GOAL-16` | Engine updates progress during edit | Data refreshed | Preserve focused target and uncommitted input when safe | Do not overwrite user's currently typed number |

**If existing target semantics differ:** write the actual mapping in `IMPLEMENTATION_PLAN.md`; do not replace model logic to make the mockup easier.

---

## 4. Progress table and activity log (Column 2)

### 4.1 Progress (`PROG-*`)

| ID | Data state | UI |
|---|---|---|
| `PROG-01` | No relevant fish/mission data yet | Small empty state `Chưa có dữ liệu.` rather than fake 0/90 rows |
| `PROG-02` | Fish target has actual goal/count | `Tên cá` + `current/goal` and optional real progress indication |
| `PROG-03` | Count only, goal unavailable | Show actual count and `—` goal; do not infer from screenshot |
| `PROG-04` | Mission progress available | Show real mission/fish progress using domain mapping; same panel, no invented calculation |
| `PROG-05` | New fish event | Update correct stable fish id and stats; preserve row order/selection and input draft |
| `PROG-06` | Many fish rows | Expand list naturally; outer page scrolls; no nested fish-table vertical scrollbar |
| `PROG-07` | Engine read failure | Retain last reliable value or show unknown based on real data policy; don't masquerade unknown as zero |

Row rendering must be efficient and not recreate entire card per tick. Progress section remains visible across all 3 tabs, while custom toolbar is contextual.

### 4.2 Activity log (`LOG-*`)

| ID | Action/state | Expected |
|---|---|---|
| `LOG-01` | Engine produces log event | Append original message via GUI-main-thread dispatcher with existing timestamps if available |
| `LOG-02` | Frequent logs | Batch queued updates; bounded UI-memory strategy (do not truncate actual log file) |
| `LOG-03` | User scrolls upward | Prefer pause auto-scroll until near bottom, to preserve reading position |
| `LOG-04` | User returns to bottom | Resume auto-scroll on new logs |
| `LOG-05` | Error/warning message | Readable color hierarchy with text prefix; color never sole indicator |
| `LOG-06` | Open folder topbar button | Open exact existing log directory without changing filenames/path |
| `LOG-07` | Empty log | Quiet empty state `Chưa có hoạt động.` |
| `LOG-08` | Engine error/stop while logging | Continue rendering accessible errors without UI crash |

**Allowed nested scrollbar:** activity log only (also modal if settings grow). Neither custom target list nor progress table receives an independent vertical scrollbar.

---

## 5. Overview and ticket statuses (Column 3)

### 5.1 Overview tiles (`MET-*`)

| ID | Tile | Data behavior |
|---|---|---|
| `MET-01` | `Quăng` | Existing casting count; update from engine, not button click |
| `MET-02` | `Cắn câu` | Existing bite count |
| `MET-03` | `Trật` | Existing miss count; **not** `Trượt` unless app's real label differs |
| `MET-04` | `Mồi mua` | Existing metric semantics (transactions or units), retain meaning and display |
| `MET-05` | `Sinh thái` | Existing ecological bait/area info; show `Chưa xác định` if unknown |
| `MET-06` | `Bến tàu` | Existing current dock/zone info; show `Chưa xác định` if unknown |
| `MET-07` | Engine snapshot refresh | Update changed values on main GUI thread, no reset on tab switch |
| `MET-08` | Stop/restart | Retain/clear counters strictly per original app rules |

Tiles layout: 2-up grid when sufficient width, otherwise 1-up without clipping. Color/shape reinforces label but is not the only cue.

### 5.2 Ticket availability (`TKT-*`)

Four read-only tiles, in this order: `Vé câu cá rô`, `Vé câu cá mập`, `Vé câu cá lóc`, `Vé câu bến tàu`.

| ID / state | Authoritative information | Label | Secondary text | Rule |
|---|---|---|---|---|
| `TKT-01 PRESENT_VALID` | Explicitly confirmed present + valid expiry | `Có` | `Còn 2h 30m` (computed from real expiry) | No hardcode; local clock/timezone semantics from existing engine |
| `TKT-02 ABSENT` | Explicitly confirmed absent | `Không` | `—` | Do not infer absence from unreadable screenshot |
| `TKT-03 UNKNOWN` | No parser/data contract yet or not scanned | `Chưa xác định` | `—` | Default fallback for new ticket fields until confirmed |
| `TKT-04 EXPIRED` | Explicit expiry passed | `Hết hạn` or `Không` per app convention | `—` | Never show negative remaining time |
| `TKT-05 READ_ERROR` | Parser/check failed | `Không thể kiểm tra` or `Chưa xác định` | Short reason if available | Do not revert to `Không` |
| `TKT-06 REFRESH` | New ticket snapshot or clock update | Update status and remaining time | Recompute from real expiry | One timer tick source; avoid multiple timers per ticket |

**Unimplemented ticket backend:** Render the four cards with unknown status and document `TicketSnapshot` contract that future game reader would need (`ticket_type`, `presence: yes/no/unknown`, `expires_at` if known, `read_at`). **Do not implement game OCR/automation to discover tickets as part of UI redesign.**

---

## 6. UI-state vs runtime-state cross-effects

| Situation | Expected UI behavior |
|---|---|
| Switch mode tab with unsaved Settings draft | Modal usually blocks background; draft persists until Save/Cancel |
| Click settings during RUNNING | Open safely; lock only fields the engine cannot update while running |
| Stop while Settings modal open | Modal remains consistent or closes via existing lifecycle policy; never save invalid out-of-date state |
| Switch custom tab while RUNNING | Follow existing engine mode switch rules; UI-only tab switching must not mutate execution |
| Fish target checked during RUNNING | Allow only if engine supports live edits; else explain disabled and keep state unchanged |
| New catch arrives while quantity input focused | Update count/progress, preserve typing/focus; do not wipe text mid-edit |
| Resize to 1024×720 with long target list | Global dashboard scroll, controls reachable, no horizontal clipping |
| Ticket read fails | `Không thể kiểm tra`/`Chưa xác định`, never a fabricated `Không` |
| Timer updates while modal open | Same single authoritative timer, no duplicate update loops |
| Window close during worker shutdown | Honor existing cleanup and thread termination, avoid freezing Tk/Qt main thread |
| Change purchase amount while buy toggle off | Preserve numeric value, no accidental purchase |
| No target selected and Set/Up/Down pressed | Action disabled or concise feedback; no implicit first-target mutation |

---

## 7. UX details and visual states

### 7.1 Consistent controls

- Checkbox dimensions and labels consistent across Settings, Mission, Free and Custom tables; checked filled-primary, unchecked outline, disabled state still legible.
- Interactive control states: `default`, `hover` (where supported), `focus-visible`, `pressed`, `disabled`, `validation-error`.
- Disabled actions must not produce side effects. Use affordances rather than allowing click then ignoring.
- Keyboard support: Tab traversal; Space toggles focused checkbox/button; Enter invokes focused primary action where toolkit permits; Escape closes modal safely; no invented global shortcuts.
- Minimum recommended button hit height 38–44 px, standard 8–12 px gaps; semantic labels with icons optional.

### 7.2 Information density

- Remove repeated tab title/header where there is no value, especially mission/free simple panes.
- Keep a compact useful hint only when it clarifies required target selection/ordering.
- Never hide relevant errors just to simplify UI.
- Avoid huge empty space with fixed-height cards: target table grows naturally; cards may align visually but can have differing heights.
- Make 35/40/25 layout proportional **after** margins/gaps.

### 7.3 Asset usage

- Banner: prefer seamless background with separate character/shop decoration and real brand text; do not embed Windows title buttons from flattened mockup.
- Fish icons: matched by fish **identifier**, never table index. If mismatched/low-quality crop, use generic fish icon until corrected asset.
- `assets/fish-icons-clean/` (if supplied) contains corrected PNG reference crops and is preferred over older `assets/fish-icons/`.
- Cards, checkboxes, buttons and modal are **live widgets**, not static PNGs.
- Source art may be concept-generated/game-inspired; do not assert it is official game artwork or reusable outside appropriate rights.

---

## 8. Suggested presenter/view interfaces (illustrative, NOT mandatory)

These represent intended boundaries only; adapt names/types to real code rather than forcing a second architecture:

```python
class UiSnapshot:  # conceptual data projection
    session_state: str
    elapsed_seconds: int | None
    active_tab: str
    stats: dict
    targets: list
    progress: list
    tickets: dict

# Conceptual event routing — connect to existing APIs:
# on_start_clicked()          -> existing_engine.start()
# on_pause_or_resume_clicked()-> existing_engine.pause()/resume()
# on_stop_clicked()           -> existing_engine.stop()
# on_open_log_clicked()       -> existing_log_service.open_folder()
# on_settings_save(draft)     -> existing_config_service.validate_and_save()
# on_target_changed(fish_id)  -> existing_targets.update()
# on_target_reordered(...)    -> existing_targets.move()
# on_ui_refresh(snapshot)     -> rendering only (no engine commands)
```

Implementation must not introduce a second authoritative `session_state` that drifts from engine state.

---

## 9. Manual acceptance / QA scripts

Use these step-by-step scripts alongside automated tests:

| Test | Steps | Expected |
|---|---|---|
| `QA-01` Initial layout | Launch at 1536×1024 | Banner + topbar + 3 body columns; no old left rail/sidebar |
| `QA-02` Tabs | Visit all three tabs, switch back | Correct content, preserved inputs and state, no phantom bot commands |
| `QA-03` Settings Cancel | Open, change toggles/amount, Cancel, reopen | Saved config unchanged |
| `QA-04` Settings Save | Save valid amount, restart | Persisted config; no data loss |
| `QA-05` Validation | Try 0, 51, text, empty bait amount | Save blocked; inline error and focus |
| `QA-06` Fixed schedule | Open selling group | 23:57 shown fixed unless backend genuinely supports editing |
| `QA-07` Target table | Load full supported catalog | Exactly Chọn/Loại cá/Khu câu; all items visible via page scroll only |
| `QA-08` Target controls | Select row, set amount, move up/down, reset | Existing target model updated correctly; no wrong fish |
| `QA-09` No selection | Clear focus/selection and use target actions | Appropriate disabled state or explanatory feedback |
| `QA-10` Session run | Start once, try double click; Pause/Resume/Stop | One worker/session, correct controls, clock semantics preserved |
| `QA-11` Live updates | Let log/counters/progress change | No freezes, counts match engine; list focus not lost |
| `QA-12` Tickets | Start app without ticket parser/source | All four show Chưa xác định, never fake Có/Không/countdowns |
| `QA-13` Tickets available | Feed known test snapshots of present/absent/expired | Correct statuses/countdown, no negative durations |
| `QA-14` Resize | 1280×800, 1024×720, zoom 125/150% | No clipped essential actions; scroll main content |
| `QA-15` Long data | More than ten species/progress rows | Tables expand with outer scroll; no table scrollbar |
| `QA-16` Log usability | Large burst, manually scroll up then resume bottom | Stable input/UI, correct folder path, readable logs |
| `QA-17` Failure handling | Simulate config-save error, stop error, ticket read error | Truthful feedback; no fake success; no app crash |
| `QA-18` Shutdown | Close app during run, pause, modal, and stop | Existing engine graceful behavior retained, no dangling update callbacks |
| `QA-19` Packaging | Build Windows app using existing process | Assets load when frozen and on other DPI/scales |
| `QA-20` Regression | Run existing unit/integration tests | Fishing/OCR/scheduler untouched; failures analyzed and reported |

## 10. Done criteria / explicit non-goals

**Done when:** actual running app visually approximates both v2 mockups; new 3-column layout + popup + target toolbar location implemented; session lifecycle and all three modes wired to real model; four ticket cards truthfully represent available/unknown data; no extra inner scroll in fish tables; tests and Windows packaging checked or missing environment clearly reported.

**Not done / NOT requested:** automating new ticket discovery, changing fish-catching strategy, adding unsupported new preferences, automatically purchasing tickets, inventing fish zones/target values, redesigning game itself, network dependencies, or replacing engine/scheduler.
