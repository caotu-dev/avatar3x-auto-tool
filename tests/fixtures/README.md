# Ảnh kiểm tra ngữ cảnh

`player_menu_exit.png`: ảnh lỗi thật 18/10/2026, menu người chơi che shop và
popup hỏi thoát cùng xuất hiện tại trung tâm. Kiểm tra phải bấm Không, đóng
menu trên nền trống rồi mới tin vào map. Hai mẫu glyph message/punch trong
`vision/templates/world/` được cắt từ ảnh này; không dùng OCR tên người chơi.

`sale_success.png`: vùng popup bán cá từ ảnh lỗi phiên
`2026-10-17_23-23-46_142576` lúc bán trước nửa đêm. Giữ nguyên popup và nút OK;
phần còn lại đặt đen để không lưu tên nhân vật hoặc số dư tài khoản.

`idle_pond.png`: ảnh ADB trước khi vào ghế, ngày 2026-10-08 buổi tối.
`no_bait.png`: ảnh thiếu mồi thật của người dùng, đổi kích thước thành 1600x900
để kiểm tra bộ nhận diện trên viewport tham chiếu; chưa phải ảnh ADB nguyên bản.
`no_bait_adb.png`: popup hết mồi thực sự xuất hiện cuối phiên tự chạy buổi tối,
giữ nguyên viewport 1600x900 để kiểm tra nhận diện và chuỗi vào ghế/Toss/hết mồi.
`same_cup_different_colors.png`: lượt 2 phiên tự chạy `2026-10-08_20-21-23_110793`,
hai nguồn cốc giống nhau nhưng màu khác. Nhãn [5,3,3,5,2], giữ vùng bảng và nguồn.

`ready_lower_seat.png` lấy từ ảnh ADB thực tế `debug/screenshots/test.png`
ngày 2026-10-08: nhân vật ngồi ở ghế phía dưới, che hai vị trí dưới.
Chỉ giữ vùng nước, cụm ghế và các nút Toss/Close; phần còn lại đặt về màu đen.
Ảnh này dùng kiểm tra ngữ cảnh vẫn nhận được khi chỉ thấy hai ghế trên,
không phụ thuộc phiên ghi tùy chọn hoặc cây, lễ hội, biển số Area.

`two_filled.png` lấy từ ảnh STOP của lượt thử `2026-10-08_00-08-21_921544`.
Giữ vùng câu, nước, ghế, hình nguồn và thanh thời gian. Hai ô đã điền làm
hàng y=655 mất liên tục; test kiểm tra vẫn đo đủ 5 ô và không kéo lại hai ô đó.

`round_005_initial.png` và `round_009_initial.png` lấy từ sự kiện FISHING của
phiên `2026-10-08_07-24-18_646635`. Nhãn ghép theo thứ tự ô:
lượt 5 = [2, 5, 2, 1], lượt 9 = [1, 6, 6, 3]. Kiểm tra màu trên/dưới,
không giảm ngưỡng tin cậy để chấp nhận bảng.

`round_002_initial.png` và `round_002_wait.png` lấy từ FISHING và WAIT_RESULT
cùng phiên. Ô đầu vẫn tối và chưa đổi sau thao tác; dùng kiểm tra điều kiện
thử kéo lại. Các ảnh mới giữ vùng dưới và cột nguồn, xóa nền phía trên.

`crowded_ready.png`: PREPARE_UNKNOWN của phiên `2026-10-08_07-55-43_023534`.
Giữ nước, nhân vật và nút; ghế bị che, nhãn đỏ và Toss/Close vẫn thấy.
`ambiguous_plant.png`: FISHING lượt 4 phiên `2026-10-08_07-51-20_222212`.
Chậu cây và hoa có cùng màu, biên điểm chưa đủ an toàn; regression không ép kéo.

`other_player_miss.png`: STOP lượt 2 phiên `2026-10-08_08-02-49_345800`.
Chữ Miss trên người khác vẫn xuất hiện trong khi bảng ghép của mình hoạt động.
Giữ vùng chữ, bảng, nước, nhân vật và nguồn để kiểm tra ưu tiên FISHING.

`exit_confirmation.png`: PREPARE_UNKNOWN phiên `2026-10-08_08-10-12_889174`.
Popup xác nhận thoát phủ trên popup nhận cá, có Yes/No. Test nhận diện cần
câu hỏi và nút No, kiểm tra không bấm Yes.

## Dữ liệu giữ lại sau dọn ảnh

`session_short` giữ 11 frame cần cho test phiên 23:09; `session_long` giữ 15 frame cần cho test phiên 23:29. Ảnh debug gốc đã xóa, JSON/CSV vẫn giữ. `success.png` thay tham chiếu trực tiếp ảnh trong debug/trials.

`ready_vi.png`, `result_vi.png`, `failed_vi.png`, `exit_vi.png` và `success_vi.png` là ảnh ADB thật 1600x900 trong phiên tiếng Việt ngày 2026-10-08 buổi tối. Dùng kiểm tra chữ Quăng câu/Đóng/Xong, Trật rồi bay lên, popup hủy thoát và nhận cá. Không tạo chữ hoặc template giả.

`no_bait_vi.png`: popup cần mồi 2 dòng thật xuất hiện khi mồi đã hết. Test tích hợp vào ghế → Quăng câu → hết mồi chạy cả bộ ảnh tiếng Anh cũ và tiếng Việt mới, không gửi swipe và không bấm OK.

## Cải tiến bảng khó

`ambiguous_plant.png`: đáp án [6,6,5,5], hai chậu cây cùng màu hoa. Quét xoay thưa làm biên điểm dưới 0,10; tinh chỉnh góc/scale giải đúng mà không hạ ngưỡng. `ambiguous_fish_crown.png`: FISHING lượt 3 phiên 21:27, đáp án [6,2,2,4,3]; cá/vương miện cùng màu tím khiến histogram lấn át hình. Chỉ ưu tiên hình khi hai nguồn có glyph khác nhau và hình có biên đủ lớn.

`ambiguous_crown_scratches.png` và `ambiguous_fish_scratches.png`: lượt 14 và 25 phiên 21:48, đáp án [2,1,5,4,5] và [1,1,3,6]. Nền pastel/nét chéo làm glyph phình ra; kiểm tra lại bằng mask trắng chặt hơn chỉ ở ô phân vân. `saturation_tolerance.png`: lượt 4 cùng phiên đã thành công [5,1,6,5], bảo vệ cách tách cũ cho ô đã đủ chắc, tránh dùng mask chặt cho mọi ô.

ambiguous_rotated_cup.png: lượt 8 phiên 22:14, đáp án [5,1,4,1,4]. Bước xoay 5° còn biên 0,0972; tinh chỉnh 2° vượt 0,10. Chỉ dùng như bước cuối ở ô chưa đủ chắc; cache riêng để giữ điểm các ô đã chấp nhận.

## Shop và map, 08–09/10/2026

center_right, shop_menu, worm_selected, quantity1, quantity20,
quantity_input20, purchase20 là ảnh ADB thật của trung tâm và chuỗi mua 20 Mồi Trùng.
bait_capacity là thông báo thật giới hạn 50 mồi.
puffer_idle/puffer_board/puffer_crowded_idle, shark_idle/shark_board/shark_occluded_board
là map, bảng ghép và trường hợp người chơi che bảng đã gặp khi thử trực tiếp.
fish/ giữ popup đủ màn hình cho cả 9 loại đã gặp. Giá không dùng suy ra loại cá.
