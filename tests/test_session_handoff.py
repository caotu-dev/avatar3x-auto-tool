import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from fishing.session import FishingSession
from tests.test_bot import Clock, FakeDevice, FakeDetector, FakeSolver
from ui.runner import BotWorker


class SessionHandoffTests(unittest.TestCase):
    def readiness(self, age, after_round=False):
        clock = Clock()
        device = FakeDevice([1, 1], clock)
        device.screenshot = Mock(wraps=device.screenshot)
        frame = np.full((2, 2, 3), 1, np.uint8)
        detector = FakeDetector()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            session = FishingSession(device, detector=detector, solver=FakeSolver(),
                clock=clock.read, sleep=clock.sleep, output=Path(folder), reuse_ready=True,
                ready_handoff=(frame, detector.detect(frame), -age))
            ready, _ = session._prepare_ready(after_round=after_round)
        self.assertTrue(ready)
        self.assertIsNone(session.ready_handoff)
        return device.screenshot.call_count

    def test_immediate_completed_round_reuses_verified_readiness_once(self):
        self.assertEqual(self.readiness(0), 0)

    def test_old_or_post_action_readiness_captures_two_new_frames(self):
        self.assertEqual(self.readiness(.26), 2)
        self.assertEqual(self.readiness(0, after_round=True), 2)

    def test_navigation_handoff_is_area_bound_one_use_and_expires(self):
        worker = BotWorker.__new__(BotWorker)
        info = ('frame', 'detection', 10)
        with patch('ui.runner.time.monotonic', return_value=10.1):
            worker.ready_for_next = ('dock', info)
            self.assertIsNone(worker.take_ready_handoff('ca_ro'))
            worker.ready_for_next = ('dock', info)
            self.assertEqual(worker.take_ready_handoff('dock'), info)
            self.assertIsNone(worker.take_ready_handoff('dock'))
        with patch('ui.runner.time.monotonic', return_value=10.3):
            worker.ready_for_next = ('dock', info)
            self.assertIsNone(worker.take_ready_handoff('dock'))
