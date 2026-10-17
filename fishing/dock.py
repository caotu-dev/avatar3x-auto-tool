"""Nhận diện bến tàu từ mẫu thực tế; kiểm tra điều kiện trước khi câu."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from config.settings import ROOT
from vision.matcher import MatchResult, ROI, find_template
from .travel import TravelController


@dataclass(frozen=True)
class DockObservation:
    confirmed: bool
    level_locked: bool
    boats: tuple[MatchResult, ...]
    shop: MatchResult | None
    room_sign: MatchResult | None
    room_menu: bool
    bait_selected: bool


class DockDetector:
    def __init__(self):
        self.templates = {p.stem: cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
                          for p in (ROOT / 'vision/templates/dock').glob('*.png')}

    def match(self, screen, name, roi=None, *, gray=None):
        if screen.shape != (900, 1600, 3):
            return None
        if gray is None:
            gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        found = find_template(gray,
                             self.templates[name], threshold=.96, roi=roi,
                             contrast_invariant=True)
        if found is None and name+'_day' in self.templates:
            found=find_template(gray,self.templates[name+'_day'],
                                threshold=.96,roi=roi,contrast_invariant=True)
        return found

    def detect(self, screen, *, gray=None) -> DockObservation:
        if screen.shape != (900, 1600, 3):
            return DockObservation(False, False, (), None, None, False, False)
        # This frame is immutable during detection. Share its conversion only
        # within this call; never retain an ndarray cache across screenshots.
        if gray is None:
            gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        def match(name, roi=None):
            return self.match(screen, name, roi, gray=gray)
        shop = match('shop')
        water = cv2.inRange(cv2.cvtColor(screen[120:170, 600:1100], cv2.COLOR_BGR2HSV),
                            (80, 60, 35), (115, 255, 255))
        confirmed = shop is not None and np.mean(water > 0) > .85
        locked = match('level_required', ROI(.20, .35, .60, .22)) is not None
        rooms = match('rooms_corner', ROI(.25, .20, .15, .15)) is not None
        boats = []
        # Thuyền ngang sát cầu: loại thuyền có mái chèo ở phía trên không dùng làm chỗ ngồi.
        # Mẫu toàn bộ lòng thuyền loại các chỗ bị nhân vật che.
        if confirmed and not locked and not rooms:
            for y in (280, 360, 440, 520):
                boat = match('boat_empty', ROI(.07, (y-48)/900, .20, 100/900))
                if boat and not any(abs(boat.y - old.y) < 30 for old in boats):
                    boats.append(boat)
        bait = (match('bait_name', ROI(.30, .50, .30, .16)) is not None
                and match('bait_price', ROI(.30, .55, .20, .12)) is not None)
        return DockObservation(confirmed, locked, tuple(boats), shop,
                               match('room_sign', ROI(0, .55, .25, .25)), rooms, bait)


class DockController(TravelController):
    """Preflight đã kiểm tra trên game; chưa quăng/mua khi cấp chưa đủ."""
    def __init__(self, device, output: Path | None = None, state_path: Path | None = None, **kwargs):
        super().__init__(device, output or ROOT / 'debug/dock' /
                         datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f'), **kwargs)
        self.detector = DockDetector()
        self.state_path = state_path or ROOT / 'runtime/dock.json'
        self.state = json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {
            'area': 'dock', 'bait': {'name': 'Mồi Câu Cá Trâm', 'unit_price': 50,
                                    'remaining': None, 'purchased': 0},
            'fish_counts': {}, 'casts': 0, 'bites': 0, 'misses': 0,
            'catalog': {}, 'room': None}

    def save(self, status, reason):
        self.state.update(status=status, reason=reason, log=str(self.output),
                          updated_at=datetime.now(timezone.utc).isoformat())
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.state_path)
        self.event(status, reason=reason)
        return self.state

    def check(self):
        self.screen = self.device.screenshot()
        from .detector import FishingDetector
        from .states import FishingState
        fishing=FishingDetector(area='dock')
        if fishing.detect(self.screen).state is FishingState.OUT_OF_BAIT:
            return self.save('OUT_OF_BAIT','Hết Mồi Câu Cá Trâm tại Bến Tàu')
        observation = self.detector.detect(self.screen)
        if observation.level_locked:
            return self.save('LEVEL_REQUIRED', 'Nhân vật chưa đủ cấp câu cá 10 để vào Bến Tàu')
        if not observation.confirmed:
            return self.save('UNKNOWN', 'Chưa xác nhận bến tàu; không thao tác')
        from .detector import FishingDetector
        from .states import FishingState
        fishing=FishingDetector(area='dock')
        current=fishing.detect(self.screen)
        if current.state is FishingState.READY:
            return self.save('READY','Đã xác nhận Quăng câu tại Bến Tàu')
        if current.state in (FishingState.WAITING,FishingState.FISHING):
            return self.save('IN_PROGRESS','Đang có lượt câu bến tàu; không chọn thuyền mới')
        if not observation.boats and observation.room_sign is None:
            self.device.swipe(300,520,1350,520,400)
            self.sleep(.9)
            self.screen=self.device.screenshot()
            observation=self.detector.detect(self.screen)
            if not observation.confirmed:
                return self.save('UNKNOWN','Chưa xác nhận Bến Tàu sau cuộn camera')
        if not observation.boats:
            return self.save('NO_SEAT', 'Chưa thấy lòng thuyền trống đủ tin cậy')
        boat = max(observation.boats, key=lambda b: b.y)
        # Điểm tương tác đã thử nằm ở mép phải dưới thuyền trái, trên đường cầu gỗ.
        point = boat.x + boat.width - 3, boat.y + boat.height - 15
        self.tap(point, 'Chọn thuyền trống')
        deadline = self.clock() + 20
        ready_frames=0
        while self.clock() < deadline:
            self.screen = self.device.screenshot()
            if self.detector.detect(self.screen).level_locked:
                return self.save('LEVEL_REQUIRED', 'Nhân vật chưa đủ cấp câu cá 10 để vào Bến Tàu')
            state=fishing.detect(self.screen).state
            if state is FishingState.OUT_OF_BAIT:
                return self.save('OUT_OF_BAIT','Hết Mồi Câu Cá Trâm khi chọn thuyền')
            ready_frames=ready_frames+1 if state is FishingState.READY else 0
            if ready_frames>=2:
                return self.save('READY','Đã xác nhận Quăng câu tại Bến Tàu')
            self.sleep(.3)
        return self.save('UNVERIFIED', 'Chưa xác minh được màn hình câu bến tàu; không quăng hay mua mồi')

    def change_room(self, room: int):
        if type(room) is not int or not 0 <= room <= 15:
            raise ValueError('Khu bến tàu đã xác minh: 0–15')
        self.screen = self.device.screenshot()
        observation = self.detector.detect(self.screen)
        if observation.level_locked or not (observation.confirmed or observation.room_menu):
            raise RuntimeError('Cần bến tàu ngoài popup trước khi đổi khu')
        if not observation.room_menu:
            sign = observation.room_sign
            if sign is None:
                self.device.swipe(300,520,1350,520,400)
                self.sleep(.9)
                sign=self.detector.detect(self.device.screenshot()).room_sign
            if sign is None:
                raise RuntimeError('Không nhận diện biển KHU')
            self.tap((sign.center[0], sign.y + 93), 'Mở chọn khu bến tàu')
        self.wait(lambda a: self.detector.detect(a).room_menu, 'bảng chọn khu bến tàu', timeout=20)
        self.tap((573 + 150 * (room % 4), 285 + 150 * (room // 4)), f'Chọn khu {room}')
        self.wait(lambda a: self.detector.match(a, 'intro'), 'giới thiệu khu bến tàu', timeout=20)
        self.tap((798, 581), 'OK giới thiệu bến tàu')
        self.wait(lambda a: self.detector.detect(a).confirmed and
                  self.detector.detect(a).room_sign is not None and
                  not self.detector.match(a, 'intro'), 'bến tàu sau chuyển khu', timeout=10)
        self.state['room'] = room
        self.save('ROOM_CHANGED', f'Đã chọn khu {room}')
