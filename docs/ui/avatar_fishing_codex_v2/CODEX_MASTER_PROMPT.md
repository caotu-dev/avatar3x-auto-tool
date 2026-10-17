# CODEX MASTER PROMPT — Avatar Fishing Bot / UI Redesign v2

> **Cách dùng:** Mở Codex ở thư mục gốc repository Python, chép toàn bộ phần từ **BEGIN PROMPT** đến **END PROMPT** vào một yêu cầu. Giải nén bộ `avatar_fishing_codex_v2.zip` vào `docs/ui/avatar-fishing-v2/` trước khi gửi prompt (hoặc điều chỉnh đường dẫn thực tế). Đây là **yêu cầu triển khai**, không phải yêu cầu viết kế hoạch suông.

---

## BEGIN PROMPT

You are a **senior Python desktop GUI engineer + UX implementation engineer + QA reviewer**. You are working **inside the existing Avatar Fishing Bot source repository**. Implement the **approved UI redesign v2** as a working, tested desktop application, matching the screenshots closely without changing the automation/business logic.

**Instructions:** Inspect the repository first, plan briefly, then implement and validate. Do not stop at a proposal, static mockup or incomplete widget skeleton. If a detail differs from the screenshot and actual code, preserve the code's true behavior and explain the visual adaptation.

### 0. Read and rank the references

Find the attached design bundle (default `docs/ui/avatar-fishing-v2/`; if it is located elsewhere, use the actual location). Read in this **priority order**:

1. `CODEX_MASTER_PROMPT.md` — this specification and engineering contract.
2. `UI_INTERACTION_FLOW.md` — **authoritative** interaction/state/validation specification; IDs `FL-*`, `ACT-*`, `SET-*`, `MODE-*`, `GOAL-*`, `MET-*`, `TKT-*`, `LOG-*`.
3. `assets/references/dashboard_main.png` — approved dashboard composition and theme.
4. `assets/references/dashboard_settings_popup.png` — approved settings modal reference.
5. `CODEX_ASSET_MAPPING.md`, `asset_registry.json`, `assets/README.md` — PNG crop mapping and limitations.
6. `DESIGN_TOKENS_V2.json` — practical color/size/spacing/layout values.

**This v2 spec supersedes older** `UI_SPEC.md`, `CODEX_PROMPT.md`, `CODEX_IMPLEMENTATION_NOTES.md` **wherever they conflict.** In particular: no permanent left settings column, no navigation sidebar, three content columns, actions in the progress card, and no internal scrolling in fish tables.

**Do not treat mockup text/data as application truth.** Counts, fish progress, ticket availability/durations, zone labels, shortcuts and settings toggles shown in images are **illustrative**, not actual game state.

### 1. Non-negotiable constraints

- Preserve all currently working engine behavior: automation, fishing flow, OCR/image recognition, screen coordinates, click/key automation, scheduling, inventory/shop, bait buying, fish selling, mission detection, free fishing, custom goals, retries, exception handling, internal state machine, persistence, log paths and Windows packaging.
- Do not rewrite or refactor the bot engine under the guise of a UI redesign. Only narrow adapters needed to expose *existing* state/events or route callbacks to the new UI are permitted; document these explicitly.
- Preserve exact Vietnamese text labels for real functionality (e.g. **Quăng**, **Cắn câu**, **Trật**, **Mồi mua**, **Nhiệm vụ game**, **Câu tự do**, **Tự đặt mục tiêu**). No untranslated controls.
- **Inspect the actual GUI toolkit** (Tkinter/ttk, CustomTkinter, PySide6, etc.) and reuse it when practical. Do not migrate frameworks/install extra dependencies solely for visual styling unless existing toolkit cannot meet a critical requirement, and report the tradeoff first.
- UI widgets must be functional native/custom widgets, not a single screenshot masquerading as UI. Do not ship hard-coded metrics/locations/progress/events.
- Reuse config schema, persistence semantics, execution rules and actual option lists. Do not assume `23:57` is editable: if the current engine supports only the fixed schedule, show it as fixed read-only text, not an editable time picker.
- Do not invent features from mockups: F8/F9/F10 shortcuts, reset counters, delete history, enable new automatic behavior, edit fish ticket expiry, auto-open log, change locale, new fishing regions, and new background services **are not approved solely by being illustrated**. Only expose them if supported by existing behavior or explicitly requested in this spec.
- For the **four newly requested ticket statuses** (cá rô, cá mập, cá lóc, bến tàu): discover whether authoritative data/expiry exists. If it does, display it. If it does **not**, show `Chưa xác định` / `—` rather than fake `Có`, `Không`, or countdowns; document the missing engine data contract. Never pretend to have extracted or recognized game data.
- Fully offline; no CDN, remote fonts, network images, webview, telemetry, or new account requirement. Do not embed private game/user data in screenshots/tests. Handle image licensing/asset provenance conservatively.

