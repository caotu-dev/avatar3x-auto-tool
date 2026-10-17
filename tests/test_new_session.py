import unittest

import cv2

from config.settings import ROOT
from fishing.detector import FishingDetector
from fishing.solver import FishingSolver
from fishing.states import FishingState

SESSION = ROOT / "tests/fixtures/session_long"


@unittest.skipUnless(SESSION.is_dir(), "Cần phiên ghi 5 phút")
class NewSessionTests(unittest.TestCase):
    def test_random_boards_with_rotation_and_repeated_symbols(self):
        expected = {
            53: [3, 5, 1, 4], 126: [6, 5, 4, 6, 6],
            201: [3, 2, 5, 4, 4], 281: [4, 4, 6, 3, 4],
            362: [3, 4, 3, 4], 413: [4, 6, 5, 4, 4],
            492: [5, 1, 4, 3, 1], 571: [2, 3, 5, 3],
        }
        solver = FishingSolver()
        for frame, sources in expected.items():
            with self.subTest(frame=frame):
                plan = solver.plan(cv2.imread(str(SESSION / f"{frame:06d}.png")))
                self.assertTrue(plan.safe)
                self.assertEqual([m.source_index + 1 for m in plan.matches], sources)

    def test_miss_moves_then_disappears(self):
        detector = FishingDetector()
        expected = {10: FishingState.WAITING, 362: FishingState.FISHING,
                    363: FishingState.FAILED, 364: FishingState.FAILED,
                    365: FishingState.FAILED, 366: FishingState.RESULT,
                    78: FishingState.SUCCESS, 521: FishingState.READY}
        for frame, state in expected.items():
            with self.subTest(frame=frame):
                detection = detector.detect(cv2.imread(str(SESSION / f"{frame:06d}.png")))
                self.assertEqual(detection.state, state)

    def test_area_number_and_upper_scenery_are_not_detection_inputs(self):
        detector = FishingDetector()
        screen = cv2.imread(str(SESSION / "000053.png"))
        screen[:500] = (20, 20, 220)
        # Thay cả biển Area; giữ ao, các ghế nhìn thấy và giao diện câu.
        screen[700:815, 1280:1390] = (255, 255, 255)
        detection = detector.detect(screen)
        self.assertEqual(detection.state, FishingState.FISHING)
        self.assertTrue(detection.scene_confirmed)
