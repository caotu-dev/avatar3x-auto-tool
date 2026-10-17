# Avatar Fishing Bot

Bot Python điều khiển Avatar trong LDPlayer qua ADB, ảnh chụp và OCR.
UI Redesign v2 là bản chính; engine và tọa độ game giữ nguyên.

## Chạy ứng dụng

Mở **`dist/AvatarFishingBot/AvatarFishingBot.exe`** hoặc shortcut
`Avatar Fishing Bot.lnk`. Giữ nguyên toàn bộ thư mục cạnh `.exe`.
Bản đóng gói không cần cài Python. Chạy source bằng `python gui.py`.

Cần LDPlayer đang mở game ở **1600×900** và ADB được bật.
Mặc định thiết bị `emulator-5554`; ADB lấy từ PATH hoặc LDPlayer14.
Có thể đặt `AVATAR_ADB_PATH` và `AVATAR_DEVICE_SERIAL` trong môi trường.

## Giao diện và hành vi

- Topbar có Thiết lập, Bắt đầu, Tạm dừng/Tiếp tục, Kết thúc, thư mục log và đồng hồ.
- **Nhiệm vụ game:** bật tự đọc/làm nhiệm vụ. **Câu tự do:** bật chế độ và chọn khu.
  **Tự đặt mục tiêu:** chọn cá, chọn hàng đang chỉnh rồi đặt số lượng hoặc đổi thứ tự.
- Bảng gồm các loài Sinh Thái và cá Bến Tàu đã xác minh bằng kết quả trong game.
  Checkbox chọn cá và focus hàng là hai trạng thái riêng.
  Số lượng, ↑/↓ và Reset nằm dưới bảng tiến độ. Có thể kéo hàng để đổi thứ tự.
- Reset bỏ chọn, đặt số lượng về 1, trả thứ tự mặc định và xóa tiến độ tự đặt;
  không xóa nhiệm vụ trong game, tồn mồi hay log.
- Bố cục rộng dùng ba cột 35/40/25. Cửa sổ hẹp xếp tổng quan xuống dưới;
  cuộn cả trang khi thiếu chiều cao. Bảng cá không có cuộn riêng.
- Popup Thiết lập dùng draft. Lưu xác thực và ghi cấu hình trước khi áp dụng;
  Hủy/X/Escape bỏ thay đổi chưa lưu. Mồi mua mỗi lần từ 1 đến 50.
- Bắt đầu luôn mở bước chuẩn bị: tới Sinh Thái/Bến Tàu, quét rương, đọc vé/ngày hết hạn,
  số lượng mồi và số dư Xu/Lượng. Chỉ quét toàn rương một lần mỗi lần Bắt đầu;
  đổi khu hoặc khôi phục mất phiên dùng cache trong phiên. Biên nhận mua thành công
  cập nhật vé/mồi ngay, không mở rương kiểm tra lại. Rương hết mồi thì mua theo thiết lập.
  Sau khi bắt đầu câu, checkbox mua mồi quyết định có tự mua tiếp khi hết hay không.
  Chỉ cộng số mồi đã mua khi có biên nhận xác nhận.
  Bán khi về shop và lịch bán cố định **23:57** dùng giờ máy Windows.
- Thiết lập/mục tiêu bị khóa khi có phiên đang chạy. Tạm dừng có hiệu lực sau lượt hiện tại;
  Tiếp tục giữ phiên. Kết thúc chặn thao tác mới và chờ thao tác đang thực thi kết thúc.
  Đồng hồ bao gồm thời gian tạm dừng.
- Progress và sáu metrics lấy dữ liệu engine. Sinh thái/Bến tàu là tồn mồi riêng;
  chưa biết thì hiển thị Chưa xác định. Bốn thẻ vé lấy thông tin rương, hiển thị
  Có/còn hiệu lực, Không có, Hết hạn hoặc Chưa xác định và ngày hết hạn khi đọc được.
- Bốn checkbox tự mua vé riêng, mặc định tắt. Chỉ mua vé cần cho khu câu, đúng shop
  và đúng loại tiền (vé cá mập 2 lượng). Thiếu tiền hoặc dữ liệu không chắc sẽ dừng.
  Không dùng lượng khóa. Vé xuất hiện trong rương là còn hiệu lực; vé hết hạn tự biến mất.
  Ngày đọc được chỉ dùng để hiển thị, không khiến bot mua lại vé đang có.
- Popup chuẩn bị có Hủy; Bắt đầu/Tạm dừng bị khóa trong bước này. Đồng hồ bắt đầu
  sau chuẩn bị. Mỗi lần Bắt đầu mới vẫn quét lại rương. Số mồi theo dõi trong lúc câu
  có dấu ≈ vì là ước tính; chỉ tự mua bổ sung khi game xác nhận hết mồi.
- Mục tiêu chưa hoàn thành được khôi phục khi danh sách, số lượng và thứ tự khớp phiên đã lưu.
  Danh sách đã hoàn thành bắt đầu phiên mới từ 0. Hoàn thành có popup và âm thanh Windows.

