import unittest

import cv2

from config.settings import ROOT
from fishing.detector import FishingDetector
from fishing.states import FishingState


class SceneTests(unittest.TestCase):
    def test_vietnamese_bait_message_has_priority(self):
        detector = FishingDetector()
        screen = cv2.imread(str(ROOT / "tests/fixtures/no_bait_vi.png"))
        self.assertEqual(detector.detect(screen).state, FishingState.OUT_OF_BAIT)
        exit_screen = cv2.imread(str(ROOT / "tests/fixtures/exit_vi.png"))
        self.assertEqual(detector.detect(exit_screen).state, FishingState.EXIT_CONFIRM)

    def test_vietnamese_reward_popup_is_detected_independently_of_body_text(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/success_vi.png"))
        self.assertEqual(FishingDetector().detect(screen).state, FishingState.SUCCESS)
        screen[460:770, 500:1100] = 0
        self.assertEqual(FishingDetector().detect(screen).state, FishingState.SUCCESS)

    def test_vietnamese_other_player_failure_does_not_interrupt_puzzle(self):
        detector = FishingDetector()
        screen = cv2.imread(str(ROOT / "tests/fixtures/other_player_miss.png"))
        failed = cv2.imread(str(ROOT / "tests/fixtures/failed_vi.png"))
        screen[455:493, 1155:1255] = failed[455:493, 1155:1255]
        detection = detector.detect(screen)
        self.assertIn("miss", detection.matches)
        self.assertEqual(detection.state, FishingState.FISHING)

    def test_vietnamese_exit_requires_question_and_cancel_button(self):
        detector = FishingDetector()
        screen = cv2.imread(str(ROOT / "tests/fixtures/exit_vi.png"))
        detection = detector.detect(screen)
        self.assertEqual(detection.state, FishingState.EXIT_CONFIRM)
        self.assertEqual(detection.matches["exit_no"].center, (958, 557))
        screen[536:578, 912:1005] = 0
        self.assertNotEqual(detector.detect(screen).state, FishingState.EXIT_CONFIRM)

    def test_vietnamese_failure_moves_and_disappears(self):
        detector = FishingDetector()
        screen = cv2.imread(str(ROOT / "tests/fixtures/failed_vi.png"))
        glyph = screen[455:493, 1155:1255].copy()
        self.assertEqual(detector.detect(screen).state, FishingState.FAILED)
        screen[455:493, 1155:1255] = 0
        screen[405:443, 1155:1255] = glyph
        self.assertEqual(detector.detect(screen).state, FishingState.FAILED)
        screen[405:443, 1155:1255] = 0
        self.assertEqual(detector.detect(screen).state, FishingState.RESULT)

    def test_vietnamese_close_and_finish_are_distinct(self):
        detector = FishingDetector()
        ready = detector.detect(cv2.imread(str(ROOT / "tests/fixtures/ready_vi.png")))
        result = detector.detect(cv2.imread(str(ROOT / "tests/fixtures/result_vi.png")))
        self.assertEqual(ready.state, FishingState.READY)
        self.assertNotIn("finish", ready.matches)
        self.assertEqual(result.state, FishingState.RESULT)
        self.assertNotIn("close", result.matches)

    def test_idle_pond_has_detected_chair_and_no_fishing_controls(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/idle_pond.png"))
        detection = FishingDetector().detect(screen)
        self.assertEqual(detection.state, FishingState.IDLE)
        self.assertIn("chair_4", detection.matches)
        screen[558:756, 80:400] = 0
        self.assertEqual(FishingDetector().detect(screen).state, FishingState.UNKNOWN)

    def test_out_of_bait_popup_has_priority_and_no_false_positive_on_exit(self):
        detector = FishingDetector()
        screen = cv2.imread(str(ROOT / "tests/fixtures/no_bait.png"))
        self.assertEqual(detector.detect(screen).state, FishingState.OUT_OF_BAIT)
        screen = cv2.imread(str(ROOT / "tests/fixtures/no_bait_adb.png"))
        self.assertEqual(detector.detect(screen).state, FishingState.OUT_OF_BAIT)
        screen = cv2.imread(str(ROOT / "tests/fixtures/exit_confirmation.png"))
        self.assertEqual(detector.detect(screen).state, FishingState.EXIT_CONFIRM)

    def test_exit_confirmation_has_priority_over_fish_popup(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/exit_confirmation.png"))
        detector = FishingDetector()
        detection = detector.detect(screen)
        self.assertEqual(detection.state, FishingState.EXIT_CONFIRM)
        x, y = detection.matches["exit_no"].center
        self.assertTrue(850 < x < 1060 and 515 < y < 595)
        screen[520:584, 872:1040] = 0
        self.assertNotEqual(detector.detect(screen).state, FishingState.EXIT_CONFIRM)

    def test_other_players_miss_does_not_end_active_puzzle(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/other_player_miss.png"))
        detection = FishingDetector().detect(screen)
        self.assertIn("miss", detection.matches)
        self.assertEqual(detection.state, FishingState.FISHING)

    def test_other_players_miss_does_not_end_own_waiting(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/other_player_miss.png"))
        ready = cv2.imread(str(ROOT / "tests/fixtures/crowded_ready.png"))
        screen[540:735, 480:1115] = ready[540:735, 480:1115]
        screen[783:900, 1344:1584] = ready[783:900, 1344:1584]
        detection = FishingDetector().detect(screen)
        self.assertIn("miss", detection.matches)
        self.assertEqual(detection.state, FishingState.WAITING)

    def test_crowded_ready_and_waiting_with_hidden_seats(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/crowded_ready.png"))
        detector = FishingDetector()
        detection = detector.detect(screen)
        self.assertEqual(detection.state, FishingState.READY)
        self.assertFalse(any(n.startswith("chair_") for n in detection.matches))
        screen[783:900, 640:930] = 0
        self.assertEqual(detector.detect(screen).state, FishingState.WAITING)

    def test_crowded_fallback_requires_water_and_red_label(self):
        detector = FishingDetector()
        screen = cv2.imread(str(ROOT / "tests/fixtures/crowded_ready.png"))
        screen[400:750, 1100:1310] = 0
        self.assertEqual(detector.detect(screen).state, FishingState.UNKNOWN)
        screen = cv2.imread(str(ROOT / "tests/fixtures/crowded_ready.png"))
        screen[558:756, 80:400] = 0
        self.assertEqual(detector.detect(screen).state, FishingState.UNKNOWN)

    def test_player_on_lower_seat_does_not_hide_entire_scene(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/ready_lower_seat.png"))
        detection = FishingDetector().detect(screen)
        self.assertEqual(detection.state, FishingState.READY)
        self.assertTrue(detection.scene_confirmed)
        self.assertIn("chair_1", detection.matches)
        self.assertIn("chair_2", detection.matches)

    def test_buttons_without_pond_and_seats_are_unknown(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/ready_lower_seat.png"))
        screen[530:825, 1150:1265] = 0
        detection = FishingDetector().detect(screen)
        self.assertEqual(detection.state, FishingState.UNKNOWN)
        self.assertFalse(detection.scene_confirmed)

    def test_pond_is_required_even_when_seats_match(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/ready_lower_seat.png"))
        screen[558:756, 80:400] = 0
        self.assertEqual(FishingDetector().detect(screen).state, FishingState.UNKNOWN)
