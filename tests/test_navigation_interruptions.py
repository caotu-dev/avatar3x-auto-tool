import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import cv2

from fishing.detector import FishingDetector
from fishing.states import FishingState
from fishing.travel import TravelController
from fishing.world import WorldDetector
from tests.test_bot import Clock

FIXTURES=Path(__file__).parent/'fixtures'


def player_menu():
    image=cv2.imread(str(FIXTURES/'center_right.png'))
    reference=cv2.imread(str(FIXTURES/'player_menu_exit.png'))
    # Reconstruct only the observed context glyphs over a real unobscured map.
    for x,y,r,b in ((1224,246,1278,294),(1412,245,1462,294)):
        image[y:b,x:r]=reference[y:b,x:r]
    return image


class MenuDevice:
    def __init__(self,clock,loading=0,stuck=False,dropped=False):
        self.clock=clock;self.loading=loading;self.state='exit'
        self.taps=[];self.stuck=stuck;self.dropped=dropped
        self.exit=cv2.imread(str(FIXTURES/'player_menu_exit.png'))
        self.player=player_menu()
        self.center=cv2.imread(str(FIXTURES/'center_right.png'))
        self.load=cv2.imread(str(FIXTURES/'loading_seated.png'))

    def screenshot(self):
        self.clock.sleep(.25)
        if self.loading:
            self.loading-=1
            return self.load.copy()
        return {'exit':self.exit,'player':self.player,'center':self.center}[self.state].copy()

    def tap(self,x,y):
        self.taps.append((x,y))
        if self.stuck:return
        if self.state=='exit':
            if abs(x-958)>5 or abs(y-557)>5:raise AssertionError('Must cancel game exit')
            if not self.dropped or len(self.taps)>1:self.state='player'
        elif self.state=='player':
            if x>=500:raise AssertionError('Must dismiss on verified empty map')
            self.state='center'


class NavigationInterruptionTests(unittest.TestCase):
    def test_real_error_requires_both_exit_question_and_no(self):
        image=cv2.imread(str(FIXTURES/'player_menu_exit.png'))
        detector=FishingDetector()
        self.assertEqual(detector.interruption(image).state,FishingState.EXIT_CONFIRM)
        image[515:596,855:1056]=0
        self.assertIsNone(detector.interruption(image))

    def test_context_menu_requires_two_distinct_glyphs_and_clear_ground(self):
        world=WorldDetector();image=player_menu()
        self.assertTrue(world.player_menu(image))
        self.assertIsNotNone(world.player_menu_dismiss_point(image))
        image[245:294,1412:1462]=0
        self.assertFalse(world.player_menu(image))
        self.assertIsNone(world.player_menu_dismiss_point(image))

    def test_loading_exit_and_player_menu_clear_before_trusting_center(self):
        clock=Clock();device=MenuDevice(clock,loading=40)
        with tempfile.TemporaryDirectory(dir=FIXTURES.parent) as folder,redirect_stdout(StringIO()):
            travel=TravelController(device,Path(folder),clock.read,clock.sleep)
            travel.wait(lambda image:travel.world.map_name(image)=='center','center',timeout=3)
        self.assertGreater(clock.now,10)
        self.assertEqual(len(device.taps),2)
        self.assertEqual(device.state,'center')

    def test_dropped_no_is_retried_but_stuck_popup_is_bounded(self):
        for stuck in (False,True):
            clock=Clock();device=MenuDevice(clock,dropped=True,stuck=stuck)
            with self.subTest(stuck=stuck),tempfile.TemporaryDirectory(dir=FIXTURES.parent) as folder,redirect_stdout(StringIO()):
                travel=TravelController(device,Path(folder),clock.read,clock.sleep)
                if stuck:
                    with self.assertRaises(RuntimeError):travel.wait(lambda _:True,'center',timeout=10)
                    self.assertEqual(device.taps,[(958,557)]*3)
                else:
                    travel.wait(lambda image:travel.world.map_name(image)=='center','center',timeout=10)
                    self.assertEqual(device.taps[:2],[(958,557)]*2)

    def test_explicit_exit_confirmation_wait_does_not_cancel_it(self):
        clock=Clock();device=MenuDevice(clock)
        device.tap=lambda x,y:device.taps.append((x,y))
        with tempfile.TemporaryDirectory(dir=FIXTURES.parent) as folder,redirect_stdout(StringIO()):
            travel=TravelController(device,Path(folder),clock.read,clock.sleep)
            travel.button('exit_yes','intentional recovery exit')
        self.assertEqual(device.taps[0],(639,555))

    def test_center_does_not_leave_old_fishing_area_when_already_in_center(self):
        clock=Clock();device=MenuDevice(clock)
        with tempfile.TemporaryDirectory(dir=FIXTURES.parent) as folder,redirect_stdout(StringIO()):
            travel=TravelController(device,Path(folder),clock.read,clock.sleep)
            travel.center('ca_ro')
        self.assertEqual(device.state,'center')
        self.assertEqual(len(device.taps),2)

    def test_verified_current_area_overrides_old_cached_area(self):
        with tempfile.TemporaryDirectory(dir=FIXTURES.parent) as folder:
            travel=TravelController(Mock(),Path(folder))
            travel.wait=Mock()
            travel.world=Mock()
            travel.world.map_name.return_value='ca_noc'
            travel.leave_chair=Mock(side_effect=RuntimeError('stop at verified area'))
            with self.assertRaisesRegex(RuntimeError,'stop at verified area'):
                travel.center('ca_ro')
            travel.leave_chair.assert_called_once_with('ca_noc')
