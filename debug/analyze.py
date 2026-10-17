import argparse
import csv
import sys
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

import cv2
import numpy as np

from fishing.detector import FishingDetector
from fishing.states import FishingState
from fishing.solver import FishingSolver
from vision.layout import find_target_board
from debug.solve import draw_plan
from adb.screenshot import save_debug_screenshot


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Nhận diện ảnh đã ghi, không kết nối ADB")
    parser.add_argument("session", type=Path, help="Thư mục chứa ảnh PNG")
    parser.add_argument("--solve", action="store_true", help="Kiểm tra ghép hình, lưu báo cáo và ảnh mẫu đường kéo")
    args = parser.parse_args()
    files = sorted(args.session.glob("*.png"))
    if not files:
        parser.error("Thư mục không có ảnh PNG")
    detector = FishingDetector()
    solver = FishingSolver() if args.solve else None
    counts = Counter()
    board_counts = Counter()
    plan_counts = Counter()
    preview_saved = False
    previous = None
    report = args.session / "detections.csv"
    with ExitStack() as stack:
        stream = stack.enter_context(report.open("w", encoding="utf-8", newline=""))
        writer = csv.writer(stream)
        writer.writerow(["file", "state", "matched_templates"])
        plan_writer = None
        if solver:
            plan_stream = stack.enter_context((args.session / "solver_report.csv").open(
                "w", encoding="utf-8", newline=""))
            plan_writer = csv.writer(plan_stream)
            plan_writer.writerow(["file", "slot_count", "safe", "source_indices", "completed", "scores", "margins", "reason"])
        for path in files:
            screen = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            if screen is None:
                raise ValueError(f"Không đọc được ảnh: {path}")
            detection = detector.detect(screen)
            state = detection.state.name
            counts[state] += 1
            writer.writerow([path.name, state, ";".join(
                f"{name}:{match.confidence:.3f}" for name, match in detection.matches.items())])
            if state != previous:
                print(f"{path.name}: {state}", flush=True)
                previous = state
            if detection.state is FishingState.FISHING:
                board = find_target_board(screen)
                if board:
                    board_counts[len(board.centers)] += 1
                if solver and plan_writer:
                    plan = solver.plan(screen)
                    plan_counts["đủ tin cậy" if plan.safe else "từ chối"] += 1
                    plan_writer.writerow([path.name, len(board.centers) if board else "",
                                          plan.safe, [m.source_index + 1 for m in plan.matches],
                                          [m.completed for m in plan.matches],
                                          [round(m.confidence, 3) for m in plan.matches],
                                          [round(m.margin, 3) for m in plan.matches], plan.reason])
                    if plan.safe and not preview_saved:
                        save_debug_screenshot(draw_plan(screen, plan),
                                              args.session / "solver_preview" / path.name)
                        preview_saved = True
            else:
                preview_saved = False
    print(f"Tổng: {dict(counts)}\nBáo cáo: {report}")
    print(f"Số ô / số ảnh đo được: {dict(board_counts)}")
    if solver:
        print(f"Ghép hình: {dict(plan_counts)}\nBáo cáo: {args.session / 'solver_report.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
