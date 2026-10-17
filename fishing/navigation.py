"""Đi giữa khu câu cá, phòng Hành chính và Bến tàu qua bản đồ thế giới."""
import json
import time
from datetime import datetime, timezone

import cv2
import numpy as np

from config.settings import ROOT
from vision.matcher import find_template, MatchResult
from .travel import TravelController
from .bot import OneRoundBot


class MapNavigator(TravelController):
    def __init__(self, device, output=None, **kwargs):
        super().__init__(device, output or ROOT / "debug/navigation" /
                         datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f"), **kwargs)
        self.templates = {path.stem: cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                          for path in (ROOT / "vision/templates/navigation").glob("*.png")}
        self.visited = []

    def match(self, screen, name):
        template = self.templates.get(name)
        if template is None or screen.shape != (900, 1600, 3):
            return None
        # Fishing marker water ripples animate independently of its rod/foliage.
        # Match the static upper portion, retaining the original click center.
        reference = template[:40] if name == 'fishing' else template
        found = find_template(cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY), reference,
                              threshold=.96, contrast_invariant=True)
        if found is None and name+'_day' in self.templates:
            found = find_template(cv2.cvtColor(screen,cv2.COLOR_BGR2GRAY),self.templates[name+'_day'],
                                  threshold=.96,contrast_invariant=True)
        if found is not None and name == 'fishing':
            return MatchResult(found.x, found.y, template.shape[1], template.shape[0], found.confidence)
        return found

    def is_world(self, screen):
        return (self.match(screen, "world_menu") is not None and
                any(self.match(screen, name) for name in ('city', 'fishing', 'entertainment', 'suburb')))

    def is_beach(self, screen):
        water = cv2.inRange(cv2.cvtColor(screen[180:380, 400:1100], cv2.COLOR_BGR2HSV),
                            (80, 60, 80), (115, 255, 255))
        sand = cv2.inRange(cv2.cvtColor(screen[520:650, 400:1100], cv2.COLOR_BGR2HSV),
                           (15, 50, 120), (40, 255, 255))
        return np.mean(water > 0) > .85 and np.mean(sand > 0) > .85

    def location(self, screen):
        if self.is_world(screen):
            return "world"
        if self.match(screen, "office_shelf") and (self.match(screen, "office_door")
                                                   or self.match(screen, "exit_question")):
            return "administration"
        from .dock import DockDetector
        if self.match(screen, "pier_shop") or DockDetector().detect(screen).confirmed:
            return "dock"
        if self.match(screen, "hall_facade"):
            return "entertainment"
        if self.match(screen, "suburb_fruit") or self.match(screen, "banner_suburb"):
            return "suburb"
        if self.match(screen, "beach_sign") or self.is_beach(screen):
            return "beach"
        if self.world.map_name(screen, require_menu=False) == "center":
            return "fishing"
        return None

    def save_location(self, location):
        state = {"location": location, "verified_at": datetime.now(timezone.utc).isoformat(),
                 "log": str(self.output), "visited": self.visited}
        path = ROOT / "runtime/navigation.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
        self.event("ARRIVED", location=location)

    def open_world(self):
        self.screen = self.device.screenshot()
        if self.is_world(self.screen):
            return
        if self.location(self.screen)=='dock':
            self.leave_chair('dock')
            self.screen=self.device.screenshot()
        if self.location(self.screen) == "administration":
            if not self.match(self.screen, "exit_question"):
                arrows = [p for p in self.world.arrows(self.screen) if 650 < p[0] < 950 and p[1] > 770]
                if len(arrows) != 1:
                    raise RuntimeError("Chưa thấy lối ra phòng Hành chính")
                self.tap((arrows[0][0], min(899, arrows[0][1] + 35)), "Ra ngoài Hành chính")
                self.wait(lambda a: self.location(a) == "entertainment" or self.match(a, "exit_question"),
                          "xác nhận rời Hành chính")
            if self.match(self.screen, "exit_question"):
                self.button("exit_yes", "Có: rời Hành chính")
            self.wait(lambda a: self.location(a) == "entertainment", "ngoài đường Khu giải trí")
        menu = self.world.match(self.screen, "menu")
        if menu is None:
            menu = self.match(self.screen, 'world_menu')
        if menu is None:
            # Các ao riêng dùng luồng đã xác minh để rời ghế và ra trung tâm.
            area = self.world.map_name(self.screen, require_menu=False)
            if area in ("ca_ro", "ca_noc", "ca_map"):
                self.center(area)
                menu = self.world.match(self.screen, "menu")
        if menu is None:
            raise RuntimeError("Không thấy Menu; chưa mở bản đồ")
        button = self.match(self.screen, "map_button")
        if button is None:
            self.tap(menu.center, "Menu")
            button = self.wait(lambda a: self.match(a, "map_button"), "icon Map", timeout=8)
        self.tap(button.center, "Map")
        self.wait(self.is_world, "bản đồ thế giới", timeout=15)

    def find_marker(self, region):
        # Đưa camera về góc trên trái rồi quét ngang; không giả định vị trí icon trên màn hình.
        scans = [(800, 230, 800, 760)] * 2 + [(300, 500, 1350, 500)] * 2
        scans += [(1350, 500, 350, 500)] * 3
        for swipe in [None, *scans]:
            if swipe is not None:
                self.screen=self.device.screenshot()
                if not self.is_world(self.screen):
                    raise RuntimeError('Chưa xác nhận bản đồ trước khi kéo tìm khu')
                markers=[self.match(self.screen,name) for name in ('city','fishing','entertainment','suburb')]
                dx,dy=swipe[2]-swipe[0],swipe[3]-swipe[1]
                candidates=[swipe,*[(x,y,x+dx,y+dy) for x,y in ((1250,230),(450,230),(1350,500),(300,500))]]
                def clear(candidate):
                    points=(candidate[:2],candidate[2:])
                    return all(20<x<1580 and 60<y<860 and not any(
                        m is not None and m.x-60<x<m.x+m.width+60 and m.y-60<y<m.y+m.height+60
                        for m in markers) for x,y in points)
                swipe=next((c for c in candidates if clear(c)),None)
                if swipe is None:
                    raise RuntimeError('Không có điểm kéo bản đồ tránh icon khu')
                self.event("PAN_WORLD", direction=swipe)
                self.device.swipe(*swipe, duration_ms=400)
                self.sleep(.4)
            # Mây có thể che icon tạm thời; chờ hai lần cùng tọa độ trước khi bấm.
            try:
                return self.wait(lambda a: self.match(a, region) if self.is_world(a) else None,
                                 f"icon {region}", timeout=5,
                                 position_tolerance=(8, 20) if region == "fishing" else (8, 8))
            except RuntimeError:
                if not self.is_world(self.screen):
                    raise RuntimeError("Đã rời bản đồ trong lúc tìm icon")
        raise RuntimeError(f"Không tìm được icon {region} sau khi cuộn có giới hạn")

    def go_region(self, region):
        if region not in ("fishing", "entertainment", "suburb"):
            raise ValueError(f"Khu chưa hỗ trợ: {region}")
        self.screen = self.device.screenshot()
        if self.location(self.screen) == region:
            return
        self.open_world()
        for attempt in range(3):
            marker = self.find_marker(region)
            self.tap(marker.center, f"Vào {region}")
            try:
                self.wait(lambda a: self.location(a) == region or self.match(a, f"banner_{region}"),
                          f"khu {region}", timeout=25)
                break
            except RuntimeError:
                # A map tap can be dropped while its camera/banner animates.
                # Never retry against a loading screen or another destination.
                self.screen = self.device.screenshot()
                if attempt == 2 or not self.is_world(self.screen):
                    raise
                self.wait(self.is_world, "bản đồ trước thử vào khu lại", timeout=5)
                self.event("RETRY_ENTER_REGION", region=region, attempt=attempt + 2)
                OneRoundBot._log(f"[DI CHUYỂN] Vẫn ở bản đồ; thử vào {region} lần {attempt + 2}/3")
        self.save_location(region)

    def enter_administration(self):
        self.go_region("entertainment")
        facade = self.wait(lambda a: self.match(a, "hall_facade"), "cửa Hành chính")
        self.tap((facade.center[0], facade.center[1] + 170), "Vào Hành chính")
        self.wait(lambda a: self.location(a) == "administration", "trong Hành chính", timeout=25)

    def enter_dock(self):
        self.go_region("suburb")
        gate = self.wait(lambda a: self.match(a, "dock_gate"), "cổng vỏ sò")
        self.tap((gate.center[0], gate.center[1] + 128), "Vào bãi biển")
        self.wait(lambda a: self.location(a) == "beach", "bãi biển", timeout=25)
        if not self.match(self.screen, "beach_sign"):
            self.device.swipe(300, 650, 1350, 650, duration_ms=400)
            self.wait(lambda a: self.match(a, "beach_sign"), "lối trái bãi biển", timeout=8)
        arrows = [p for p in self.world.arrows(self.screen) if p[0] < 150 and p[1] > 700]
        if len(arrows) != 1:
            raise RuntimeError("Chưa xác định lối trái tới Bến tàu")
        self.tap((arrows[0][0], arrows[0][1] + 35), "Vào Bến tàu")
        self.wait(lambda a: self.match(a, "pier_intro") or self.match(a, "pier_shop"), "Bến tàu", timeout=25)
        if self.match(self.screen, "pier_intro"):
            button = self.wait(lambda a: self.match(a, "pier_intro_ok"), "OK giới thiệu Bến tàu")
            self.tap(button.center, "Đóng giới thiệu Bến tàu")
        self.wait(lambda a: self.location(a) == "dock", "Bến tàu ngoài popup")

    def go(self, destination):
        if destination not in ("fishing", "administration", "dock"):
            raise ValueError(f"Đích chưa hỗ trợ: {destination}")
        self.screen = self.device.screenshot()
        if self.location(self.screen) != destination:
            if destination == "administration":
                self.enter_administration()
            elif destination == "dock":
                self.enter_dock()
            else:
                self.go_region("fishing")
        self.visited.append(destination)
        self.save_location(destination)

    def test_route(self):
        for destination in ("fishing", "administration", "dock", "fishing"):
            self.go(destination)
        self.event("COMPLETE", route=self.visited)
        return self.visited
