"""Nhận dòng tên cá tiếng Việt trên popup; chỉ đọc ảnh, không gửi input."""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from config.settings import ROOT


SPECIES = {"ca_ro": "Cá rô", "ca_chep_vang": "Cá chép vàng",
           "ca_long_tong": "Cá lòng tong", "ca_noc": "Cá nóc",
           "ca_loc": "Cá lóc", "cua": "Cua", "ca_duoi": "Cá đuối",
           "ca_chim": "Cá chim", "ca_ngua": "Cá ngựa",
           "ca_vang": "Cá vàng", "ca_chep": "Cá chép", "ca_he": "Cá hề",
           "ca_lia_thia": "Cá lia thia"}
AREA_SPECIES = {"ca_ro": {"ca_ro", "ca_chep_vang", "ca_long_tong"},
                "ca_noc": {"ca_noc", "ca_loc", "cua"},
                "ca_map": {"ca_duoi", "ca_chim", "ca_ngua"},
                "dock": {"ca_vang", "ca_chep", "ca_he", "ca_lia_thia"}}


@dataclass(frozen=True)
class CatchDetection:
    species: str | None
    name: str
    confidence: float


class CatchDetector:
    def __init__(self, templates: Path = ROOT / "vision/templates/fish", area: str | None = None):
        self.templates = {}
        for species in SPECIES:
            if area in AREA_SPECIES and species not in AREA_SPECIES[area]:
                continue
            path = templates / f"{species}.png"
            if path.is_file():
                self.templates[species] = cv2.imdecode(
                    np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)

    def detect(self, screen: np.ndarray) -> CatchDetection:
        unknown = CatchDetection(None, "Chưa xác định", 0.0)
        if screen.shape != (900, 1600, 3):
            return unknown
        # Cố định ROI trong popup 1600x900, không phụ thuộc nhân vật/background.
        hsv = cv2.cvtColor(screen[710:780, 450:1150], cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (95, 60, 70), (120, 255, 230))
        points = cv2.findNonZero(mask)
        if points is None:
            return unknown
        x, y, width, height = cv2.boundingRect(points)
        line = mask[y:y + height, x:x + width]
        scores = []
        for species, template in self.templates.items():
            if template is None or min(template.shape) == 0:
                continue
            if abs(template.shape[0] - height) > 2 or abs(template.shape[1] - width) > 2:
                continue
            # Bỏ câu chung dài 267 px; phần tên quyết định đáp án.
            glyph = line[:, 267:]
            reference = template[:, 267:]
            if min(glyph.shape) == 0 or min(reference.shape) == 0:
                continue
            glyph = cv2.resize(glyph, (reference.shape[1], reference.shape[0]), interpolation=cv2.INTER_NEAREST)
            response = cv2.matchTemplate(glyph, reference, cv2.TM_CCOEFF_NORMED)
            score = float(cv2.minMaxLoc(response)[1])
            if np.isfinite(score):
                scores.append((score, species))
        scores.sort(reverse=True)
        if not scores:
            return unknown
        score, species = scores[0]
        runner_up = scores[1][0] if len(scores) > 1 else 0.0
        if score < .95 or score - runner_up < .04:
            return CatchDetection(None, "Chưa xác định", round(score, 4))
        return CatchDetection(species, SPECIES[species], round(score, 4))
