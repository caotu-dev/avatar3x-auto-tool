import unittest

import numpy as np
import cv2

from vision.layout import find_target_board
from fishing.solver import FishingSolver
from config.settings import ROOT


class LayoutTests(unittest.TestCase):
    def test_filled_icons_do_not_split_board(self):
        screen = cv2.imread(str(ROOT / "tests/fixtures/two_filled.png"))
        board = find_target_board(screen)
        self.assertIsNotNone(board)
        self.assertEqual(len(board.centers), 5)
        plan = FishingSolver().plan(screen)
        self.assertTrue(plan.safe)
        self.assertEqual([match.completed for match in plan.matches],
                         [True, True, False, False, False])
        self.assertEqual([match.source_index + 1 for match in plan.matches], [2, 5, 5, 2, 6])

    def test_counts_come_from_board_width(self):
        # Kiểm tra hình học, không coi bố cục tổng hợp là bằng chứng game có 1–8 ô.
        for count in range(1, 9):
            with self.subTest(count=count):
                screen = np.full((900, 1600, 3), (200, 180, 80), np.uint8)
                left, right = 798 - count * 63, 798 + count * 63
                screen[544:666, left:right] = (80, 70, 30)
                board = find_target_board(screen)
                self.assertIsNotNone(board)
                self.assertEqual(len(board.centers), count)
                self.assertTrue(all(left < x < right for x, _ in board.centers))

    def test_rejects_shifted_or_irregular_board(self):
        screen = np.full((900, 1600, 3), (200, 180, 80), np.uint8)
        screen[544:666, 450:1080] = (80, 70, 30)
        self.assertIsNone(find_target_board(screen))
        screen[544:666] = (200, 180, 80)
        screen[544:666, 573:1023] = (80, 70, 30)
        self.assertIsNone(find_target_board(screen))