### 2. Phase 0 — repository audit (required BEFORE edits)

Inspect and write a concise `docs/ui/avatar-fishing-v2/IMPLEMENTATION_PLAN.md` covering:

| Audit subject | Locate/confirm |
|---|---|
| Bootstrap/UI | Entry point, toolkit/version, theme system, window, DPI handling, layout tree |
| State | Source of truth for idle/starting/running/pausing/paused/stopping/stopped/error |
| Controls | Existing Start/Pause/Resume/Stop handlers, valid transitions and debounce protections |
| Three modes | Tab-selection state vs enabled-mode state; persisted defaults; permission to change mid-session |
| Settings | Storage/read/write/defaults, purchase toggle + amount (1–50), shop sell, timed sell 23:57 |
| Custom targets | Existing fish catalog, zone mapping, selected targets, quantity, order and reset semantics |
| Progress | Caught/goal rows, mission progress, list refresh cadence and counter data sources |
| Overview | Quăng, Cắn câu, Trật, Mồi mua, Sinh thái, Bến tàu sources |
| Tickets | 4 ticket status/expiry sources or clearly state missing data |
| Logs | Log stream, UI scheduler, retention, open-directory command |
| Thread model | Worker/background thread → UI dispatcher, cancellation and shutdown |
| Packaging | Windows entry point, bundled assets, frozen-app resource loading, tests |

Deliver a short mapping of `UI widget -> existing state/property -> handler/callback` for all important controls. Favor minimal refactor into `presentation/view`, `view_model/adapter`, `assets/theme`. **Proceed with implementation after the audit**, adjusting file paths to actual repository patterns.

### 3. Exact layout & composition

#### 3.1 Desktop shell

At wide size (~1536×1024), build:

