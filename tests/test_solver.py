import unittest

import cv2
import numpy as np

from config.settings import ROOT
from fishing.solver import FishingSolver

SESSION = ROOT / "tests/fixtures/session_short"


class SolverTests(unittest.TestCase):
    def test_shifted_puffer_camera_recognizes_bite_and_solves(self):
        from fishing.detector import FishingDetector
        from fishing.states import FishingState
        screen=cv2.imread(str(ROOT/'tests/fixtures/ca_noc_shifted_board.png'))
        detector=FishingDetector(area='ca_noc')
        detection=detector.detect(screen)
        self.assertEqual(detection.state,FishingState.FISHING)
        self.assertTrue(detection.scene_confirmed)
        plan=FishingSolver(detector).plan_after_detection(screen,detection)
        self.assertTrue(plan.safe)
        self.assertEqual([m.source_index+1 for m in plan.matches],[5,2,2,5])
        for box in [(520,714,1080,728),(1390,350,1540,840),(540,540,1060,670)]:
            changed=screen.copy();x,y,r,b=box;changed[y:b,x:r]=255
            self.assertNotEqual(detector.detect(changed).state,FishingState.FISHING)

    def test_daytime_dock_board_over_planks_is_detected_and_solved(self):
        from fishing.detector import FishingDetector
        from fishing.states import FishingState
        screen=cv2.imread(str(ROOT/'tests/fixtures/dock/day_puzzle_planks.png'))
        detector=FishingDetector(area='dock')
        detection=detector.detect(screen)
        self.assertEqual(detection.state,FishingState.FISHING)
        plan=FishingSolver(detector).plan_after_detection(screen,detection)
        self.assertTrue(plan.safe)
        self.assertEqual([m.source_index+1 for m in plan.matches],[6,2,2,1,3])
        self.assertEqual([m.target for m in plan.matches],[(546,604),(672,604),(798,604),(924,604),(1050,604)])

    def test_rotated_cup_uses_precise_fallback_without_lowering_margin(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/ambiguous_rotated_cup.png"))
        solver = FishingSolver()
        plan = solver.plan(screen)
        self.assertTrue(plan.safe)
        self.assertEqual([m.source_index + 1 for m in plan.matches], [5, 1, 4, 1, 4])
        self.assertGreaterEqual(plan.matches[3].margin, .10)
        self.assertEqual(solver.plan(screen), plan)

    def test_strict_white_mask_does_not_replace_already_safe_matches(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/saturation_tolerance.png"))
        plan = FishingSolver().plan(screen)
        self.assertTrue(plan.safe)
        self.assertEqual([m.source_index + 1 for m in plan.matches], [5, 1, 6, 5])

    def test_fish_shapes_same_palette_exclude_pastel_noise(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/ambiguous_fish_scratches.png"))
        solver = FishingSolver()
        plan = solver.plan(screen)
        self.assertTrue(plan.safe)
        self.assertEqual([m.source_index + 1 for m in plan.matches], [1, 1, 3, 6])
        self.assertEqual(solver.plan(screen), plan)

    def test_crown_and_fish_same_palette_exclude_pastel_noise(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/ambiguous_crown_scratches.png"))
        solver = FishingSolver()
        plan = solver.plan(screen)
        self.assertTrue(plan.safe)
        self.assertEqual([m.source_index + 1 for m in plan.matches], [2, 1, 5, 4, 5])
        self.assertEqual(solver.plan(screen), plan)

    def test_same_cup_with_different_colors_uses_color_when_glyphs_agree(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/same_cup_different_colors.png"))
        plan = FishingSolver().plan(screen)
        self.assertTrue(plan.safe)
        self.assertEqual([m.source_index + 1 for m in plan.matches], [5, 3, 3, 5, 2])

    def test_similar_plant_and_flower_refines_rotation(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/ambiguous_plant.png"))
        solver = FishingSolver()
        plan = solver.plan(screen)
        self.assertTrue(plan.safe)
        self.assertEqual([m.source_index + 1 for m in plan.matches], [6, 6, 5, 5])
        self.assertEqual(solver.plan(screen), plan)

    def test_fish_and_crown_with_similar_colors_use_distinct_glyphs(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/ambiguous_fish_crown.png"))
        solver = FishingSolver()
        plan = solver.plan(screen)
        self.assertTrue(plan.safe)
        self.assertEqual([m.source_index + 1 for m in plan.matches], [6, 2, 2, 4, 3])
        self.assertEqual(solver.plan(screen), plan)

    def test_refinement_does_not_accept_a_missing_target_glyph(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/ambiguous_fish_crown.png"))
        solver = FishingSolver()
        x, y = solver.plan(screen).matches[2].target
        screen[y - 42:y + 42, x - 42:x + 42] = 0
        self.assertFalse(solver.plan(screen).safe)

    def test_rejected_color_boards_now_match_labeled_sources(self):
        for number, expected in [(5, [2, 5, 2, 1]), (9, [1, 6, 6, 3])]:
            screen = cv2.imread(str(ROOT / f"tests/fixtures/round_{number:03}_initial.png"))
            plan = FishingSolver().plan(screen)
            self.assertTrue(plan.safe)
            self.assertEqual([m.source_index + 1 for m in plan.matches], expected)

    def test_retry_requires_unchanged_unfilled_target_and_source(self):
        solver = FishingSolver()
        before = cv2.imread(str(ROOT / "tests/fixtures/round_002_initial.png"))
        after = cv2.imread(str(ROOT / "tests/fixtures/round_002_wait.png"))
        pending = solver.plan(before).matches[0]
        self.assertTrue(solver.retry_match(before, after, pending))
        x, y = pending.target
        after[y-32:y+32, x-32:x+32] = 255
        self.assertFalse(solver.retry_match(before, after, pending))

    def test_unknown_screen_has_no_plan(self):
        plan = FishingSolver().plan(np.zeros((900, 1600, 3), np.uint8))
        self.assertFalse(plan.safe)
        self.assertEqual(plan.matches, ())

    def test_cached_scores_match_fresh_solver_and_changed_sources(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/two_filled.png"))
        solver = FishingSolver()
        first = solver.plan(screen)
        self.assertEqual(solver.plan(screen), first)
        # Đổi thứ tự nguồn: cache cũ phải được hủy dù các ô đích chưa đổi.
        changed = screen.copy()
        changed[90:174, 1427:1511] = screen[217:301, 1427:1511]
        changed[217:301, 1427:1511] = screen[90:174, 1427:1511]
        self.assertEqual(solver.plan(changed), FishingSolver().plan(changed))

    @unittest.skipUnless(SESSION.is_dir(), "Cần phiên ảnh thực tế")
    def test_hand_labeled_initial_boards(self):
        solver = FishingSolver()
        expected = {80: [5, 4, 3, 2, 2], 153: [4, 4, 2, 4, 1], 244: [4, 5, 5, 6]}
        for frame, sources in expected.items():
            with self.subTest(frame=frame):
                plan = solver.plan(cv2.imread(str(SESSION / f"{frame:06d}.png")))
                self.assertTrue(plan.safe)
                self.assertEqual([match.source_index + 1 for match in plan.matches], sources)
                self.assertTrue(all(not match.completed for match in plan.matches))

    @unittest.skipUnless(SESSION.is_dir(), "Cần phiên ảnh thực tế")
    def test_completed_slots_and_obscured_sources(self):
        solver = FishingSolver()
        screen = cv2.imread(str(SESSION / "000092.png"))
        plan = solver.plan(screen)
        self.assertEqual([match.completed for match in plan.matches],
                         [True, True, True, False, False])
        screen[80:180, 1420:1520] = 0
        self.assertFalse(solver.plan(screen).safe)


if __name__ == "__main__":
    unittest.main()
