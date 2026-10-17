import unittest

import cv2
import numpy as np

from config.settings import ROOT
from fishing.detector import FishingDetector
from fishing.states import FishingState
from vision.matcher import ROI, find_template

SESSION = ROOT / "tests/fixtures/session_short"


class VisionTests(unittest.TestCase):
    def test_match_returns_screen_coordinates(self):
        rng = np.random.default_rng(123)
        screen = rng.integers(0, 256, (100, 200, 3), dtype=np.uint8)
        template = screen[60:70, 120:140].copy()
        match = find_template(screen, template, .99, ROI(.5, .5, .5, .5))
        self.assertIsNotNone(match)
        self.assertEqual(match.center, (130, 65))

    def test_unrelated_and_unsupported_screens_are_unknown(self):
        detector = FishingDetector()
        for shape in ((900, 1600, 3), (450, 800, 3)):
            self.assertEqual(detector.detect(np.zeros(shape, np.uint8)).state,
                             FishingState.UNKNOWN)

    @unittest.skipUnless(SESSION.is_dir(), "Cần phiên ảnh thực tế trên máy để kiểm tra hồi quy")
    def test_recorded_frames_outside_template_sources(self):
        detector = FishingDetector()
        expected = {5: FishingState.RESULT, 12: FishingState.READY,
                    20: FishingState.WAITING, 90: FishingState.FISHING,
                    160: FishingState.FISHING, 180: FishingState.SUCCESS,
                    245: FishingState.FISHING}
        for frame, state in expected.items():
            with self.subTest(frame=frame):
                screen = cv2.imread(str(SESSION / f"{frame:06d}.png"))
                self.assertEqual(detector.detect(screen).state, state)


if __name__ == "__main__":
    unittest.main()