```text
┌──────────────────────────── continuous illustrated banner ────────────────────────────┐
│  [original Avatar-inspired art]  AVATAR • FISHING BOT            [scene/SHOP art]    │
├────────────────────────────── horizontal session control bar ────────────────────────┤
│ [⚙ Thiết lập] [▶ Bắt đầu] [Ⅱ Tạm dừng] [■ Kết thúc] [📁 Mở thư mục log] [⏱ 00:32:29] │
├──────────────────────────── main body (no sidebar/settings rail) ────────────────────┤
│           COL 1 — 35%          │            COL 2 — 40%           │   COL 3 — 25%     │
│ [Nhiệm vụ game|Câu tự do|      │  Cá đã câu & tiến độ nhiệm vụ    │ Tổng quan phiên   │
│  Tự đặt mục tiêu]              │  [live progress table]          │  câu: 6 metrics   │
│ [active mode content]          │  [quantity/order/reset toolbar] │                   │
│                               │  Hoạt động [live log]            │ Vé câu: 4 cards   │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

- Width ratio **35 / 40 / 25 of usable body width after margins and gutters**, not the whole window. Use flexible layout weights; do not hardcode screenshot pixel positions.
- Header: ~176–180 px; control bar immediately below; content area background ice-blue; cards white, light stroke, soft 12–14 px radii, navy headings.
- The previous left column (settings + timer + session buttons) **must disappear**. There is **no sidebar**. Timer appears only in top bar.
- At wide sizes (recommend ≥ 1400 px): maintain exact 3-column ratio. At narrower sizes preserve usability; e.g. 1200–1399 keep 3 columns if cells remain usable, otherwise put right overview below main columns; at ~1024×720 prefer 2 columns plus overview below, and use the page's vertical scrolling. Record your chosen breakpoint.
- Windows title bar is native. Don't draw fake minimize/maximize/close buttons from a cropped banner.
- Do not allow layout clipping when resizing or DPI scaling (100%, 125%, 150%). Use a single **outer vertical scrolling surface** when content exceeds window height. Exception: the **activity log may have its own vertical scrollbar**; fish tables must not.
- Header artwork: avoid hard seams when joining image crops; do **not** duplicate rasterized text over live title. If crops look poor at runtime, use a gradient + left/right decorative PNGs and real text. Do not sacrifice layout for visual assets.

#### 3.2 Top session control bar

Order: `Thiết lập` | `Bắt đầu` | `Tạm dừng` | `Kết thúc` | `Mở thư mục log` | timer aligned right (`HH:MM:SS`).

- Use green for Start, blue/neutral for Pause, red outline/tint for Stop, outline for Settings/Log.
- Native handlers for actions (existing callbacks). Use active/disabled state based on the *real* session engine. Prevent duplicate starts and simultaneous conflicting commands.
- Button label for Pause can change to `Tiếp tục` only if the engine truly supports resume; never fake it.
- Remove duplicate prose `Đang chạy`, `Phiên câu đang hoạt động`; do not remove required error/safety messages. Show actionable errors via unobtrusive message when needed.
- Timer derives from authoritative session clock/elapsed state, remains consistent through pause/resume; if semantics unclear, preserve existing display exactly.
- Keyboard shortcuts only if already implemented; no invented F8/F9/F10.

#### 3.3 Column 1 — mode switcher and content (35%)

Three tabs along top: `Nhiệm vụ game`, `Câu tự do`, `Tự đặt mục tiêu`. Exactly one content pane is visible, but do **not** accidentally change engine mode activation semantics when tab is merely visited.

- **Game mission:** one clear checkbox `Tự động đọc và làm nhiệm vụ hiện tại` bound to existing behavior. Remove duplicated title/long explanatory paragraph unless necessary. Keep a brief inline error/empty state if data cannot be read and that state is exposed.
- **Free fishing:** existing `Câu tự do` checkbox + labeled zone selector. Use actual options, default and existing meaning; remove redundant instruction text. If selector is disabled until enabled, preserve that behavior; if not, don't impose it arbitrarily.
- **Custom targets:** a real multi-row table with only `Chọn | Loại cá | Khu câu`. Checkbox style same size/appearance as modal settings. **Remove `Số con` column.** Row height should fit readable fish icon + species + zone. No internal table vertical scrollbar or fixed 3-row viewport. All fish entries shown using natural list height; if needed scroll **the main page**. Keep row selection/focus visually distinguishable from check/uncheck.
- Fish catalog comes **only from code**. The seven newly illustrated species must be mapped by actual existing names/IDs when available: Cá lòng tong, Cá nóc, Cá đuối, Cá lia thia, Cua, Cá rô, Cá chép vàng. The prior examples (Cá lóc, Cá chim, Cá ngựa) remain if present. If a fish does not exist in catalog, do not inject a fake automation target just to match an icon.
- The mode panel should grow naturally with its content. All interactive controls are real editable widgets with focus and keyboard access.

#### 3.4 Column 2 — progress & activity (40%)

Top card `Cá đã câu & tiến độ nhiệm vụ`:

- Dynamic progress table columns `Loại cá | Số lượng / Tiến độ` using authoritative counts/target limits. 0/90 means progress when target exists, not proof of fish caught. For missing target/mission semantics, display accurate actual values or `—`.
- No vertical scrollbar inside fish progress table; all current rows visible; **page** may scroll.
- Target actions **live here, not in Column 1**: editable integer quantity input + `Đặt số lượng` + `↑` + `↓` + `Reset mục tiêu`. Enabled/disabled rules derive from existing target model and currently focused/selected fish. Validate integer/range with existing domain rules (do not assume the 1–50 bait range applies to fish target quantity).
- If a command needs a specific fish selection, show clear focus/selected row and never silently modify the wrong fish; when no eligible target is selected, disable affected actions or show a concise reason. Preserve exact existing row-order behavior.
- These controls are **mode-specific**: when on Game mission or Free fishing, keep progress readable and hide/disable actions not meaningful for the active mode; do not render inert clickable controls.

Bottom card `Hoạt động`:

- Stream **real** log/activity, newest behavior consistent with existing implementation; fixed-height inner scrolling is allowed **only here**. Monospace font 11–12 px, readable contrast; long lines don't break layout; no expensive append/re-render loop.
- Do not log fabricated events, credentials, tokens, OCR crops or sensitive paths. Keep log directory opener working.

#### 3.5 Column 3 — overview & tickets (25%)

- Section `Tổng quan phiên câu`: **6 existing tiles** `Quăng`, `Cắn câu`, `Trật`, `Mồi mua`, `Sinh thái`, `Bến tàu` with genuine dynamic data, no extra timer.
- Section `Vé câu (hiệu lực)`: **4 new status tiles** `Vé câu cá rô`, `Vé câu cá mập`, `Vé câu cá lóc`, `Vé câu bến tàu`.
- Ticket status visual states: `Có` + truthful time remaining *when known*, `Không` *only if absence is confirmed*, `Chưa xác định` otherwise. Expired is not available; avoid negative time. Each ticket may refresh from existing state/events, not from hardcoded demo countdown.
- Do not add game purchasing/activating tickets; **display only** unless those actions already exist.
- Responsive metric/ticket grid must not squeeze labels into unreadable text; fall back to one tile per row for narrow right rail.

### 4. Settings modal — required

Click `Thiết lập` on top bar -> centered **modal popup**, app background dimmed, keyboard focus within modal, Escape/close X handled safely, no accidental clicks to app behind modal.

Suggested semantic groups (render groups only when supported by existing settings):

1. **Mồi & mua sắm**
   - `Mua mồi khi hết` checkbox.
   - `Số mồi mỗi lần mua (1–50)` integer stepper, enabled/read-only mapping based on current engine settings; validate `1..50` only for bait purchase size.
2. **Bán cá**
   - `Bán cá khi về shop` checkbox.
   - `Bán cá lúc 23:57` checkbox; if 23:57 is fixed, show fixed time clearly and **do not** display fake editable picker.
3. **Tự động khác** and **Hiển thị & nhật ký**
   - Display only **actually configurable options already in code**; don't convert explanatory notes (e.g. auto-switch region or pause-after-round) into new independent toggles without existing backing state.

Modal actions: `Hủy` and `Lưu thay đổi`. `Khôi phục mặc định` is shown **only if** a safe existing default/restore contract is available; otherwise omit. Implement **draft state**: opening clones persisted/current values; edits do not take effect until Save (unless engine cannot support atomic deferred commit, in which case preserve current semantics and explicitly document adaptation); Cancel/X/Escape discards unsaved edits. On Save, validate, commit using existing config APIs, update UI, close and persist. On invalid data, keep dialog open, show field-level error and focus it.

If modal opens during a session, respect existing mid-run setting update restrictions: field-level disabled with concise reason if unsafe. Do not silently change the running bot's execution. Test closing popup during/after a stop event.

### 5. Visual system: use tokens, not magic numbers

Use `DESIGN_TOKENS_V2.json` (and adapt to GUI toolkit). Recommended: Segoe UI; deep navy `#10245C`, primary blue `#135BFA`, surface `#FFFFFF`, app background `#EFF6FF`, divider `#D6E4FA`, success `#42AF25`, danger `#E11D48`, text-secondary `#526DA7`; spacious 8/12/16 px rhythm; controls min 38–44 px high; visible focus ring, readable disabled colors. Large timer monospaced tabular digits. The screenshot is a **visual target**, not an excuse to bake form controls into images.

