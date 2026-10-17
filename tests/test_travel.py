import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import cv2

from fishing.travel import TravelController
from fishing.statistics import fishing_statistics
from fishing.bot import TrialResult
from tests.test_bot import Clock


class LateBaitPopupTests(unittest.TestCase):
    def test_late_shark_no_bait_popup_is_closed_before_navigation(self):
        import numpy as np
        from fishing.world import WorldDetector
        image=cv2.imread(str(Path(__file__).parent/'fixtures/shark_no_bait_navigation.png'))
        class Device:
            calls=0
            def __init__(self):self.taps=[]
            def screenshot(self):
                self.calls+=1
                return np.zeros_like(image) if self.calls==1 or self.taps else image.copy()
            def tap(self,x,y):self.taps.append((x,y))
        device=Device();clock=Clock()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            controller=TravelController(device,Path(folder),clock.read,clock.sleep)
            original=controller.world.map_name
            controller.world.map_name=lambda screen,**kwargs: 'ca_map' if device.taps else None
            controller.leave_chair('ca_map')
        self.assertEqual(device.taps,[(798,581)])

    def test_hamburger_menu_is_detected_on_reported_shark_screen(self):
        from fishing.world import WorldDetector
        image=cv2.imread(str(Path(__file__).parent/'fixtures/shark_no_bait_navigation.png'))
        self.assertIsNotNone(WorldDetector().match(image,'menu'))


class ShopDevice:
    def __init__(self, fail_purchase=False, fail_number=False, capacity=False, closed_shop_once=False):
        self.state = "center_right"
        self.inputs = []
        self.buy_count = 0
        self.fail_purchase, self.fail_number = fail_purchase, fail_number
        self.sold = False
        self.capacity = capacity
        self.closed_shop_once = closed_shop_once

    def screenshot(self):
        folder = Path(__file__).parent / "fixtures"
        image = cv2.imread(str(folder / f"{self.state}.png"))
        if self.state == "quantity_input1":
            # Thiết bị giả: popup số 1 và ô nhập Android đã mở hoàn toàn.
            # Frame thật số 1 ghi đúng lúc ô nhập đang trượt lên.
            image = cv2.imread(str(folder / "quantity1.png"))
            image[795:] = cv2.imread(str(folder / "quantity_input20.png"))[795:]
        return image

    def tap(self, x, y):
        if self.state == "center_right":
            self.state = "shop_menu"
        elif self.state == "shop_menu":
            if y > 300:
                self.state = "purchase20"
                self.sold = True
            else:
                self.state = "center_right" if self.closed_shop_once else "worm_selected"
                self.closed_shop_once = False
        elif self.state == "worm_selected" and x > 900 and y > 500:
            self.state = "quantity1"
        elif self.state == "worm_selected" and x < 400:
            self.state = "center_right"
        elif self.state == "quantity1":
            self.state = "quantity_input1"
        elif self.state == "quantity_input20":
            self.state = "quantity20"
        elif self.state == "quantity20":
            self.buy_count += 1
            self.state = "bait_capacity" if self.capacity else "worm_selected" if self.fail_purchase else "purchase20"
            self.sold = False
        elif self.state == "purchase20":
            self.state = "center_right" if self.sold else "worm_selected"
        elif self.state == "bait_capacity":
            self.state = "worm_selected"

    def type_number(self, value):
        self.inputs.append(value)
        if not self.fail_number:
            self.state = "quantity_input20"


