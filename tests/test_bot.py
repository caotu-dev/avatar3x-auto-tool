import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import numpy as np

from config.settings import TrialSettings
from fishing.bot import OneRoundBot
from fishing.detector import Detection
from fishing.solver import DragMatch, SolvePlan
from fishing.states import FishingState
from vision.matcher import MatchResult


class Clock:
    def __init__(self):
        self.now = 0.0

    def read(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeDevice:
    def __init__(self, frames, clock):
        self.frames = list(frames)
        self.clock = clock
        self.last = frames[-1]
        self.taps = []
        self.swipes = []

    def screenshot(self):
        self.clock.now += .2
        value = self.frames.pop(0) if self.frames else self.last
        if isinstance(value, BaseException):
            raise value
        return np.full((2, 2, 3), value, np.uint8)

    def tap(self, x, y):
        self.taps.append((x, y))

    def swipe(self, *coordinates, duration_ms=250):
        self.swipes.append((coordinates, duration_ms))


class FakeDetector:
    STATES = {1: FishingState.READY, 2: FishingState.WAITING,
              3: FishingState.FISHING, 4: FishingState.FISHING,
              5: FishingState.SUCCESS, 6: FishingState.RESULT,
              7: FishingState.FAILED, 8: FishingState.UNKNOWN,
              9: FishingState.EXIT_CONFIRM}
    STATES.update({10: FishingState.IDLE, 11: FishingState.OUT_OF_BAIT})

    def detect(self, screen):
        return Detection(self.STATES[int(screen[0, 0, 0])],
                         {"toss": MatchResult(90, 90, 20, 20, 1.0),
                          "exit_no": MatchResult(900, 530, 20, 20, 1.0)}, True)


class FakeSolver:
    def completed(self, screen, target):
        return int(screen[0, 0, 0]) == 4

    def plan(self, screen):
        match = DragMatch(0, 0, (1400, 130), (600, 604), .9, .3,
                          self.completed(screen, (600, 604)))
        return SolvePlan((match,), True, "OK")


class BotTests(unittest.TestCase):
    def test_auto_recovers_unknown_to_result_without_another_input(self):
        clock=Clock();device=FakeDevice([1]+[8]*30+[6,6],clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            result=OneRoundBot(device,TrialSettings(round_timeout=2),FakeDetector(),FakeSolver(),Path(folder),clock.read,clock.sleep,recover_uncertain=True).run()
        self.assertEqual(result.outcome,'RESULT')
        self.assertEqual(device.taps,[(100,100)]);self.assertEqual(device.swipes,[])

    def test_auto_recovers_to_ready_without_recasting_inside_failed_round(self):
        clock=Clock();device=FakeDevice([1]+[8]*20+[1,1],clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            result=OneRoundBot(device,TrialSettings(round_timeout=2),FakeDetector(),FakeSolver(),Path(folder),clock.read,clock.sleep,recover_uncertain=True).run()
        self.assertEqual(result.outcome,'ABORTED');self.assertEqual(result.casts,1)
        self.assertEqual(device.taps,[(100,100)])

    def test_auto_recovery_honors_stop(self):
        from ui.runner import Cancelled
        clock=Clock();device=FakeDevice([1]+[8]*20+[Cancelled()],clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            bot=OneRoundBot(device,TrialSettings(round_timeout=2),FakeDetector(),FakeSolver(),Path(folder),clock.read,clock.sleep,recover_uncertain=True)
            with self.assertRaises(Cancelled):bot.run()
        self.assertEqual(device.taps,[(100,100)])

    def test_changed_plan_waits_for_result_in_auto_mode(self):
        class ChangedSolver(FakeSolver):
            def plan(self,screen):
                match=super().plan(screen).matches[0]
                if int(screen[0,0,0])==4:
                    match=DragMatch(1,0,match.source,match.target,.9,.3,True)
                return SolvePlan((match,),True,'OK')
        clock=Clock();device=FakeDevice([1,3,3,3,4,4,6,6],clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            result=OneRoundBot(device,TrialSettings(round_timeout=8),FakeDetector(),ChangedSolver(),Path(folder),clock.read,clock.sleep,recover_uncertain=True).run()
        self.assertEqual(result.outcome,'RESULT');self.assertEqual(len(device.swipes),1)
        self.assertEqual(result.confirmed,1)
    def test_loading_after_bite_then_exit_resumes_without_blind_input(self):
        class Detector(FakeDetector):
            def detect(self,screen):
                if int(screen[0,0,0])==12:return Detection(FishingState.LOADING,{})
                return super().detect(screen)
        clock=Clock();device=FakeDevice([1,3]+[12]*25+[9,9,2,5],clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            result=OneRoundBot(device,TrialSettings(round_timeout=30,bite_timeout=20),Detector(),FakeSolver(),Path(folder),clock.read,clock.sleep).run()
        self.assertEqual(result.outcome,'SUCCESS')
        self.assertEqual(device.taps,[(100,100),(910,540)])
        self.assertEqual(device.swipes,[])

    def test_long_loading_pauses_round_timeout_without_input(self):
        class Detector(FakeDetector):
            def detect(self,screen):
                if int(screen[0,0,0])==12:return Detection(FishingState.LOADING,{})
                return super().detect(screen)
        clock=Clock();device=FakeDevice([1]+[12]*200+[9,9,2,5],clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            result=OneRoundBot(device,TrialSettings(round_timeout=8),Detector(),FakeSolver(),Path(folder),clock.read,clock.sleep).run()
        self.assertEqual(result.outcome,'SUCCESS')
        self.assertGreater(clock.now,30)
        self.assertEqual(device.taps,[(100,100),(910,540)])

    def test_exit_after_brief_bite_recasts_only_on_verified_ready(self):
        clock=Clock();device=FakeDevice([1,3,9,9,1,1,2,5],clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            result=OneRoundBot(device,TrialSettings(round_timeout=30),FakeDetector(),FakeSolver(),Path(folder),clock.read,clock.sleep).run()
        self.assertEqual(result.outcome,'SUCCESS');self.assertEqual(result.casts,2)
        self.assertEqual(device.taps,[(100,100),(910,540),(100,100)])
        self.assertEqual(device.swipes,[])

    def run_trial(self, frames, solver=None):
        clock = Clock()
        device = FakeDevice(frames, clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            bot = OneRoundBot(device, TrialSettings(round_timeout=8, bite_timeout=2,
                               unknown_timeout=.8, confirmation_timeout=.8,
                               plan_timeout=.3, recovery_timeout=2),
                              FakeDetector(), solver or FakeSolver(), Path(folder), clock.read, clock.sleep)
            with redirect_stdout(StringIO()):
                result = bot.run()
            self.assertTrue((Path(folder) / "result.json").is_file())
        return result, device

    def test_success_casts_once_and_confirms_drag(self):
        result, device = self.run_trial([1, 2, 3, 3, 3, 4, 4, 5])
        self.assertEqual(result.outcome, "SUCCESS")
        self.assertEqual((result.casts, result.drags, result.confirmed), (1, 1, 1))
        self.assertEqual(len(device.taps), 1)
        self.assertEqual(len(device.swipes), 1)

    def test_flash_then_miss_never_drags(self):
        result, device = self.run_trial([1, 2, 3, 7])
        self.assertEqual(result.outcome, "FAILED")
        self.assertEqual(device.swipes, [])

    def test_next_drag_uses_second_confirmation_frame(self):
        class TwoSlotSolver(FakeSolver):
            def completed(self, screen, target):
                return target == (600, 604) and super().completed(screen, target)

            def plan(self, screen):
                first = super().plan(screen).matches[0]
                second = DragMatch(1, 1, (1400, 257), (726, 604), .9, .3, False)
                return SolvePlan((first, second), True, "OK")

        result, device = self.run_trial([1, 3, 3, 3, 4, 4, 5], TwoSlotSolver())
        self.assertEqual(result.outcome, "SUCCESS")
        self.assertEqual(len(device.swipes), 2)
        self.assertEqual(result.confirmed, 1)

    def test_fresh_guard_miss_cancels_drag(self):
        result, device = self.run_trial([1, 3, 3, 7])
        self.assertEqual(result.outcome, "FAILED")
        self.assertEqual(device.swipes, [])

    def test_unconfirmed_drag_is_not_repeated(self):
        result, device = self.run_trial([1, 3, 3, 3, 3])
        self.assertEqual(result.outcome, "STOPPED")
        self.assertEqual(len(device.swipes), 1)
        self.assertEqual(result.confirmed, 0)

    def test_unsafe_plan_waits_for_finish_without_dragging(self):
        class UnsafeSolver(FakeSolver):
            def plan(self, screen):
                return SolvePlan((), False, "Không chắc chắn")
        result, device = self.run_trial([1, 3, 3, 3, 8, 6], UnsafeSolver())
        self.assertEqual(result.outcome, "RESULT")
        self.assertEqual(device.swipes, [])
        self.assertEqual(len(device.taps), 1)

    def test_unconfirmed_drag_waits_for_miss_without_repeating(self):
        result, device = self.run_trial([1, 3, 3, 3, 3, 3, 3, 7])
        self.assertEqual(result.outcome, "FAILED")
        self.assertEqual(len(device.swipes), 1)

    def test_unsafe_plan_recovery_has_deadline(self):
        class UnsafeSolver(FakeSolver):
            def plan(self, screen):
                return SolvePlan((), False, "Không chắc chắn")
        result, device = self.run_trial([1, 3], UnsafeSolver())
        self.assertEqual(result.outcome, "STOPPED")
        self.assertEqual(device.swipes, [])

    def test_unchanged_slot_can_retry_once_then_confirm(self):
        class RetrySolver(FakeSolver):
            def retry_match(self, before, screen, pending):
                return int(screen[0, 0, 0]) == 3
        result, device = self.run_trial([1, 3, 3, 3, 3, 3, 3, 3, 4, 4, 5], RetrySolver())
        self.assertEqual(result.outcome, "SUCCESS")
        self.assertEqual(len(device.swipes), 2)
        self.assertEqual(device.swipes[-1][1], 900)

    def test_retry_never_repeats_more_than_once(self):
        class RetrySolver(FakeSolver):
            def retry_match(self, before, screen, pending):
                return True
        result, device = self.run_trial([1, 3], RetrySolver())
        self.assertEqual(result.outcome, "STOPPED")
        self.assertEqual(len(device.swipes), 2)

    def test_miss_on_retry_guard_cancels_retry(self):
        class RetrySolver(FakeSolver):
            def retry_match(self, before, screen, pending):
                return True
        result, device = self.run_trial([1, 3, 3, 3, 3, 3, 3, 7], RetrySolver())
        self.assertEqual(result.outcome, "FAILED")
        self.assertEqual(len(device.swipes), 1)

    def test_unknown_after_cast_never_clicks_again(self):
        result, device = self.run_trial([1, 8])
        self.assertEqual(result.outcome, "STOPPED")
        self.assertEqual(len(device.taps), 1)
        self.assertEqual(device.swipes, [])

    def test_finish_has_no_automatic_failure_label(self):
        result, device = self.run_trial([1, 2, 6])
        self.assertEqual(result.outcome, "RESULT")
        self.assertEqual(device.swipes, [])

    def test_starting_at_finish_sends_no_input(self):
        result, device = self.run_trial([6])
        self.assertEqual(result.casts, 0)
        self.assertEqual(device.taps, [])

    def test_wait_timeout_does_not_recast(self):
        result, device = self.run_trial([1, 2])
        self.assertEqual(result.outcome, "TIMEOUT")
        self.assertEqual(len(device.taps), 1)

    def test_connection_error_stops_and_reports(self):
        result, device = self.run_trial([1, RuntimeError("offline")])
        self.assertEqual(result.outcome, "ERROR")
        self.assertEqual(device.swipes, [])

    def test_keyboard_interrupt_stops(self):
        result, device = self.run_trial([1, KeyboardInterrupt()])
        self.assertEqual(result.outcome, "STOPPED")
        self.assertEqual(device.swipes, [])

    def test_no_bait_before_start_sends_no_input(self):
        result, device = self.run_trial([11])
        self.assertEqual(result.outcome, "OUT_OF_BAIT")
        self.assertEqual(device.taps, [])

    def test_no_bait_after_cast_stops_without_another_action(self):
        result, device = self.run_trial([1, 11])
        self.assertEqual(result.outcome, "OUT_OF_BAIT")
        self.assertEqual(len(device.taps), 1)
        self.assertEqual(device.swipes, [])

    def test_exit_over_result_is_cancelled_then_success(self):
        result, device = self.run_trial([1, 2, 9, 9, 5])
        self.assertEqual(result.outcome, "SUCCESS")
        self.assertEqual(device.taps, [(100, 100), (910, 540)])
        self.assertEqual(device.swipes, [])

    def test_stuck_exit_during_round_is_tapped_only_once(self):
        result, device = self.run_trial([1, 9])
        self.assertEqual(result.outcome, "STOPPED")
        self.assertEqual(device.taps, [(100, 100), (910, 540)])

    def test_exit_after_cast_recasts_once_on_stable_ready(self):
        result, device = self.run_trial([1, 8, 8, 9, 9, 1, 1, 2, 5])
        self.assertEqual(result.outcome, 'SUCCESS')
        self.assertEqual(result.casts, 2)
        self.assertEqual(device.taps, [(100, 100), (910, 540), (100, 100)])

    def test_ready_after_recast_does_not_cast_repeatedly(self):
        result, device = self.run_trial([1, 9, 9, 1, 1, 1])
        self.assertEqual(device.taps, [(100, 100), (910, 540), (100, 100)])
        self.assertEqual(result.outcome, 'STOPPED')

