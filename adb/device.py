import re
import subprocess
import time
from collections.abc import Callable, Sequence

import numpy as np
from numpy.typing import NDArray

from .screenshot import decode_screenshot, decode_raw_screenshot

Runner = Callable[..., subprocess.CompletedProcess[bytes]]


class AdbError(RuntimeError):
    """Lỗi kết nối hoặc thực thi ADB."""


class AdbDevice:
    def __init__(self, serial: str, adb_path: str = "adb", timeout: float = 15.0,
                 runner: Runner = subprocess.run, fast_capture: bool = False):
        self.serial = serial
        self.adb_path = adb_path
        self.timeout = timeout
        self._runner = runner
        self.fast_capture=fast_capture
        self._size: tuple[int, int] | None = None
        self._size_observed = 0.0

    def _run(self, args: Sequence[str]) -> bytes:
        command = [self.adb_path, "-s", self.serial, *args]
        try:
            result = self._runner(command, capture_output=True, timeout=self.timeout,
                                  check=False, creationflags=subprocess.CREATE_NO_WINDOW
                                  if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AdbError(f"Không chạy được ADB: {exc}") from exc
        if result.returncode:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            raise AdbError(f"ADB thất bại: {message}")
        return result.stdout

    def is_connected(self) -> bool:
        return self._run(["get-state"]).strip() == b"device"

    def get_device_info(self) -> dict[str, str]:
        return {name: self._run(["shell", "getprop", prop]).decode().strip()
                for name, prop in (("model", "ro.product.model"),
                                   ("android", "ro.build.version.release"))}

    def get_screen_size(self) -> tuple[int, int]:
        output = self._run(["shell", "wm", "size"]).decode()
        sizes = re.findall(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", output)
        if not sizes:
            raise AdbError(f"Không đọc được độ phân giải: {output.strip()}")
        width, height = map(int, sizes[-1])
        if width <= 0 or height <= 0:
            raise AdbError("Độ phân giải không hợp lệ")
        return width, height

    def screenshot(self, checkpoint: Callable[[], None] | None = None,
                   on_retry: Callable[[int, int], None] | None = None) -> NDArray[np.uint8]:
        # Retrying this read cannot duplicate a cast or a payment. Never apply
        # these retries to input commands, whose timeout has an unknown outcome.
        for attempt in range(1, 4):
            if checkpoint is not None:
                checkpoint()
            try:
                if self.fast_capture:
                    try:
                        screen=decode_raw_screenshot(self._run(['exec-out','screencap']))
                    except ValueError:
                        self.fast_capture=False
                        screen=decode_screenshot(self._run(['exec-out','screencap','-p']))
                else:
                    screen = decode_screenshot(self._run(["exec-out", "screencap", "-p"]))
            except AdbError as exc:
                if checkpoint is not None:
                    checkpoint()
                if not isinstance(exc.__cause__, subprocess.TimeoutExpired):
                    raise
                if attempt == 3:
                    raise AdbError('ADB chụp màn hình timeout sau 3 lần; đã dừng. ' + str(exc)) from exc
                if on_retry is not None:
                    on_retry(attempt, 2)
                time.sleep(.5)
                continue
            except ValueError as exc:
                raise AdbError(str(exc)) from exc
            if checkpoint is not None:
                checkpoint()
            self._size = (screen.shape[1], screen.shape[0])
            self._size_observed = time.monotonic()
            return screen

    @staticmethod
    def _validate_point(x: int, y: int, size: tuple[int, int]) -> None:
        if (type(x) is not int or type(y) is not int
                or not (0 <= x < size[0] and 0 <= y < size[1])):
            raise ValueError(f"Tọa độ ({x}, {y}) nằm ngoài màn hình {size}")

    def tap(self, x: int, y: int) -> None:
        self._validate_point(x, y, self._input_size())
        self._run(["shell", "input", "tap", str(x), str(y)])

    def swipe(self, x1: int, y1: int, x2: int, y2: int,
              duration_ms: int = 250) -> None:
        if type(duration_ms) is not int or duration_ms <= 0:
            raise ValueError("Thời gian kéo phải là số nguyên dương")
        size = self._input_size()
        self._validate_point(x1, y1, size)
        self._validate_point(x2, y2, size)
        self._run(["shell", "input", "swipe", str(x1), str(y1),
                   str(x2), str(y2), str(duration_ms)])

    def back(self) -> None:
        self._run(["shell", "input", "keyevent", "4"])

    def _input_size(self) -> tuple[int, int]:
        # Ảnh vừa chụp đã cho kích thước thật; tránh thêm một tiến trình ADB mỗi tap/kéo.
        if self._size is not None and time.monotonic() - self._size_observed < 2:
            return self._size
        return self.get_screen_size()

    def type_number(self, value: int) -> None:
        """Nhập số vào ô đang được chọn, dùng cho số lượng mua mồi."""
        if type(value) is not int or value <= 0:
            raise ValueError("Số nhập phải là số nguyên dương")
        self._run(["shell", "input", "text", str(value)])
