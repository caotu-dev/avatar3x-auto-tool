# Nguồn ảnh mẫu

`idle_menu.png`: MENU cắt x40:157, y25:75 từ ảnh ADB tại ao trước khi vào ghế,
2026-10-08 20:19 (`tests/fixtures/idle_pond.png`).
`no_bait_reference.png`: câu thông báo thiếu mồi thật từ ảnh người dùng
`codex-clipboard-9ec3a3aa-7bfc-4d62-a173-c51fe8e97b5b.png`, cắt x350:628,
y224:250 rồi phóng theo tỉ lệ chiều rộng Android 1600/993. Detector thử vài
tỉ lệ font, không tạo chữ giả. `no_bait.png` là mẫu ADB sắc nét x580:1020,
y412:452 từ `debug/runs/2026-10-08_20-21-23_110793/round_052/003_STOP.png`.
Font ADB và font trong ảnh cửa sổ cũ có tỉ lệ khác, detector hỗ trợ cả hai mẫu.

Các PNG được cắt từ phiên ADB 1600×900 `2026-10-07_23-09-27_460870`.
Tọa độ theo thứ tự trái, trên, phải, dưới (điểm cuối không bao gồm):

| Mẫu | Frame | Vùng cắt |
|---|---|---|
| toss | 000010 | 740,826,865,862 |
| close | 000010 | 1410,826,1520,862 |
| finish | 000000 | 1400,826,1520,862 |
| success | 000185 | 575,154,1015,252 |
| timer | 000080 | 900,713,1030,728 |
| miss | phiên 23-29-23, frame 000364 | 1182,467,1237,490 |
| chair_top | phiên 23-29-23, frame 000010 | 1170,696,1230,734 |
| chair_bottom | phiên 23-29-23, frame 000010 | 1170,765,1230,795 |

`success` chỉ lấy tiêu đề, không phụ thuộc loại cá. `timer` lấy đoạn thanh
thời gian. Mẫu Area cũ đã xóa vì không còn dùng.
Ngữ cảnh dùng vùng nước và ít nhất hai trong bốn vị trí ghế đá, không đọc số Area.
Hai mẫu ghế dùng 15 hàng pixel trên cùng để tránh tên nhân vật và vật nuôi che.
Đã kiểm tra ở
Area 6 và Area 11, độ phân giải 1600×900. `miss` là chữ Miss thật từ phiên
`2026-10-07_23-29-23_107206`, so trên mặt nạ chữ vàng để tránh nền thay đổi.
Đã bổ sung mẫu chữ Trật rồi tiếng Việt từ ADB thật. UNKNOWN không được hành động.
# Popup xác nhận thoát

`exit_question.png` và `exit_no.png` cắt từ
`debug/runs/2026-10-08_08-10-12_889174/006_PREPARE_UNKNOWN.png`:
câu hỏi x650:950, y412:450 và nút No x872:1040, y520:584 (1600x900).
Nhận diện cần cả hai mẫu; không dùng nút Close của màn hình câu cá.

## Tiếng Việt — 2026-10-08

`toss_vi.png`, `close_vi.png`, `finish_vi.png` và `idle_menu_vi.png` cắt từ ADB thật. Ảnh gốc nút Quăng câu/Đóng: `tests/fixtures/ready_vi.png`; nút Xong: `tests/fixtures/result_vi.png`. So tương quan chữ để tránh nhầm Đóng với Xong trên nền vàng. Tiêu đề nhận cá vẫn dùng CONGRATS trong bản game này. Mẫu tiếng Anh giữ để chạy hồi quy dữ liệu cũ. Các ảnh ghi thử cũ đã dọn; ảnh hồi quy cần thiết nằm trong `tests/fixtures/session_short` và `session_long`.

`miss_vi.png`: Trật rồi, x1155:1255 y455:493 từ lượt 1 phiên tiếng Việt 21:19, ảnh `tests/fixtures/failed_vi.png`. Tách chữ vàng khỏi nền. `exit_question_vi.png` (x650:950 y408:452) và `exit_no_vi.png` (x912:1005 y536:578) từ popup thật trong `tests/fixtures/exit_vi.png`. Nhận cả câu hỏi và nút Không trước khi bấm. Đã mở bằng Android Back và kiểm tra hủy thoát trên LDPlayer thật.

`no_bait_vi.png`: câu thông báo 2 dòng x463:1137 y380:483, cắt từ `tests/fixtures/no_bait_vi.png`, chụp ADB tại lần quăng sau lượt 9 phiên cuối. Không nhận theo riêng nút OK. Thông báo: Bạn cần sử dụng mồi câu để câu cá trong khu vực này.