**Asset quality warning:** previous crop packs are derived from a **flattened raster mockup** and several small icons may contain neighboring text, background, or wrong cropping. Inspect `assets/ASSET_PREVIEW_SHEET.png` and each icon **before** including it. Prefer clean corrected assets under `assets/fish-icons-clean/` if present; otherwise recreate simple vector/icon shapes using existing toolkit or use a simple text fallback. Never blindly load all `asset_registry.json` entries as production-perfect assets. Keep fonts and artwork local; do not fetch externally.

### 6. State, update & error-handling contract

Follow `UI_INTERACTION_FLOW.md` precisely, especially its session transition table and action enablement rules. In particular:

- A session has a single engine-owned authoritative lifecycle. UI does not derive `running` solely from timer value or button state.
- Worker threads must never directly mutate GUI widgets. Use `root.after()` / thread-safe queue / Qt signal-slot, as appropriate for actual framework. Batch/debounce rapid updates and dispose UI subscriptions when closing.
- Tab switching must never silently start, stop, change modes or reset progress without an existing domain command and safe state transition.
- No duplicate timers or leaked scheduler jobs when opening/closing settings, switching modes or restarting a session.
- Start/Stop repeated clicks are safe, idempotent according to engine, and don't create multiple worker loops.
- Distinguish confirmed `Không`, unknown `Chưa xác định`, and unavailable temporary failure for tickets/zone/status.
- Show explicit error feedback when an action fails; retain data and app usability.
- The fishing table list, progress rows and summary must reflect **one consistent authoritative model**, not separate mock arrays.

