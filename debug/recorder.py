import csv
import time
from datetime import datetime
from pathlib import Path

from adb import AdbDevice
from adb.screenshot import save_debug_screenshot


def record_session(device: AdbDevice, root: Path, duration: float,
                   interval: float) -> Path:
    """Chụp tuần tự; tốc độ thực tế phụ thuộc thời gian ADB và lưu PNG."""
    if duration <= 0 or interval <= 0:
        raise ValueError("Thời lượng và khoảng chụp phải lớn hơn 0")
    session = root / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    session.mkdir(parents=True, exist_ok=False)
    print(f"Thư mục phiên: {session}", flush=True)
    print("Đang ghi ảnh. Hãy câu thủ công; Ctrl+C để dừng.", flush=True)
    started = time.monotonic()
    count = 0
    interrupted = False
    with (session / "frames.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["file", "capture_started_seconds", "capture_duration_seconds", "width", "height"])
        try:
            while time.monotonic() - started < duration:
                frame_started = time.monotonic()
                screen = device.screenshot()
                captured = time.monotonic()
                filename = f"{count:06d}.png"
                save_debug_screenshot(screen, session / filename)
                writer.writerow([filename, f"{frame_started - started:.3f}",
                                 f"{captured - frame_started:.3f}",
                                 screen.shape[1], screen.shape[0]])
                file.flush()
                count += 1
                if count == 1 or count % 20 == 0:
                    print(f"Đã lưu {count} ảnh ({captured - started:.1f}s)", flush=True)
                remaining = min(interval - (time.monotonic() - frame_started),
                                duration - (time.monotonic() - started))
                if remaining > 0:
                    time.sleep(remaining)
        except KeyboardInterrupt:
            interrupted = True
        finally:
            elapsed = time.monotonic() - started
            print(f"{'Đã dừng' if interrupted else 'Kết thúc ghi'}: {count} ảnh / "
                  f"{elapsed:.1f}s, {count / elapsed if elapsed else 0:.2f} ảnh/s.", flush=True)
    return session
