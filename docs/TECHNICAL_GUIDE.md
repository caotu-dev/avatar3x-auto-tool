# Phát triển Avatools 3x

Tài liệu này dành cho người phát triển. Hướng dẫn cài game và sử dụng EXE nằm
trong [README](../README.md). Phiên bản hiện tại: **2.0.0**.

## Chạy source

Windows, Python 3.12 được dùng cho bản build chính thức. UI dùng Tkinter/ttk,
nhận diện dùng NumPy/OpenCV; không có GUI framework mới.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe gui.py
```

LDPlayer cần Android 1600×900, ADB cục bộ và game đã đăng nhập. ADB được tìm
trong PATH hoặc `C:\LDPlayer\LDPlayer14\adb.exe`; có thể ghi đè bằng
`AVATAR_ADB_PATH` và `AVATAR_DEVICE_SERIAL` (mặc định `emulator-5554`).

## Cấu trúc source

| Thư mục/file | Chức năng |
| --- | --- |
| `gui.py`, `ui/` | UI, theme/assets, worker và các control |
| `fishing/` | Nhận diện trạng thái, solver, phiên câu, rương, nhiệm vụ, di chuyển |
| `adb/` | Transport, screenshot và kiểm tra tọa độ |
| `vision/` | Matching/layout, templates và Windows OCR helper |
| `config/` | Settings, giới hạn luồng native, version Windows |
| `tests/fixtures/` | Ảnh cố định để regression; không phải cache có thể dọn tùy ý |
| `tools/` | Chụp README, tách artwork tham chiếu, kiểm tra/phát hành GitHub |
| `docs/design/` | Tham chiếu thiết kế được duyệt |
| `docs/images/`, `docs/releases/` | Ảnh và ghi chú phát hành dùng cho người đọc |

UI updates đi qua queue tới luồng Tk. Cần giữ logic nhận diện, xác nhận thanh
toán và giới hạn luồng worker khi chỉnh layout. Animation tiến độ chỉ đổi ảnh
hiển thị; tổng/ratio vẫn lấy từ dữ liệu mục tiêu có clamp.

## Test

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

Tests dùng mock và fixtures, không gửi thao tác vào giả lập thật. Cần desktop
Windows/Tk cho kiểm tra UI. Kết quả release: [VALIDATION_v2.0.0.md](VALIDATION_v2.0.0.md).

Chụp lại ảnh README từ widget thật, không dùng dữ liệu tài khoản:

```powershell
.venv\Scripts\python.exe -m pip install Pillow
.venv\Scripts\python.exe tools/capture_readme.py
```

Pillow chỉ dùng khi chụp tài liệu, không phải dependency runtime của EXE.
Dữ liệu ảnh được đánh dấu minh họa; helper không tạo BotWorker hay gọi ADB.

## Build portable

Đóng EXE trước khi build. `build_gui.ps1` dùng spec hiện có, cập nhật package theo
manifest và bảo toàn `runtime/debug`; thư viện không đổi được kiểm tra hash rồi
bỏ qua copy. Không tự dừng ứng dụng đang chạy để ghi đè EXE.

```powershell
powershell -ExecutionPolicy Bypass -File build_gui.ps1
powershell -ExecutionPolicy Bypass -File package_release.ps1
.venv\Scripts\python.exe tools/verify_release.py --installed dist/AvatarFishingBot
```

Output: `dist/AvatarFishingBot/Avatools 3x.exe` và
`dist/release/Avatools-3x-windows-x64.zip` + `SHA256SUMS.txt`.
Giữ nguyên cả thư mục portable. ZIP có hướng dẫn/ảnh, không kèm dữ liệu cá nhân.

Kiểm tra frozen UI, không chạy bot:

```powershell
& '.\dist\AvatarFishingBot\Avatools 3x.exe' --ui-check
& '.\dist\AvatarFishingBot\Avatools 3x.exe' --smoke-test
```

Hai chế độ ghi JSON chẩn đoán cạnh EXE; chúng không nằm trong manifest phát hành.
Version ở `ui/branding.py` và `config/windows_version_info.txt` cần đồng bộ.

## Dữ liệu người dùng

Trong source, dữ liệu nằm ở gốc repo; trong EXE, nằm cạnh executable:

- `runtime/ui_preferences.json`: thiết lập UI và lựa chọn.
- `runtime/custom_mission.json`, `game_quest.json`: tiến độ/mục tiêu.
- `runtime/ui_inventory.json`, `character_state.json`: trạng thái rương/cache.
- `runtime/ui_last.json`: snapshot phiên cuối.
- `debug/ui/<phiên>/`: log và báo cáo; `debug/bugs.jsonl`: lỗi cần kiểm tra.

Không commit dữ liệu runtime/debug, token, mật khẩu, shortcut đường dẫn máy,
file build hoặc báo cáo máy cá nhân. Kết quả QA phát sinh nằm trong `docs/build/`
(bị ignore), chẩn đoán máy ở `docs/diagnostics/` (bị ignore). Tư liệu QA lịch sử
đã được chuyển khỏi source công khai vào `.local-qa/` trên máy phát triển.

Dọn debug có ngân sách/tuổi và bảo vệ bằng chứng giao dịch chưa xử lý. Không
xóa templates, fixtures hoặc runtime cùng với cache. Pagefile/RAM của LDPlayer
không thuộc phạm vi bộ dọn dữ liệu của tool.

## Phát hành

Workflow Windows chạy tests, build và upload ZIP/SHA, rồi tạo draft Release khi
push tag `v*`. Chỉ gắn tag vào commit đã kiểm tra. Sau khi CI thành công, đối
chiếu asset/version và publish draft. Không retag phiên bản đã công bố.

```powershell
git tag -a v2.0.0 -m 'Avatools 3x v2.0.0'
git push origin main
git push origin v2.0.0
.venv\Scripts\python.exe tools/github_release.py runs --sha <commit>
.venv\Scripts\python.exe tools/github_release.py release --tag v2.0.0
```

Helper lấy token từ Git Credential Manager hoặc GH_TOKEN/GITHUB_TOKEN, không in
bí mật. Lệnh publish yêu cầu notes và đúng SHA đã review:

```powershell
.venv\Scripts\python.exe tools/github_release.py publish --tag v2.0.0 --sha <commit> --notes docs/releases/v2.0.0.md
```

## CLI

`python main.py --help` liệt kê đầy đủ tùy chọn. `python main.py` chỉ kiểm tra
ADB/chụp ảnh; các lệnh `--run-one`, `--run`, `--tour`, `--navigate` thực sự thao
tác game. Công cụ phân tích offline: `python -m debug.solve <ảnh>` hoặc
`python -m debug.analyze <thư mục phiên> --solve`.
