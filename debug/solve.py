import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np

from adb.screenshot import save_debug_screenshot
from fishing.solver import FishingSolver, SolvePlan


def draw_plan(screen: np.ndarray, plan: SolvePlan) -> np.ndarray:
    annotated = screen.copy()
    for match in plan.matches:
        color = (0, 220, 0) if plan.safe else (0, 150, 255)
        cv2.circle(annotated, match.source, 45, color, 2)
        cv2.circle(annotated, match.target, 48, color, 2)
        if not match.completed:
            cv2.arrowedLine(annotated, match.source, match.target, color, 2, tipLength=.025)
        label = (f"T{match.target_index + 1} <- S{match.source_index + 1} "
                 f"{match.confidence:.2f} gap {match.margin:.2f}"
                 f"{' DONE' if match.completed else ''}")
        cv2.putText(annotated, label, (420, 40 + match.target_index * 30),
                    cv2.FONT_HERSHEY_SIMPLEX, .6, color, 2)
    return annotated


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Vẽ kế hoạch kéo trên ảnh, không điều khiển game")
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    screen = cv2.imdecode(np.frombuffer(args.image.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    if screen is None:
        parser.error("Không đọc được ảnh")
    plan = FishingSolver().plan(screen)
    output = args.image.parent / "solver_preview"
    output.mkdir(exist_ok=True)
    for match in plan.matches:
        label = f"T{match.target_index + 1} <- S{match.source_index + 1} {match.confidence:.2f} gap {match.margin:.2f}"
        print(label, "đã điền" if match.completed else "chưa điền")
    save_debug_screenshot(draw_plan(screen, plan), output / args.image.name)
    (output / f"{args.image.stem}.json").write_text(
        json.dumps(asdict(plan), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{plan.reason} | đủ tin cậy: {plan.safe}\nẢnh: {output / args.image.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