### 7. Engineering quality & incremental tasks

Perform these tasks in order (small cohesive diffs, preserve commit history):

1. Repository audit + `IMPLEMENTATION_PLAN.md` and mapping table.
2. Theme/tokens adapter, working layout shell: banner + top bar + 3 columns + responsive/outer scrolling.
3. Session controls/timer wiring and existing engine state mapping.
4. Three tabs and content; custom fish full-height table and consistent checkbox styles.
5. Progress table + relocate target action buttons + preserve handlers, selection and order.
6. Overview tiles + four ticket status cards (real/unknown data contract).
7. Activity log and open-log-directory event binding.
8. Settings modal with draft/save/cancel, existing config storage, validation, focus/disable rules.
9. Art/icon audit and final polish, screenshot comparison, no extra dead controls.
10. Tests, README/change notes and final QA.

Use maintainable components/classes and a thin view-model/presenter. No unnecessary mega-file rewrite. Do not copy the screenshot into the entire app background. Match exact labels only where confirmed; otherwise inspect and preserve original domain labels.

### 8. Acceptance tests (implement where feasible)

At minimum cover:

- `AT-01`: all 3 tabs render correct mode controls; switching tabs does not spuriously call engine or reset selected values.
- `AT-02`: settings modal open/edit/cancel does not persist; open/edit/save validates and persists current settings; invalid bait amount (0, 51, non-integer) rejected.
- `AT-03`: fixed 23:57 behavior preserved; picker does not appear unless truly editable.
- `AT-04`: top controls valid/invalid per state and repeated rapid clicks do not duplicate sessions.
- `AT-05`: timer correct for start/pause/resume/stop according to current engine semantics; only one timer updater.
- `AT-06`: custom table has only 3 columns and **no inner scroll**; rows remain reachable with outer scroll.
- `AT-07`: quantity, up/down and reset in progress card target the intended fish and preserve existing order/quantity behavior; handle no selection.
- `AT-08`: data-driven progress/overview update without UI-thread violations or frozen app.
- `AT-09`: ticket cards distinguish unavailable vs unknown; no mock counts or expiry countdown.
- `AT-10`: log view streams, auto-scroll only when reader is near bottom if practical, and existing folder opener opens correct path.
- `AT-11`: layout usable at 1536×1024, 1280×800 and 1024×720 with OS DPI variations; no clipped actionable controls.
- `AT-12`: Windows packaging still resolves local banner/icons from project or frozen application correctly.
- `AT-13`: close dialog/app during running/paused/stopping without blocking UI or leaking worker/event handlers.

If a GUI display/screenshot facility is unavailable, run code/tests that are possible and explicitly report manual validation steps; do not claim screenshots were taken.

### 9. Final deliverables / report

When finished, report:

1. Files changed + concise architectural mapping.
2. Screenshot(s) of actual running UI if possible, comparing **dashboard** and **settings modal** with provided references.
3. Per-feature completion (topbar, three tabs, custom table, progress/actions, overview/tickets, modal, log).
4. Real wiring of engine data; ticket source or `Chưa xác định` fallback, any unavailable field(s).
5. Tests/commands run and exact outcomes, including unrun tests.
6. Visual deviations, asset quality limitations and follow-up risks.

**Definition of Done:** Working desktop UI, responsive/reachable controls, correctly wired existing functionality, tests passing where runnable, and no modifications to the core automation flow. **Do not stop after writing only a plan.**

## END PROMPT
