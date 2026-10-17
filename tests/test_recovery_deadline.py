import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from config.settings import TrialSettings
from fishing.bot import OneRoundBot
from fishing.detector import Detection
from fishing.states import FishingState
from tests.test_bot import Clock, FakeDevice, FakeDetector, FakeSolver


class ResultRecoveryDeadlineTests(unittest.TestCase):
    def run_bot(self, frames, detector=None, solver=None):
        clock = Clock()
        device = FakeDevice(frames, clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, redirect_stdout(StringIO()):
            result = OneRoundBot(
                device, TrialSettings(round_timeout=2, recovery_timeout=3),
                detector or FakeDetector(), solver or FakeSolver(), Path(folder),
                clock.read, clock.sleep, recover_uncertain=True).run()
        return result, device, clock.now

    def test_unknown_cannot_leave_auto_session_waiting_forever(self):
        result, device, elapsed = self.run_bot([1] + [8] * 200)
        self.assertEqual(result.outcome, 'TIMEOUT')
        self.assertLess(elapsed, 7)
        self.assertEqual(device.taps, [(100, 100)])
        self.assertEqual(device.swipes, [])

    def test_loading_pauses_result_deadline_and_resumes(self):
        class LoadingDetector(FakeDetector):
            def detect(self, screen):
                if int(screen[0, 0, 0]) == 12:
                    return Detection(FishingState.LOADING, {})
                return super().detect(screen)

        result, device, elapsed = self.run_bot(
            [1] + [8] * 10 + [12] * 200 + [6, 6], LoadingDetector())
        self.assertEqual(result.outcome, 'RESULT')
        self.assertGreater(elapsed, 50)
        self.assertEqual(device.taps, [(100, 100)])

    def test_guard_rejects_pair_changed_during_solving(self):
        class ChangedPairSolver(FakeSolver):
            def validate_match(self, screen, detection, chosen):
                return False

        result, device, _ = self.run_bot([1, 3, 3, 3, 6, 6], solver=ChangedPairSolver())
        self.assertEqual(result.outcome, 'RESULT')
        self.assertEqual(device.swipes, [])

