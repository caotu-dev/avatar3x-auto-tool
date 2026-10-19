"""Di chuyển và mua Mồi Trùng theo số lượng đã xác minh trên ảnh."""
import json
import time
import re
import cv2
import numpy as np
from pathlib import Path
from typing import Callable

from adb.screenshot import save_event_screenshot
from vision.matcher import MatchResult
from .bot import OneRoundBot
from .detector import FishingDetector
from .states import FishingState
from .session import popup_outside_point
from .world import WorldDetector


class TravelController:
    def __init__(self, device, output: Path, clock: Callable = time.monotonic,
                 sleep: Callable = time.sleep, on_event: Callable | None = None):
        self.device, self.output = device, output
        self.clock, self.sleep = clock, sleep
        self.world = WorldDetector()
        self.screen = None
        self.index = 0
        self.bait_purchased = 0
        self.on_event = on_event
        self._interruption_detector = None
        self.output.mkdir(parents=True, exist_ok=True)

    def event(self, name: str, **details) -> None:
        filename = f"{self.index:03d}_{name}.png"
        if self.screen is not None:
            captured=save_event_screenshot(self.screen, self.output / filename, name, details)
            filename=captured.name if captured is not None else None
        with (self.output / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event": name, "image": filename, **details}, ensure_ascii=False) + "\n")
        self.index += 1
        if self.on_event is not None:
            self.on_event(name, details)

    def wait(self, predicate, label: str, timeout: float = 45, observations: int = 2,
             position_tolerance: tuple[int, int] = (8, 8), handle_interruptions: bool = True):
        deadline = self.clock() + timeout
        previous = None
        stable = 0
        loading_since=None
        overlay_key=None
        overlay_stable=0
        overlay_sent=False
        overlay_attempts=0
        overlay_sent_at=None
        overlay_since=None
        while self.clock() < deadline or loading_since is not None:
            self.screen = self.device.screenshot()
            if handle_interruptions:
                if self._interruption_detector is None:
                    self._interruption_detector=FishingDetector()
                interruption=self._interruption_detector.interruption(self.screen)
                if interruption is not None and interruption.state is FishingState.LOADING:
                    if loading_since is None:
                        self.event('WAIT_LOADING',expected=label)
                        loading_since=self.clock()
                    previous=None;stable=0;overlay_key=None;overlay_stable=0;overlay_sent=False
                    overlay_attempts=0;overlay_sent_at=None
                    self.sleep(.1)
                    continue
                if loading_since is not None:
                    deadline+=self.clock()-loading_since
                    loading_since=None
                point=None;kind=None
                if interruption is not None and interruption.state is FishingState.EXIT_CONFIRM:
                    point=interruption.matches['exit_no'].center;kind='exit'
                elif self.world.player_menu(self.screen):
                    kind='player'
                    point=self.world.player_menu_dismiss_point(self.screen)
                if kind:
                    key=(kind,point)
                    overlay_stable=overlay_stable+1 if key==overlay_key else 1
                    if key!=overlay_key:
                        overlay_sent=False;overlay_attempts=0;overlay_sent_at=None
                    overlay_key=key
                    if overlay_since is None:overlay_since=self.clock()
                    if (point and overlay_stable>=2 and overlay_attempts<3
                            and (not overlay_sent or self.clock()-overlay_sent_at>=3)):
                        self.tap(point,'Không: giữ game khi điều hướng' if kind=='exit' else 'Đóng menu người chơi đang che đường/shop')
                        overlay_sent=True
                        overlay_attempts+=1;overlay_sent_at=self.clock();overlay_stable=0
                    previous=None;stable=0
                    self.sleep(.02)
                    continue
                if overlay_since is not None:
                    # Allow the requested screen to settle after a verified
                    # dismissal, without granting stuck overlays infinite time.
                    deadline+=min(10,self.clock()-overlay_since)
                    overlay_since=None
                overlay_key=None;overlay_stable=0;overlay_sent=False
                overlay_attempts=0;overlay_sent_at=None
            value = predicate(self.screen)
            key = value.center if isinstance(value, MatchResult) else value
            same = key == previous
            if isinstance(value, MatchResult) and isinstance(previous, tuple):
                # Icon bản đồ nhấp nhô vài pixel; vẫn phải ở cùng vị trí, khác hẳn khi cuộn camera.
                same = all(abs(key[i] - previous[i]) <= position_tolerance[i] for i in (0, 1))
            stable = stable + 1 if value and same else 1
            if value and stable >= observations:
                return value
            previous = key
            self.sleep(.02)
        self.event("TIMEOUT", expected=label)
        raise RuntimeError(f"Không xác nhận được {label}; đã dừng thao tác")

    def tap(self, point: tuple[int, int], label: str):
        self.event("TAP", action=label, point=point)
        OneRoundBot._log(f"[DI CHUYỂN] {label}: {point}")
        self.device.tap(*point)

    def button(self, name: str, label: str):
        match = self.wait(lambda image: self.world.match(image, name), label,
                          handle_interruptions=name not in ('exit_yes','exit_no'))
        self.tap(match.center, label)

    def leave_chair(self, area: str, _late_popup_retry: bool = True):
        detector = FishingDetector(area=area)
        def outside(image):
            if area == 'dock':
                from .dock import DockDetector
                return DockDetector().detect(image).confirmed and self.world.match(image,'menu') is not None
            return self.world.map_name(image) == area
        self.wait(lambda image: True,'màn hình trước khi rời ghế',observations=1,timeout=10)
        if self.world.map_name(self.screen)=='center':return
        detection = detector.detect(self.screen)
        if detection.state is FishingState.SUCCESS:
            point = popup_outside_point(self.screen)
            if point is None:
                raise RuntimeError("Chưa có điểm an toàn để đóng popup cá trước khi rời khu")
            self.tap(point, "Đóng popup cá trước khi rời khu")
            self.wait(lambda image: detector.detect(image).state in
                      (FishingState.RESULT, FishingState.FAILED), "Xong sau popup cá")
            detection = detector.detect(self.screen)
        closed_no_bait = detection.state is FishingState.OUT_OF_BAIT
        if closed_no_bait:
            self.button("ok", "Đóng thông báo hết mồi")
            def after_no_bait(image):
                if outside(image):
                    return True
                observed = detector.detect(image)
                return (observed.scene_confirmed and 'close' in observed.matches and
                        observed.state in (FishingState.READY, FishingState.WAITING))
            self.wait(after_no_bait, "map ngoài ghế hoặc nút Đóng sau hết mồi", timeout=10)
            detection = detector.detect(self.screen)
        elif detection.state in (FishingState.RESULT, FishingState.FAILED):
            self.tap(detection.matches["finish"].center, "Xong trước khi rời khu")
            self.wait(lambda image: detector.detect(image).state is FishingState.READY, "Quăng câu")
            self.screen = self.device.screenshot()
            detection = detector.detect(self.screen)
        if detection.state is FishingState.READY or (
                closed_no_bait and detection.state is FishingState.WAITING
                and detection.scene_confirmed and 'close' in detection.matches):
            self.tap(detection.matches["close"].center, "Rời ghế")
            deadline = self.clock() + 10
            while self.clock() < deadline:
                self.screen = self.device.screenshot()
                if outside(self.screen):
                    return
                if detector.detect(self.screen).state is FishingState.EXIT_CONFIRM:
                    # Chỉ bấm Có sau thao tác chủ động rời ghế của luồng di chuyển.
                    self.button("exit_yes", "Có: rời ghế để về trung tâm")
                    break
                self.sleep(.3)
        def outside_or_no_bait(image):
            # The failed cast can briefly show the map before its no-bait
            # dialog arrives. Do not spend the entire navigation timeout
            # waiting underneath a newly appeared, verified popup.
            if detector.detect(image).state is FishingState.OUT_OF_BAIT:
                return 'no_bait'
            return 'outside' if outside(image) else None
        observed = self.wait(outside_or_no_bait, f"map {area} ngoài ghế")
        if observed == 'no_bait':
            if not _late_popup_retry:
                raise RuntimeError('Thông báo hết mồi xuất hiện lại khi rời khu; chưa điều hướng.')
            self.event('LATE_NO_BAIT_POPUP',area=area)
            self.leave_chair(area,_late_popup_retry=False)

    def center(self, area: str | None = None):
        self.wait(lambda image: True,'màn hình trước khi về trung tâm',observations=1,timeout=10)
        actual=self.world.map_name(self.screen)
        if actual == "center":
            return
        if actual in ('ca_ro','ca_noc','ca_map'):
            area=actual
        if area is None:
            area = self.world.map_name(self.screen, require_menu=False)
        if area not in ("ca_ro", "ca_noc", "ca_map"):
            self.event("UNKNOWN_MAP")
            raise RuntimeError("Chưa xác định map để về trung tâm")
        self.leave_chair(area)
        self.screen = self.device.screenshot()
        def exit_points(image):
            arrows = self.world.arrows(image)
            if area == 'ca_ro':
                return [p for p in arrows if p[0]>1400 and 500<p[1]<720]
            if area == 'ca_noc':
                return [p for p in arrows if p[0]<100 and 500<p[1]<720]
            return [p for p in arrows if p[1]>770]
        candidates = exit_points(self.screen)
        # A room change/seat exit can leave the camera on a middle pier. Reveal
        # the map edge, then detect its actual arrow; never tap a guessed exit.
        if not candidates and area in ('ca_ro','ca_noc'):
            for _ in range(5):
                if self.world.map_name(self.screen) != area:
                    raise RuntimeError('Mất xác nhận khu hiện tại khi tìm lối về trung tâm')
                start,end = ((300,650),(850,650)) if area=='ca_noc' else ((1450,650),(900,650))
                self.event('PAN_EXIT',area=area,start=start,end=end)
                OneRoundBot._log('[DI CHUYỂN] Kéo camera để tìm lối về trung tâm')
                self.device.swipe(*start,*end,500)
                self.sleep(.7)
                self.screen = self.device.screenshot()
                candidates = exit_points(self.screen)
                if candidates:
                    def exit_match(image):
                        points=exit_points(image)
                        return MatchResult(points[0][0]-1,points[0][1]-1,2,2,1.) if points else None
                    match=self.wait(exit_match,'mũi tên về trung tâm sau kéo camera',timeout=5)
                    candidates=[match.center]
                    break
        if not candidates:
            raise RuntimeError("Không thấy mũi tên về trung tâm của khu hiện tại")
        point = candidates[0]
        if area == "ca_map":
            point = (point[0], min(899, point[1] + 32))
        self.tap(point, "Về trung tâm")
        self.wait(lambda image: self.world.map_name(image) == "center", "khu trung tâm")

    def open_shop(self):
        for attempt in range(3):
            self.wait(lambda image:True,'màn hình trước khi mở shop',observations=1,timeout=10)
            if self.world.match(self.screen,'shop_menu'):
                return
            sign = self.wait(lambda image: self.world.match(image, "shop_sign"), "biển SHOP",timeout=10)
            offset=(-12,-65,45)[attempt]
            self.tap((sign.center[0] + offset, sign.center[1] + 123), "Mở shop")
            try:
                self.wait(lambda image: self.world.match(image, "shop_menu"), "menu shop",timeout=8)
                return
            except RuntimeError:
                if attempt==2:
                    raise
                self.event('SHOP_OPEN_RETRY',attempt=attempt+1)

    def purchase_matches(self, image, quantity: int, receipt: bool = False) -> bool:
        if quantity == 20:
            return bool(self.world.match(image, 'purchase_success20') if receipt else
                        self.world.match(image, 'purchase20') and self.world.match(image, 'quantity20'))
        from .quest import read_ocr, normalize
        import cv2
        path = self.output / 'quantity_check.png'
        cv2.imwrite(str(path), image[300:510, 420:1180])
        plain = normalize(' '.join(read_ocr(path)))
        crop = image.copy()
        crop[:300] = 0
        crop[510:] = 0
        if receipt:
            return bool(self.world.match(crop, 'receipt_worm_name') and self.world.match(crop, 'receipt_success')
                        and re.search(rf'\bmua\s+{quantity}\b', plain))
        # OCR en-US đọc sai dấu tiếng Việt: tên vật phẩm được kiểm bằng glyph thật,
        # OCR chỉ chịu trách nhiệm hai số trong phần mô tả (không đọc ô nhập).
        return bool(self.world.match(crop, 'purchase_worm_name')
                    and re.search(rf'\bmua\s+{quantity}\b', plain)
                    and re.search(rf'\b{quantity * 20}\s*xu\b', plain))

    def select_worm(self):
        for attempt in range(3):
            image=self.device.screenshot()
            if self.world.match(image,'worm') and self.world.match(image,'worm_price'):
                return
            if self.world.match(image,'fish_shop') is None:
                raise RuntimeError('Mất xác nhận shop khi chọn mồi; chưa mua.')
            self.tap((999,261),'Chọn Mồi Trùng (lần %d/3)' % (attempt+1))
            try:
                self.wait(lambda a:self.world.match(a,'worm') and self.world.match(a,'worm_price'),
                          'Mồi Trùng giá 20 xu',timeout=4)
                return
            except RuntimeError:
                if attempt==2:
                    raise

    def sell_and_buy(self, sell: bool = True, buy: bool = True, quantity: int = 20) -> int:
        if not isinstance(quantity, int) or not 1 <= quantity <= 50:
            raise ValueError('Số lượng mồi phải từ 1 đến 50')
        if not sell and not buy:
            return 0
        self.wait(lambda image: self.world.map_name(image) == "center", "trung tâm")
        if sell:
            self.open_shop()
            self.button("sell", "Bán cá")
            # The shop disappears before the sale receipt arrives. A transient
            # center frame is not evidence that the sale has finished.
            response = self.wait(lambda image: self.world.match(image, "ok"),
                                 "OK kết quả bán cá")
            for attempt in range(3):
                self.tap(response.center, "OK thông báo bán cá")
                try:
                    self.wait(lambda image: not self.world.match(image, "ok")
                              and self.world.map_name(image) == "center",
                              "trung tâm sau đóng thông báo bán cá", timeout=10)
                    break
                except RuntimeError:
                    if attempt == 2:
                        raise
                    # Retrying a verified dismissal is safe; never sell again.
                    response = self.wait(lambda image: self.world.match(image, "ok"),
                                         "OK bán cá còn mở để thử đóng lại", timeout=10)
            self.event("SALE_CONFIRMED")
        if not buy:
            self.wait(lambda image: self.world.map_name(image) == "center", "trung tâm sau bán")
            return 0
        for attempt in range(2):
            self.open_shop()
            self.button("shop_menu", "Cửa Hàng Cá")
            response = self.wait(lambda image: self.world.match(image, "fish_shop")
                                 or ("center" if self.world.map_name(image) == "center" else None),
                                 "giao diện cửa hàng cá hoặc trở lại trung tâm")
            if isinstance(response, MatchResult):
                break
            self.event("SHOP_MENU_CLOSED", retry=attempt + 1)
        else:
            raise RuntimeError("Menu shop đóng hai lần; chưa mua, đã dừng")
        self.select_worm()
        self.button("buy", "Mua Mồi Trùng")
        self.wait(lambda image: self.world.match(image, "purchase_confirm"), "xác nhận Mồi Trùng")
        self.tap((798, 500), "Ô số lượng")
        self.wait(lambda image: self.world.match(image, "input_ok"), "ô nhập số lượng Android")
        self.event("TYPE_QUANTITY", quantity=quantity)
        self.device.type_number(quantity)
        self.wait(lambda image: self.purchase_matches(image, quantity), f"{quantity} Mồi Trùng giá {quantity * 20} xu")
        self.button("input_ok", "OK số lượng")
        self.wait(lambda image: self.purchase_matches(image, quantity), f"số lượng {quantity} sau đóng ô nhập")
        self.event("PURCHASE_PENDING", quantity=quantity)
        self.button("buy_coin", f"Mua bằng xu: {quantity} mồi / {quantity * 20} xu")
        response = self.wait(lambda image: 'capacity' if self.world.match(image, 'bait_capacity') else
                             ('bought' if self.purchase_matches(image, quantity, receipt=True) else None), "kết quả mua mồi")
        bought = response == 'bought'
        if bought:
            self.bait_purchased += quantity
            self.event("PURCHASE_CONFIRMED", quantity=quantity, coins=quantity * 20, bait="Mồi Trùng")
            (self.output / "purchases.json").write_text(json.dumps({"bait_purchased": self.bait_purchased}, indent=2), encoding="utf-8")
        else:
            self.event("PURCHASE_REJECTED_CAPACITY", quantity=quantity, counted=0)
            OneRoundBot._log("[SHOP] Giới hạn 50 mồi; không mua thêm, dùng mồi đang có")
        self.button("ok", "OK kết quả mua mồi")
        self.wait(lambda image: self.world.match(image, "fish_shop"), "shop sau mua")
        self.tap((200, 650), "Bấm ngoài để đóng shop")
        self.wait(lambda image: self.world.map_name(image) == "center", "trung tâm sau đóng shop")
        return quantity if bought else 0

    def enter(self, area: str):
        self.wait(lambda image: self.world.map_name(image) == "center", "trung tâm trước chuyển khu")
        if area == "ca_ro":
            for _ in range(3):
                self.screen = self.device.screenshot()
                candidates = [point for point in self.world.arrows(self.screen)
                              if point[0] < 100 and 500 < point[1] < 720]
                if candidates:
                    self.tap(candidates[0], "Sang khu cá rô")
                    break
                if self.world.map_name(self.screen) != "center":
                    raise RuntimeError("Mất xác nhận trung tâm khi tìm cửa trái")
                self.device.swipe(300, 650, 850, 650, 500)
                self.wait(lambda image: self.world.map_name(image) == "center", "trung tâm sau kéo camera")
            else:
                raise RuntimeError("Không thấy cửa trái khu cá rô")
        elif area == "ca_noc":
            for _ in range(3):
                self.screen = self.device.screenshot()
                candidates = [point for point in self.world.arrows(self.screen)
                              if point[0] > 1400 and 500 < point[1] < 720]
                if candidates:
                    self.tap(candidates[-1], "Sang khu cá nóc")
                    break
                if self.world.map_name(self.screen) != "center":
                    raise RuntimeError("Mất xác nhận trung tâm khi tìm lối bên phải")
                self.event("PAN_RIGHT", start=(1450, 650), end=(900, 650))
                OneRoundBot._log("[DI CHUYỂN] Kéo camera sang phải để hiện cửa khu cá nóc")
                self.device.swipe(1450, 650, 900, 650, 500)
                try:
                    self.wait(lambda image: any(x > 1400 and 500 < y < 720
                                               for x, y in self.world.arrows(image)),
                              "mũi tên khu cá nóc", timeout=5)
                except RuntimeError:
                    # Tối đa ba lần kéo camera trong map trung tâm đã xác nhận.
                    self.wait(lambda image: self.world.map_name(image) == "center", "trung tâm khi đi sang phải")
                    if self.uncover_center_exit():
                        try:
                            self.wait(lambda image:any(x>1400 and 500<y<720 for x,y in self.world.arrows(image)),
                                      'mũi tên sau khi tránh che lối',timeout=5)
                        except RuntimeError:
                            continue
                    else:
                        continue
                # Use the frame just verified, including the last allowed pan.
                candidates=[p for p in self.world.arrows(self.screen) if p[0]>1400 and 500<p[1]<720]
                if candidates:
                    self.tap(candidates[-1],'Sang khu cá nóc')
                    break
            else:
                raise RuntimeError("Không thấy lối khu cá nóc")
        elif area == "ca_map":
            self.screen = self.device.screenshot()
            sign = self.world.match(self.screen, "shop_sign")
            candidates = [point for point in self.world.arrows(self.screen)
                          if sign is not None and point[0] < sign.center[0] - 250
                          and 250 < point[1] < sign.center[1] + 40]
            if len(candidates) != 1:
                raise RuntimeError("Chưa xác nhận được lối trên khu cá mập")
            self.tap((candidates[0][0], candidates[0][1] + 32), "Sang khu cá mập")
        else:
            raise ValueError("Luồng hiện khảo sát cá nóc rồi cá mập")
        self.wait(lambda image: self.world.map_name(image) == area, f"map {area}")

    def uncover_center_exit(self):
        """Move off the right exit only onto verified empty stone pavement."""
        self.screen=self.device.screenshot()
        if self.world.map_name(self.screen)!='center':
            return False
        for x,y in ((1300,710),(1200,740),(1100,740)):
            patch=cv2.cvtColor(self.screen[y-20:y+20,x-30:x+30],cv2.COLOR_BGR2HSV)
            pavement=cv2.inRange(patch,(0,0,60),(179,55,230))
            if np.mean(pavement>0)>.9:
                self.tap((x,y),'Bước sang đường trống để tránh che lối khu cá nóc')
                self.sleep(1.5)
                return True
        return False
