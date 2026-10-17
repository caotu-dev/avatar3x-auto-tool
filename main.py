import argparse
import math
import sys

from adb import AdbDevice, AdbError
from adb.screenshot import save_debug_screenshot
from config.settings import Settings, TrialSettings, SessionSettings
from debug.recorder import record_session
from debug.notifications import notify_out_of_bait
from fishing.bot import OneRoundBot
from fishing.session import FishingSession


def positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Giá trị phải là số hữu hạn lớn hơn 0")
    return number


def positive_integer(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Số lượt phải lớn hơn 0")
    return number


def main() -> int:
    # Console Windows có thể dùng bảng mã không hỗ trợ tiếng Việt.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Kiểm tra ADB và thu thập ảnh câu cá")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--record", action="store_true", help="Ghi chuỗi ảnh, không điều khiển game")
    modes.add_argument("--run-one", action="store_true", help="Quăng và giải một lượt, dừng khi có kết quả")
    modes.add_argument("--run", action="store_true", help="Câu nhiều lượt có giới hạn, tự đóng popup và Xong")
    modes.add_argument("--tour", action="store_true", help="Shop → cá nóc → shop → cá mập; mua 20 mồi mỗi lô")
    modes.add_argument("--mission", action="store_true", help="Chạy nhiệm vụ từ config/mission.json, giữ tiến độ")
    modes.add_argument("--read-quest", action="store_true", help="Mở và đọc nhiệm vụ trong game, lưu state")
    modes.add_argument("--navigate", choices=("fishing", "administration", "dock"), help="Di chuyển đến một khu")
    modes.add_argument("--test-navigation", action="store_true", help="Câu cá → Hành chính → Bến tàu → Câu cá")
    modes.add_argument("--dock-check", action="store_true", help="Kiểm tra thuyền và điều kiện câu bến tàu; chưa mua/quăng")
    parser.add_argument("--rounds", type=positive_integer, help="Số lượt cho --run (mặc định 5)")
    parser.add_argument("--area", choices=("ca_ro", "ca_noc", "ca_map"), default="ca_ro", help="Khu câu đang mở")
    parser.add_argument("--duration", type=positive_seconds, default=120.0, help="Thời lượng ghi (giây)")
    parser.add_argument("--interval", type=positive_seconds, default=0.3, help="Khoảng chụp mục tiêu (giây)")
    args = parser.parse_args()
    if args.rounds is not None and not (args.run or args.tour):
        parser.error("--rounds chỉ dùng cùng --run hoặc --tour")
    settings = Settings()
    device = AdbDevice(settings.serial, settings.adb_path, settings.command_timeout)
    print("Avatar Fishing Bot\n")
    try:
        if not device.is_connected():
            raise AdbError("Thiết bị chưa kết nối")
        print(f"Thiết bị ADB: {device.serial}\nTrạng thái: đã kết nối")
        info = device.get_device_info()
        print(f"Model: {info['model']} | Android: {info['android']}")
        width, height = device.get_screen_size()
        print(f"Độ phân giải: {width}x{height}")
        if args.dock_check:
            from fishing.dock import DockController
            result = DockController(device).check()
            print(f"[BẾN TÀU] {result['status']}: {result['reason']}")
            print(f"State: runtime/dock.json. Log: {result['log']}")
            return 0 if result['status'] == 'LEVEL_REQUIRED' else 1
        if args.navigate or args.test_navigation:
            from fishing.navigation import MapNavigator
            navigator = MapNavigator(device)
            if args.test_navigation:
                navigator.test_route()
            else:
                navigator.go(args.navigate)
            print(f"Đã đến: {navigator.visited[-1]}. Log: {navigator.output}")
            return 0
        if args.read_quest:
            from fishing.quest import QuestReader
            result = QuestReader(device).read()
            for target in result["targets"]:
                print(f"{target['name']}: {target['current']}/{target['required']}")
            print("Đã lưu: runtime/game_quest.json")
            return 0
        if args.run_one or args.run or args.tour or args.mission:
            if (width, height) != (1600, 900):
                raise ValueError("Chế độ thử hiện cần độ phân giải Android 1600x900")
            if args.mission:
                from fishing.mission import FishingMission
                result = FishingMission(device).run()
                return 0 if result["status"] == "COMPLETE" else 1
            if args.tour:
                from fishing.tour import FishingTour
                result = FishingTour(device, rounds_per_area=args.rounds or 20).run()
                return 0 if result["status"] == "COMPLETE" else 1
            if args.run:
                result = FishingSession(device, SessionSettings(rounds=args.rounds or 5), area=args.area).run()
                return 0 if result.status in ("COMPLETE", "OUT_OF_BAIT") else 1
            result = OneRoundBot(device, TrialSettings(), area=args.area).run()
            if result.outcome == "OUT_OF_BAIT":
                notify_out_of_bait(settings.screenshot_path.parent.parent)
                return 0
            return 0 if result.outcome in ("SUCCESS", "FAILED", "RESULT") else 1
        if args.record:
            record_session(device, settings.screenshot_path.parent / "sessions",
                           args.duration, args.interval)
            return 0
        screen = device.screenshot()
        path = save_debug_screenshot(screen, settings.screenshot_path)
        print(f"\nĐã chụp ảnh vào bộ nhớ: {screen.shape[1]}x{screen.shape[0]}")
        print(f"Đã lưu: {path}")
        return 0
    except (AdbError, OSError, ValueError, RuntimeError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
