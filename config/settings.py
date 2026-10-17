import os
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys

ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


def default_adb_path() -> str:
    explicit = os.environ.get("AVATAR_ADB_PATH")
    if explicit:
        return explicit
    installed = Path(r"C:\LDPlayer\LDPlayer14\adb.exe")
    return shutil.which("adb") or (str(installed) if installed.is_file() else "adb")


@dataclass(frozen=True)
class Settings:
    serial: str = os.environ.get("AVATAR_DEVICE_SERIAL", "emulator-5554")
    adb_path: str = default_adb_path()
    command_timeout: float = 15.0
    screenshot_path: Path = ROOT / "debug" / "screenshots" / "test.png"


@dataclass(frozen=True)
class TrialSettings:
    bite_timeout: float = 120.0
    round_timeout: float = 180.0
    unknown_timeout: float = 3.0
    plan_timeout: float = 2.0
    confirmation_timeout: float = 2.0
    recovery_timeout: float = 30.0
    poll_interval: float = 0.08
    swipe_duration_ms: int = 180


@dataclass(frozen=True)
class SessionSettings:
    rounds: int = 5
    transition_timeout: float = 6.0
    poll_interval: float = 0.15
    chair_entry_timeout: float = 20.0
