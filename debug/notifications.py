import json
import sys
from datetime import datetime
from pathlib import Path


def notify_out_of_bait(output: Path) -> None:
    """Báo tại máy đang chạy; không gửi tin nhắn hoặc mua mồi."""
    output.mkdir(parents=True, exist_ok=True)
    message = "Avatar Fishing Bot: hết mồi câu. Bot đã dừng; hãy mua thêm mồi."
    (output / "notification.json").write_text(json.dumps(
        {"time": datetime.now().astimezone().isoformat(), "message": message},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[THÔNG BÁO] {message}", flush=True)
    if sys.platform == "win32":
        import winsound
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except RuntimeError:
            pass
