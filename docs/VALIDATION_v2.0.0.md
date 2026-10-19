# Kiểm tra phát hành v2.0.0

Ngày kiểm tra: 19/10/2026. Môi trường local: Windows, Python 3.12, Tk 8.6.

## Source và hồi quy

`python -m unittest discover -s tests`: **380 tests passed**. Lần chạy đầy đủ
có verbose/watchdog trên máy phát triển hoàn tất trong 189,559 giây. Bao gồm
nhận diện, matching, solver, xác nhận mua/bán, nhiệm vụ, khôi phục, transport,
layout, mini mode, dragging, thống kê nhận cá và vòng đời animation.

Có thông báo Tk ThemeChanged khi hủy test roots và traceback chẩn đoán định kỳ
của watchdog ở một số test dài; kết quả cuối cùng là OK, không phải lỗi startup.
File log thô được giữ riêng trên máy phát triển, không đóng gói log cá nhân.

### Khác biệt phát hiện trên runner

Lần CI đầu tiên của bản chuẩn bị có 1/380 test thất bại tại puffer_idle, dù local
pass: hai biển phòng có điểm gần như bằng nhau, và biển không có ghế có thể
thắng do sai số số thực khác CPU. Không bỏ qua test hoặc hạ ngưỡng. Bộ dò hiện
kiểm tra cả hai bờ bằng ROI chồng lấn, rồi chọn nhóm có nhiều ghế thật được xác
nhận hơn. Regression mới buộc biển không có ghế đạt điểm cao hơn; 40 tests liên
quan khu câu/scene/ghế/fast path pass sau sửa. Suite đầy đủ có thêm test này
(381 tests); kết quả cuối cùng của tag nằm ở workflow Windows release.

## Visual QA

- Dashboard, Chọn nhiệm vụ và Thiết lập được chụp từ các widget thật bằng
  `tools/capture_readme.py`, với settings tạm và số liệu minh họa có nhãn.
- Dashboard client 1534×1025; ảnh popup dùng kích thước thật.
- Kiểm tra icon Xu/Lượng trong suốt, nhãn Cắn câu, tiến độ cyan, các heading,
  bảng cá, trạng thái nút và nội dung popup.
- Giữ hàng Lưu nhiệm vụ/Hủy luôn hiện trong popup; regression test kiểm tra
  cả ba tab. Bản này không thay engine để tạo số liệu cho ảnh.

## Packaging

Version Windows và APP_VERSION là **2.0.0** (FileVersion 2.0.0.0).
Build bằng PyInstaller/spec hiện có; ZIP portable kèm README, ảnh và tài liệu.
Frozen `--ui-check` và `--smoke-test` là các bước xác nhận khởi tạo UI/assets,
template và OCR helper, không bắt đầu worker hoặc thao tác game.

Kết quả local: cả hai diagnostic **pass**, version 2.0.0, 49 UI assets, 3 tab,
worker_started=false, 12 dock templates và OCR helper có mặt. ZIP CRC và SHA-256
**pass**; EXE trong ZIP khớp bản đã kiểm tra, có README/ba ảnh mới và không có
thư mục runtime/debug cá nhân.

Trước publish, kiểm tra ZIP CRC, SHA-256, EXE/README/ảnh và không có runtime/debug
cá nhân. Workflow [Windows release](https://github.com/caotu-dev/avatar3x-auto-tool/actions/workflows/release.yml)
chạy tests lại trên Windows runner, build ZIP và tạo draft cho tag.

## Dọn source

Các bộ asset thiết kế lịch sử trùng, screenshot cũ, báo cáo thử nghiệm, output
QA và script live probe một lần được bỏ khỏi cây source công khai. Tư liệu
lịch sử cần giữ nằm trong thư mục `.local-qa/` bị ignore trên máy phát triển.
Không xóa templates, fixtures, cấu hình hay tiến độ/log đang dùng.

Kiểm tra diff whitespace, cú pháp helper Python, đường dẫn ảnh/link tài liệu
nội bộ và mẫu credential trước khi push. Không có runtime/dist/diagnostic máy
cá nhân hoặc shortcut đường dẫn máy trong các file source được stage.

## Phạm vi kiểm chứng

Không thực hiện phiên câu/treo máy dài bằng bản release này. Bộ test dùng
fixtures/mocks, không xác nhận mọi thay đổi giao diện game hoặc loại bỏ leak
trong LDPlayer/driver. Các giới hạn vận hành có trong README và release notes.
