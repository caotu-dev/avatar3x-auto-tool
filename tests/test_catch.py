import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import cv2
import numpy as np

from fishing.catch import CatchDetector
from fishing.bot import OneRoundBot, TrialResult
from fishing.session import FishingSession


class CatchTests(unittest.TestCase):
    def setUp(self):
        self.detector = CatchDetector()
        self.fixtures = Path(__file__).parent / "fixtures/fish"

    def test_three_real_species(self):
        for species in ("ca_ro", "ca_chep_vang", "ca_long_tong"):
            with self.subTest(species=species):
                result = self.detector.detect(cv2.imread(str(self.fixtures / f"{species}.png")))
                self.assertEqual(result.species, species)
                self.assertGreaterEqual(result.confidence, .95)

    def test_unrelated_screen_and_missing_name_are_unknown(self):
        self.assertIsNone(self.detector.detect(np.zeros((900, 1600, 3), np.uint8)).species)
        self.assertIsNone(self.detector.detect(np.zeros((2, 2, 3), np.uint8)).species)
        screen = cv2.imread(str(self.fixtures / "ca_ro.png"))
        screen[710:780, 830:1150] = 255
        self.assertIsNone(self.detector.detect(screen).species)

    def test_reward_saved_once_and_failed_not_counted(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, redirect_stdout(StringIO()):
            bot = OneRoundBot(None, output=Path(folder) / "round")
            bot.last_screen = cv2.imread(str(self.fixtures / "ca_ro.png"))
            result = bot._finish("SUCCESS", "test")
            self.assertEqual(result.fish_species, "ca_ro")
            self.assertEqual(json.loads((bot.output / "result.json").read_text(encoding="utf-8"))["fish_name"], "Cá rô")
            session = FishingSession(None, output=Path(folder) / "session")
            session.results = [result, TrialResult("FAILED", "test", 1, 0, 0),
                               TrialResult("SUCCESS", "test", 1, 0, 0)]
            session._summary("COMPLETE", "test")
            summary = json.loads((session.output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["fish_counts"], {"ca_ro": 1, "unknown": 1})
