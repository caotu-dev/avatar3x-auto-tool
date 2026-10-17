# Avatar Fishing Bot — Codex UI Redesign v2

**Mục tiêu:** Triển khai UI Python desktop dựa trên 2 mockup đã duyệt, không thay đổi thuật toán bot.

## Bộ tài liệu

| File | Ưu tiên | Công dụng |
|---|---|---|
| `CODEX_MASTER_PROMPT.md` | 1 | Prompt triển khai cực chi tiết, có phase, ràng buộc, acceptance criteria |
| `UI_INTERACTION_FLOW.md` | 2 | Luồng UI từng màn/nút/tab, bảng trạng thái, lỗi, data mapping, QA |
| `DESIGN_TOKENS_V2.json` | 3 | Quy tắc màu, kích thước, spacing, tỉ lệ cột mới |
| `assets/references/dashboard_main.png` | 4 | Mockup dashboard duyệt cuối |
| `assets/references/dashboard_settings_popup.png` | 5 | Mockup popup Thiết lập |
| `CODEX_ASSET_MAPPING.md` | 6 | Hướng dẫn dùng PNG crop / nơi dùng / cảnh báo legacy icons |
| `asset_registry.json` | 7 | Danh mục machine-readable asset |
| `assets/fish-icons-clean/` | 8 | 10 crop icon cá/cua đã sửa đúng vị trí, có preview + fish ID mapping |
| `assets/ASSET_PREVIEW_SHEET.png` | 9 | Preview asset cũ (một số crop nhỏ **lệch**, không được dùng mù quáng) |

## Bắt đầu (khuyên dùng)

1. Giải nén ZIP vào `<repository-root>/docs/ui/avatar-fishing-v2/`.
2. Mở Codex tại **root của repository Python** (không mở trong thư mục chỉ chứa docs).
3. Copy prompt nhanh dưới đây vào Codex; nó buộc Codex đọc **toàn bộ prompt dài + flow** trước khi implement.

```text
Implement the Avatar Fishing Bot desktop UI redesign v2 in this repository.

Before modifying code, read these files IN FULL and follow their priority:
1) docs/ui/avatar-fishing-v2/CODEX_MASTER_PROMPT.md (section BEGIN PROMPT through END PROMPT)
2) docs/ui/avatar-fishing-v2/UI_INTERACTION_FLOW.md
3) docs/ui/avatar-fishing-v2/DESIGN_TOKENS_V2.json
4) docs/ui/avatar-fishing-v2/CODEX_ASSET_MAPPING.md
5) both images in docs/ui/avatar-fishing-v2/assets/references/

Inspect the actual Python GUI framework, application entry point, engine callbacks, session state model, settings storage, target model, threading and packaging. Write a concise IMPLEMENTATION_PLAN.md in the same design folder, then implement the UI in phases, wire every supported action to the existing app, and run tests plus visual checks. Do not stop after planning.

Critical changes: settings in modal; controls+timer in a horizontal bar; body 35%/40%/25%; 3 mode tabs; custom fish table 3 columns and NO internal scroll; move target quantity/order/reset actions into progress card; six live overview tiles; four ticket status cards using verified data or 'Chưa xác định'; preserve all existing automation logic. Prioritize corrected icons under assets/fish-icons-clean/ instead of legacy fish-icons crops.

Produce working code and report files changed, actual tests run, screenshots if possible and limitations. Never fabricate values/features. If your paths differ, locate this folder rather than assuming it is missing.
```

4. Nếu Codex không tìm được file vì thư mục đã đổi tên, hãy gửi lại path đúng trong repo.
5. Sau lượt code đầu tiên, đối chiếu screenshot app thật với hai ảnh mockup, rồi yêu cầu Codex sửa khác biệt theo thứ tự ưu tiên.

## Notes quan trọng

- File `UI_INTERACTION_FLOW.md` **ghi đè** các yêu cầu cũ khi có mâu thuẫn. Bản cũ có sidebar + Settings column, nhưng **v2 đã bỏ**.
- Mọi con số và `Có` / thời hạn vé trong ảnh **chỉ là dữ liệu minh hoạ**.
- `assets/fish-icons-clean/` đã sửa nhóm crop lệch từ bundle trước; vẫn là PNG crop từ ảnh flattened và có thể dính nền nhạt.
- Tất cả button, table, checkbox, popup, timer phải là GUI controls thật; PNG chỉ là reference/decor.
- Không tự ý thêm dependency, shortcut hay thay đổi luồng OCR/game automation.

## Checklist nhanh trước khi chốt

- [ ] Không còn cột bên trái thiết lập cũ
- [ ] Đủ 3 cột chính theo tỷ lệ rộng 35/40/25
- [ ] Modal lưu/hủy đúng, không tự save lúc hủy
- [ ] Các checkbox đồng nhất
- [ ] Table cá full content, không inner-scroll
- [ ] Toolbar mục tiêu nằm ở progress card
- [ ] Timer/Start/Pause/Stop đúng session state
- [ ] 4 vé hiển thị Có/Không/Chưa xác định đúng nguồn dữ liệu
- [ ] Chạy tests + kiểm tra GUI Windows resize/DPI
