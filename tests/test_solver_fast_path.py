import unittest
from unittest.mock import patch

import cv2

from config.settings import ROOT
from fishing.detector import FishingDetector
from fishing.solver import FishingSolver


class SolverFastPathTests(unittest.TestCase):
    def test_only_puzzle_patches_are_converted_and_scene_changes_do_not_break_cache(self):
        screen = cv2.imread(str(ROOT / 'tests/fixtures/round_002_initial.png'))
        detector = FishingDetector()
        detection = detector.detect(screen)
        solver = FishingSolver(detector)
        with patch('fishing.solver.cv2.cvtColor', wraps=cv2.cvtColor) as convert:
            first = solver.plan_after_detection(screen, detection)
        self.assertTrue(first.safe)
        self.assertTrue(all(call.args[0].shape[0] * call.args[0].shape[1] <= 20000
                            for call in convert.call_args_list))
        variants = solver._variants
        changed = screen.copy()
        changed[:80, :1000] = 0
        self.assertEqual(solver.plan_after_detection(changed, detection), first)
        self.assertIs(solver._variants, variants)

    def test_fresh_guard_revalidates_source_identity(self):
        screen = cv2.imread(str(ROOT / 'tests/fixtures/round_002_initial.png'))
        detector = FishingDetector()
        detection = detector.detect(screen)
        solver = FishingSolver(detector)
        chosen = solver.plan_after_detection(screen, detection).matches[0]
        self.assertTrue(solver.validate_match(screen, detection, chosen))
        changed = screen.copy()
        source = chosen.source_index
        other = (source + 1) % 6
        y1, y2 = 132 + 127 * source, 132 + 127 * other
        changed[y1 - 42:y1 + 42, 1427:1511] = screen[y2 - 42:y2 + 42, 1427:1511]
        changed[y2 - 42:y2 + 42, 1427:1511] = screen[y1 - 42:y1 + 42, 1427:1511]
        self.assertFalse(solver.validate_match(changed, detection, chosen))

