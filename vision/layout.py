from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from .matcher import ROI


@dataclass(frozen=True)
class TargetBoard:
    left: int
    right: int
    centers: tuple[tuple[int, int], ...]


def find_target_board(screen: NDArray[np.uint8]) -> TargetBoard | None:
    """Đo bảng nằm giữa màn hình; mỗi ô có bước 126 px ở 1600×900."""
    if screen.shape != (900, 1600, 3):
        return None
    # Ô đã điền có hình sáng chạm hàng 655, làm đứt bảng nếu quét ở đó.
    # Đo dải dưới biểu tượng, lấy trung vị để loại các nét chéo mỏng.
    # Khu cá nóc: nhân vật/vật nuôi có thể che mép dưới. Thử mép trên
    # khi mép dưới không vượt được cùng các kiểm tra hình học.
    # Daytime dock planks join the lower edge and the upper rounded corner.
    # The straight top border at y=550 retains the same width/center checks.
    for scan_y in (660, 543, 550):
        x1, y1, x2, y2 = ROI(.10, scan_y / 900, .77, 3 / 900).bounds(screen)
        # HSV value is exactly max(B,G,R). Only three narrow scan lines are
        # needed; avoid converting the entire 1600x900 frame on every call.
        value = np.median(np.max(screen[y1:y2, x1:x2], axis=2), axis=0)
        row = cv2.morphologyEx((value < 140).astype(np.uint8)[None, :],
                               cv2.MORPH_CLOSE, np.ones((1, 9), np.uint8))[0]
        edges = np.diff(np.pad(row.astype(np.int8), (1, 1)))
        runs = [(int(a) + x1, int(b) + x1) for a, b in
                zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))
                if a + x1 < 798 < b + x1]
        if len(runs) != 1:
            continue
        left, right = runs[0]
        count = round((right - left) / 126)
        if (left <= x1 or right >= x2 or count < 1
                or abs((right - left) - count * 126) > 18
                or abs((left + right) / 2 - 798) > 10):
            continue
        center = (left + right) / 2
        centers = tuple((round(center + (index - (count - 1) / 2) * 126), 604)
                        for index in range(count))
        return TargetBoard(left, right, centers)
    return None