class TravelTests(unittest.TestCase):
    def test_occluded_shop_retries_dropped_open_without_payment(self):
        blocked=cv2.imread(str(Path(__file__).parent/'fixtures/shop_entrance_occluded.png'))
        menu=cv2.imread(str(Path(__file__).parent/'fixtures/shop_menu.png'))
        clock=Clock()
        class Device:
            taps=[]
            def screenshot(self):
                clock.sleep(1)
                return menu if len(self.taps)>=2 else blocked
            def tap(self,*point):self.taps.append(point)
        device=Device()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            controller=TravelController(device,Path(folder),clock.read,clock.sleep)
            controller.open_shop()
        self.assertEqual(device.taps,[(1011,425)]*2)

    def test_own_avatar_occludes_exit_until_it_moves_to_pavement(self):
        blocked=cv2.imread(str(Path(__file__).parent/'fixtures/center_exit_occluded.png'))
        uncovered=cv2.imread(str(Path(__file__).parent/'fixtures/center_exit_uncovered.png'))
        device=Mock();device.screenshot.return_value=blocked
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            controller=TravelController(device,Path(folder),sleep=lambda _:None)
            self.assertFalse(any(x>1400 and 500<y<720 for x,y in controller.world.arrows(blocked)))
            self.assertTrue(controller.uncover_center_exit())
            device.tap.assert_called_once_with(1300,710)
            self.assertTrue(any(x>1400 and 500<y<720 for x,y in controller.world.arrows(uncovered)))

    def test_no_unverified_walking_when_map_is_unknown(self):
        import numpy as np
        device=Mock();device.screenshot.return_value=np.zeros((900,1600,3),np.uint8)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            controller=TravelController(device,Path(folder))
            self.assertFalse(controller.uncover_center_exit())
        device.tap.assert_not_called()

    def test_exit_revealed_by_last_allowed_pan_is_used(self):
        import numpy as np
        frame=np.zeros((900,1600,3),np.uint8)
        class Device:
            pans=0;taps=[]
            def screenshot(self):return frame
            def swipe(self,*args):self.pans+=1
            def tap(self,*point):self.taps.append(point)
        device=Device();clock=Clock()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            controller=TravelController(device,Path(folder),clock.read,clock.sleep)
            controller.world=Mock();controller.event=Mock();controller.uncover_center_exit=Mock(return_value=False)
            controller.world.map_name.side_effect=lambda a:'ca_noc' if device.taps else 'center'
            controller.world.arrows.side_effect=lambda a:[(1535,603)] if device.pans==3 else []
            controller.enter('ca_noc')
        self.assertEqual(device.pans,3);self.assertEqual(device.taps,[(1535,603)])

    def test_shifted_camera_reveals_verified_exit_before_tap(self):
        device=Mock();device.screenshot.side_effect=['shifted','shifted','edge']
        clock=Clock()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            controller=TravelController(device,Path(folder),clock.read,clock.sleep)
            controller.leave_chair=Mock();controller.event=Mock();controller.tap=Mock()
            controller.world=Mock();controller.world.map_name.return_value='ca_noc'
            controller.world.arrows.side_effect=lambda a: [(12,570)] if a=='edge' else []
            from vision.matcher import MatchResult
            controller.wait=Mock(return_value=MatchResult(11,569,2,2,1.))
            controller.center('ca_noc')
            device.swipe.assert_called_once_with(300,650,850,650,500)
            controller.tap.assert_called_once_with((12,570),'Về trung tâm')

    def test_missing_exit_pans_are_bounded_and_never_tap(self):
        device=Mock();device.screenshot.return_value='shifted';clock=Clock()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            controller=TravelController(device,Path(folder),clock.read,clock.sleep)
            controller.leave_chair=Mock();controller.event=Mock();controller.tap=Mock()
            controller.world=Mock();controller.world.map_name.return_value='ca_noc';controller.world.arrows.return_value=[]
            with self.assertRaisesRegex(RuntimeError,'Không thấy mũi tên'):
                controller.center('ca_noc')
            self.assertEqual(device.swipe.call_count,5);controller.tap.assert_not_called()

    def test_out_of_bait_is_closed_before_return_navigation(self):
        class Device:
            def __init__(self):
                self.closed = False
                self.taps = []
            def screenshot(self):
                name = "puffer_idle" if self.closed else "no_bait_vi"
                return cv2.imread(str(Path(__file__).parent / "fixtures" / f"{name}.png"))
            def tap(self, x, y):
                self.taps.append((x, y))
                self.closed = True
        device, clock = Device(), Clock()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, redirect_stdout(StringIO()):
            controller = TravelController(device, Path(folder), clock.read, clock.sleep)
            controller.leave_chair("ca_noc")
        self.assertEqual(device.taps, [(798, 581)])

    def test_out_of_bait_can_leave_seated_close_only_screen(self):
        class Device:
            def __init__(self):
                self.state = 'no_bait_vi'
                self.taps = []
            def screenshot(self):
                return cv2.imread(str(Path(__file__).parent / 'fixtures' / (self.state + '.png')))
            def tap(self, x, y):
                self.taps.append((x, y))
                self.state = 'no_bait_closed_seated' if len(self.taps) == 1 else 'idle_pond'
        device, clock = Device(), Clock()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, redirect_stdout(StringIO()):
            controller = TravelController(device, Path(folder), clock.read, clock.sleep)
            controller.leave_chair('ca_ro')
        self.assertEqual(len(device.taps), 2)
        self.assertEqual(device.taps[0], (798, 581))
        self.assertGreater(device.taps[1][0], 1300)

    def purchase(self, device):
        clock = Clock()
        def fast_poll(seconds):
            clock.sleep(max(5., seconds))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, redirect_stdout(StringIO()):
            controller = TravelController(device, Path(folder), clock.read, fast_poll)
            try:
                value = controller.sell_and_buy()
            except RuntimeError as exc:
                print(str(exc))
                value = None
            return value, controller.bait_purchased

    def test_buy_twenty_once_after_visual_receipt(self):
        device = ShopDevice()
        self.assertEqual(self.purchase(device), (20, 20))
        self.assertEqual(device.inputs, [20])
        self.assertEqual(device.buy_count, 1)

    def test_missing_receipt_never_buys_twice_or_counts_bait(self):
        device = ShopDevice(fail_purchase=True)
        self.assertEqual(self.purchase(device), (None, 0))
        self.assertEqual(device.buy_count, 1)

    def test_wrong_quantity_cannot_buy(self):
        device = ShopDevice(fail_number=True)
        self.assertEqual(self.purchase(device), (None, 0))
        self.assertEqual(device.buy_count, 0)

    def test_capacity_rejection_does_not_count_or_repeat_purchase(self):
        device = ShopDevice(capacity=True)
        self.assertEqual(self.purchase(device), (0, 0))
        self.assertEqual(device.buy_count, 1)

    def test_shop_menu_returning_to_center_can_reopen_before_purchase(self):
        device = ShopDevice(closed_shop_once=True)
        self.assertEqual(self.purchase(device), (20, 20))
        self.assertEqual(device.buy_count, 1)

    def test_statistics_separate_areas_and_uncertain_results(self):
        rounds = [TrialResult("SUCCESS", "ok", 1, 4, 3, "ca_noc", "Cá nóc", 1., "ca_noc", True),
                  TrialResult("FAILED", "miss", 1, 0, 0, area="ca_noc", bite_observed=True),
                  TrialResult("RESULT", "finish", 1, 0, 0, area="ca_map")]
        stats = fishing_statistics(rounds)
        self.assertEqual((stats["caught"], stats["bites"], stats["misses"]), (1, 2, 1))
        self.assertEqual(stats["areas"]["ca_noc"]["fish_counts"], {"ca_noc": 1})
        self.assertEqual(stats["areas"]["ca_map"]["misses_confirmed"], 0)

