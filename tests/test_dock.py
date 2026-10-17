import tempfile
import unittest
from pathlib import Path

import cv2

from config.settings import ROOT
from fishing.dock import DockController, DockDetector


class DockTests(unittest.TestCase):
    def image(self, name):
        return cv2.imread(str(ROOT / 'tests/fixtures/dock' / f'{name}.png'))

    def test_real_missing_tram_bait_dialog_is_not_a_seat_failure(self):
        from unittest.mock import Mock
        from fishing.detector import FishingDetector
        from fishing.states import FishingState
        image=self.image('no_bait_at_seat')
        self.assertEqual(FishingDetector(area='dock').detect(image).state,FishingState.OUT_OF_BAIT)
        with tempfile.TemporaryDirectory(dir=ROOT/'debug') as folder:
            device=Mock();device.screenshot.return_value=image
            controller=DockController(device,output=Path(folder),state_path=Path(folder)/'dock.json')
            self.assertEqual(controller.check()['status'],'OUT_OF_BAIT')
            device.tap.assert_not_called()

    def test_real_controls_and_empty_boats(self):
        detector = DockDetector()
        idle = detector.detect(self.image('idle'))
        self.assertTrue(idle.confirmed)
        self.assertGreaterEqual(len(idle.boats), 2)
        self.assertTrue(all(300 < boat.y < 540 for boat in idle.boats))
        self.assertIsNotNone(idle.room_sign)
        self.assertTrue(detector.detect(self.image('level_locked')).level_locked)
        self.assertTrue(detector.detect(self.image('rooms')).room_menu)
        self.assertTrue(detector.detect(self.image('bait_item')).bait_selected)

    def test_ecological_map_is_not_dock(self):
        image = cv2.imread(str(ROOT / 'tests/fixtures/navigation/fishing.png'))
        observation = DockDetector().detect(image)
        self.assertFalse(observation.confirmed)
        self.assertFalse(observation.level_locked)

    def test_daytime_fishing_controls_and_boats(self):
        from fishing.detector import FishingDetector
        from fishing.states import FishingState
        from fishing.session import popup_outside_point
        detector=FishingDetector(area='dock')
        ready=detector.detect(self.image('day_ready'))
        self.assertEqual(ready.state,FishingState.READY)
        fishing=detector.detect(self.image('day_fishing'))
        self.assertEqual(fishing.state,FishingState.FISHING)
        self.assertTrue(fishing.scene_confirmed)
        self.assertEqual(popup_outside_point(self.image('day_ready')),(160,180))
        self.assertGreaterEqual(len(DockDetector().detect(self.image('day_empty')).boats),2)

    def test_observed_dock_fish_are_distinct_from_ecological_fish(self):
        from fishing.catch import CatchDetector
        for species in ('ca_chep','ca_vang','ca_he','ca_lia_thia'):
            image=self.image('fish_'+species)
            self.assertEqual(CatchDetector(area='dock').detect(image).species,species)
            self.assertIsNone(CatchDetector(area='ca_ro').detect(image).species)

    def test_dock_quest_names_route_to_dock(self):
        from fishing.quest import parse_quest
        quest=parse_quest(['Nhiệm vụ - 1','3 con Cá chép - 0/3','2 con Cá lia thia - 0/2','Phần thưởng'])
        self.assertEqual([t['species'] for t in quest['targets']],['ca_chep','ca_lia_thia'])
        self.assertTrue(all(t['area']=='dock' for t in quest['targets']))

    def test_level_gate_saves_separate_stock_and_sends_no_input(self):
        image = self.image('level_locked')
        class Device:
            def screenshot(self):
                return image
            def tap(self, *point):
                raise AssertionError('Không bấm khi chưa đủ cấp')
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder:
            controller = DockController(Device(), Path(folder) / 'log', Path(folder) / 'state.json')
            state = controller.check()
            self.assertEqual(state['status'], 'LEVEL_REQUIRED')
            self.assertIsNone(state['bait']['remaining'])
            self.assertEqual(state['bait']['purchased'], 0)
            self.assertEqual(state['fish_counts'], {})


if __name__ == '__main__':
    unittest.main()
