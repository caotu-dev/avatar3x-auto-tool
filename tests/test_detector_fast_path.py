import unittest
from pathlib import Path
from unittest.mock import patch

import cv2

from fishing.detector import FishingDetector
from fishing.dock import DockDetector
from fishing.states import FishingState
from vision.layout import find_target_board
from vision.matcher import find_template


FIXTURES = Path(__file__).parent / 'fixtures'


class DetectorFastPathTests(unittest.TestCase):
    def image(self, filename):
        return cv2.imread(str(FIXTURES / filename))

    def test_shared_gray_keeps_dock_matches_unchanged(self):
        optimized = DockDetector()
        reference = DockDetector()
        original_match = reference.match
        # Compare the shared-frame path against independent conversions for
        # every label, including the night/day fallback and moving boats.
        reference.match = lambda screen, name, roi=None, **kwargs: original_match(screen, name, roi)
        for filename in ('day_ready', 'day_fishing', 'day_empty', 'idle',
                         'level_locked', 'no_bait_at_seat', 'rooms', 'bait_item'):
            with self.subTest(filename=filename):
                image = self.image(f'dock/{filename}.png')
                self.assertEqual(optimized.detect(image), reference.detect(image))

    def test_dock_detection_converts_full_frame_gray_once(self):
        image = self.image('dock/day_ready.png')
        with patch('fishing.dock.cv2.cvtColor', wraps=cv2.cvtColor) as convert:
            self.assertTrue(DockDetector().detect(image).confirmed)
        gray_calls = [call for call in convert.call_args_list
                      if call.args[0] is image and call.args[1] == cv2.COLOR_BGR2GRAY]
        self.assertEqual(len(gray_calls), 1)

    def test_combined_fishing_detector_reuses_its_gray_for_dock(self):
        image = self.image('dock/day_ready.png')
        detector = FishingDetector(area='dock')
        with patch('fishing.detector.cv2.cvtColor', wraps=cv2.cvtColor) as convert:
            self.assertEqual(detector.detect(image).state, FishingState.READY)
        gray_calls = [call for call in convert.call_args_list
                      if call.args[0] is image and call.args[1] == cv2.COLOR_BGR2GRAY]
        self.assertEqual(len(gray_calls), 1)

    def test_dock_skips_discarded_ecology_chairs_but_keeps_boats(self):
        detector = FishingDetector(area='dock')
        chairs = {id(template) for template in detector.chair_templates}
        with patch('fishing.detector.find_template', wraps=find_template) as match:
            observation = detector.detect(self.image('dock/idle.png'))
        self.assertEqual(observation.state, FishingState.IDLE)
        self.assertGreaterEqual(sum(key.startswith('chair_') for key in observation.matches), 2)
        self.assertFalse(any(id(call.args[1]) in chairs for call in match.call_args_list))

    def test_board_measurement_is_shared_only_within_current_frame(self):
        detector = FishingDetector(area='ca_ro')
        image = self.image('round_005_initial.png')
        with patch('fishing.detector.find_target_board', wraps=find_target_board) as board:
            self.assertEqual(detector.detect(image).state, FishingState.FISHING)
            self.assertEqual(board.call_count, 1)
            self.assertEqual(detector.detect(self.image('ready_vi.png')).state, FishingState.READY)
        self.assertEqual(board.call_count, 2)

    def test_same_dock_detector_does_not_retain_previous_frame_pixels(self):
        detector = DockDetector()
        self.assertTrue(detector.detect(self.image('dock/idle.png')).confirmed)
        observation = detector.detect(self.image('dock/level_locked.png'))
        self.assertTrue(observation.level_locked)
        self.assertFalse(observation.boats)


if __name__ == '__main__':
    unittest.main()