Bot không tự trả nhiệm vụ trong game. Luồng mua vé cần xác nhận tên/giá/nút thanh toán
và biên nhận; popup chưa nhận diện sẽ dừng trước bước tiếp theo. Luồng Bến Tàu hỗ trợ
chọn thuyền trống, đổi khu khi đông người, câu và mua mồi Cá Trâm. Popup lạ, lỗi kết nối hoặc thiếu bằng chứng
nhận diện sẽ dừng và lưu thông tin lỗi. Các mùa/giao diện game khác còn cần kiểm tra.

## Dữ liệu và cập nhật

Trong bản `.exe`, `runtime/` và `debug/` nằm cạnh executable;
trong source chúng nằm ở gốc repository.

| File/thư mục | Nội dung |
|---|---|
| `runtime/ui_preferences.json` | Thiết lập và danh sách mục tiêu |
| `runtime/custom_mission.json` | Tiến độ tự đặt |
| `runtime/ui_inventory.json` | Tồn cá/mồi, ngày bán và trạng thái mua |
| `runtime/ui_last.json` | Snapshot phiên cuối |
| `runtime/game_quest.json`, `navigation.json`, `dock.json` | State nhiệm vụ/di chuyển/bến tàu khi có |
| `debug/ui/<phiên>/` | Log, ảnh và state của từng phiên GUI |
| `debug/bugs.jsonl` | Lỗi dừng và kết quả cần chẩn đoán |

Khi đưa v2 thành bản chính, file runtime mới nhất và log cả hai bản được giữ.
Script build chỉ cập nhật file thuộc package theo `release-files.json`;
không xóa `runtime/debug`.

## Cài đặt và build

Cần Python 3.10 trở lên; môi trường hiện tại dùng Python 3.12/Tk 8.6.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File build_gui.ps1
```

Package chính nằm tại `dist/AvatarFishingBot/`. `build/` chỉ là staging/cache,
được tạo lại khi build. Không còn script build hoặc package riêng cho v2.
Đóng app trước khi cập nhật executable.

## Kiểm tra và công cụ CLI

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

Tests dùng mock/fixtures, không bấm emulator. Tài liệu thiết kế, screenshots và
kết quả kiểm tra hiện tại nằm trong `docs/ui/avatar_fishing_codex_v2/`.

| Lệnh | Hành vi |
|---|---|
| `python main.py` | Kiểm tra ADB và chụp ảnh, không gửi input |
| `python main.py --record --duration 120 --interval 0.3` | Ghi phiên thao tác thủ công |
| `python -m debug.analyze <thư mục phiên> --solve` | Phân tích trạng thái/solver offline |
| `python -m debug.solve <ảnh>` | Vẽ kế hoạch kéo offline |
| `python main.py --run-one` | Quăng/giải một lượt thật |
| `python main.py --run --rounds 5 --area ca_ro` | Câu số lượt giới hạn |
| `python main.py --tour --rounds 20` | Shop/cá nóc/cá mập theo luồng CLI hiện có |
| `python main.py --mission` | Nhiệm vụ từ `config/mission.json` |
| `python main.py --read-quest` | Mở và đọc nhiệm vụ trong game |
| `python main.py --navigate fishing` | Di chuyển; đích khác: administration, dock |
| `python main.py --test-navigation` | Kiểm tra vòng di chuyển |
| `python main.py --dock-check` | Kiểm tra bến tàu, chưa mua/quăng |

Templates thật và nguồn mẫu: `vision/templates/README.md`.
Fixtures kiểm tra nằm trong `tests/fixtures/`; không xóa cùng dữ liệu debug.

Mất phiên: chỉ bấm Chơi tiếp khi nhận diện logo và nút ổn định. Nếu tap bị bỏ qua,
bot thử lại tối đa 3 lần; không bấm vào màn hình loading. Khôi phục giữ tiến độ và
cache rương; thất bại báo ERROR, không kết thúc bằng trạng thái RUNNING.

### Dung lượng và nhật ký

Chỉ chạy `dist/AvatarFishingBot/AvatarFishingBot.exe` hoặc shortcut `Avatar Fishing Bot.lnk`; cần giữ các thư viện cạnh exe. Công cụ Python trong `.venv` dùng để phát triển/build, không phải bản bot thứ hai. Build thành công tự xóa staging.

Ảnh sự kiện tự động được xoay vòng ba JPEG trong mỗi thư mục chẩn đoán. Debug được dọn định kỳ theo tuổi 24 giờ và ngân sách 32 MiB, tối đa 128 báo cáo lượt GUI; file đang dùng trong 10 phút gần nhất và kết quả lượt phục vụ khôi phục được giữ. Ảnh OCR làm việc, ảnh xuất thủ công, `vision/templates`, `tests/fixtures`, `ui/assets` và `runtime` không bị chuyển sang ảnh nén. Dữ liệu nhiệm vụ/vé/mồi lưu trong `runtime`, không phụ thuộc ảnh debug.
