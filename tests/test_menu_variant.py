import unittest
from pathlib import Path
import cv2
from config.settings import ROOT
from fishing.detector import FishingDetector
from fishing.states import FishingState


class MenuVariantTests(unittest.TestCase):
    def test_real_crowded_pond_with_menu_text_still_enters_idle(self):
        screen = cv2.imread(str(ROOT / 'tests/fixtures/menu_text_idle.png'))
        result = FishingDetector().detect(screen)
        self.assertTrue(result.scene_confirmed)
        self.assertEqual(result.state, FishingState.IDLE)
        self.assertIn('chair_1', result.matches)
        self.assertIn('idle_menu', result.matches)
