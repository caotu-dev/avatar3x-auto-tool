"""Nhận map và các nút shop từ ảnh thật, dành cho luồng di chuyển."""
from pathlib import Path

import cv2
import numpy as np

from config.settings import ROOT
from vision.matcher import MatchResult, find_template, ROI


class WorldDetector:
    REGIONS={
        'menu':ROI(0,0,.12,.22),
        'fish_shop':ROI(.24,.05,.53,.22),
        'shop_menu':ROI(.30,.10,.40,.80),
        'shop_sign':ROI(0,.15,1,.45),
        'buy':ROI(.50,.40,.40,.55),
        'ok':ROI(.25,.20,.55,.70),
        'cancel':ROI(.30,.30,.45,.50),
    }
    def __init__(self, folder: Path = ROOT / "vision/templates/world"):
        self.fishing_detectors={}
        self.templates = {path.stem: cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8),
                                                cv2.IMREAD_GRAYSCALE)
                          for path in folder.glob("*.png")}

    def match(self, screen: np.ndarray, name: str) -> MatchResult | None:
        template = self.templates.get(name)
        if screen.shape != (900, 1600, 3) or template is None:
            return None
        gray=cv2.cvtColor(screen,cv2.COLOR_BGR2GRAY)
        region=self.REGIONS.get(name)
        found=find_template(gray, template, threshold=.98, contrast_invariant=True,roi=region)
        if found is None and name == 'menu':
            alternate = self.templates.get('menu_hamburger')
            if alternate is not None:
                found = find_template(gray,alternate,threshold=.98,contrast_invariant=True,roi=region)
                if found is not None and not (found.x < 180 and found.y < 120):
                    found = None
        if found is None and name=='shop_sign':
            # Players obscure the bottom of the lettering and the entrance arrow.
            # Match the unchanged upper lettering, preserving full-sign geometry.
            partial=find_template(gray,template[:round(template.shape[0]*.65)],
                                  threshold=.98,contrast_invariant=True,roi=region)
            if partial is not None and 180<partial.y<420:
                found=MatchResult(partial.x,partial.y,template.shape[1],template.shape[0],partial.confidence)
        return found

    def arrows(self, screen: np.ndarray) -> list[tuple[int, int]]:
        # Mũi tên có cùng sprite ở map; mép trái có thể cắt một nửa sprite.
        template = self.templates.get("arrow_mask")
        if template is None:
            return []
        mask = cv2.inRange(cv2.cvtColor(screen, cv2.COLOR_BGR2HSV),
                           (20, 140, 150), (38, 255, 255))
        points = []
        reference = max(cv2.findContours(template, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea)
        for contour in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            x, y, width, height = cv2.boundingRect(contour)
            if (y > 280 and 25 <= width <= 38 and 20 <= height <= 36
                    and 300 <= cv2.contourArea(contour) <= 500
                    and cv2.matchShapes(contour, reference, cv2.CONTOURS_MATCH_I1, 0) < .04):
                points.append((x + width // 2, y + height // 2))
        # Sprite ở mép trái có nền thay đổi: kiểm tra hình mũi tên qua mask vàng.
        hsv = cv2.cvtColor(screen[540:640, :25], cv2.COLOR_BGR2HSV)
        yellow = cv2.inRange(hsv, (20, 140, 150), (38, 255, 255))
        for contour in cv2.findContours(yellow, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            x, y, w, h = cv2.boundingRect(contour)
            if h >= 20 and w >= 8 and x <= 2:
                points.append((max(8, x + w // 2), 540 + y + h // 2))
        return sorted(points)

    def map_name(self, screen: np.ndarray, require_menu: bool = True) -> str | None:
        if self.match(screen, "shop_menu") or self.match(screen, "fish_shop"):
            return None
        if require_menu and not self.match(screen, "menu"):
            return None
        if self.match(screen, "shop_sign"):
            return "center"
        if self.match(screen, "shark_anchor"):
            return "ca_map"
        # Map cá rô do FishingDetector xác nhận bằng ao/ghế, không suy từ mùa.
        from .detector import FishingDetector
        boat = self.templates.get("boat")
        if (boat is not None and find_template(cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY),
                boat, threshold=.96, contrast_invariant=True)
                and np.mean(cv2.inRange(cv2.cvtColor(screen[515:700, 330:400], cv2.COLOR_BGR2HSV),
                                       (80, 60, 35), (115, 255, 255)) > 0) > .8):
            return "ca_noc"
        water_regions = (screen[558:756, 80:400], screen[558:756, 1250:1380])
        surrounded = all(np.count_nonzero(cv2.inRange(cv2.cvtColor(region, cv2.COLOR_BGR2HSV),
                                                     (80, 60, 35), (115, 255, 255))) / (region.shape[0] * region.shape[1]) > .8
                         for region in water_regions)
        if surrounded:
            if 'ca_map' not in self.fishing_detectors:
                self.fishing_detectors['ca_map']=FishingDetector(area='ca_map')
            if self.fishing_detectors['ca_map'].detect(screen).scene_confirmed:
                return 'ca_map'
        pond = cv2.inRange(cv2.cvtColor(screen[600:750, 500:1000], cv2.COLOR_BGR2HSV),
                           (80, 60, 35), (115, 255, 255))
        left = cv2.inRange(cv2.cvtColor(screen[558:756, 80:400], cv2.COLOR_BGR2HSV),
                           (80, 60, 35), (115, 255, 255))
        right = cv2.inRange(cv2.cvtColor(screen[558:756, 1250:1500], cv2.COLOR_BGR2HSV),
                            (80, 60, 35), (115, 255, 255))
        if np.mean(pond > 0) > .8 and np.mean(left > 0) > .8 and np.mean(right > 0) < .2:
            # Ao lớn bên trái, bờ bên phải; không phụ thuộc cây/trang trí theo mùa.
            return "ca_ro"
        return None
