import unittest
from pathlib import Path
import cv2
import tempfile
from config.settings import ROOT
from fishing.rooms import RoomSwitcher
from fishing.travel import TravelController
from vision.matcher import MatchResult


class RoomTests(unittest.TestCase):
    def test_actual_room_grid_and_normal_maps(self):
        switcher = RoomSwitcher(None)
        self.assertTrue(switcher.is_open(cv2.imread(str(ROOT / 'tests/fixtures/rooms_ecological.png'))))
        for name in ('idle', 'level_locked', 'bait_item'):
            self.assertFalse(switcher.is_open(cv2.imread(str(ROOT / f'tests/fixtures/dock/{name}.png'))))

    def test_attempt_limit_prevents_endless_room_loop(self):
        switcher = RoomSwitcher(None)
        switcher.tried = {5, 7, 10}
        with self.assertRaisesRegex(RuntimeError, '3 khu'):
            switcher.choose('ca_ro')

    def test_bobbing_marker_is_stable_but_far_movement_is_not(self):
        class Device:
            def screenshot(self):
                return None
        samples = iter([MatchResult(10, 10, 20, 20, 1), MatchResult(80, 80, 20, 20, 1),
                        MatchResult(80, 85, 20, 20, 1)])
        with tempfile.TemporaryDirectory(dir=ROOT/'debug') as folder:
            travel = TravelController(Device(), Path(folder), sleep=lambda _: None)
            found = travel.wait(lambda _: next(samples), 'icon', timeout=2)
            self.assertEqual(found.y, 85)
