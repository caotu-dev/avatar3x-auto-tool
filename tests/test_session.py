import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import numpy as np

from config.settings import SessionSettings, TrialSettings
from fishing.detector import Detection
from fishing.session import FishingSession, popup_outside_point
from vision.matcher import MatchResult
from tests.test_bot import Clock, FakeDevice, FakeDetector, FakeSolver


class SessionDevice(FakeDevice):
    def screenshot(self):
        code = int(super().screenshot()[0, 0, 0])
        screen = np.zeros((900, 1600, 3), np.uint8)
        screen[0, 0] = code
        screen[630:670, 140:180] = (180, 150, 50)
        return screen


class SessionDetector(FakeDetector):
    def detect(self, screen):
        detection = super().detect(screen)
        return Detection(detection.state,
                         {**detection.matches, "finish": MatchResult(1450, 830, 20, 20, 1.0),
                          "exit_no": MatchResult(900, 530, 20, 20, 1.0),
                          "chair_4": MatchResult(1180, 770, 40, 15, 1.0)}, True)


class SessionTests(unittest.TestCase):
    def test_seated_loading_longer_than_deadline_then_no_resumes(self):
        from fishing.states import FishingState
        class Detector(SessionDetector):
            def detect(self,screen):
                if int(screen[0,0,0])==12:return Detection(FishingState.LOADING,{})
                return super().detect(screen)
        clock=Clock();device=SessionDevice([12]*200+[9,9,1,1],clock)
        with tempfile.TemporaryDirectory(dir='debug') as folder,redirect_stdout(StringIO()):
            session=FishingSession(device,detector=Detector(),output=Path(folder),clock=clock.read,sleep=clock.sleep)
            ready,_=session._prepare_ready()
        self.assertTrue(ready);self.assertGreater(clock.now,30)
        self.assertEqual(device.taps,[(910,540)])
        self.assertEqual(device.swipes,[])

    def test_actual_seated_loading_popup_is_recognized(self):
        import cv2
        from fishing.detector import FishingDetector
        from fishing.states import FishingState
        image=cv2.imread(str(Path(__file__).parent/'fixtures/loading_seated.png'))
        self.assertEqual(FishingDetector(area='ca_noc').detect(image).state,FishingState.LOADING)

    def test_auto_retries_dropped_finish_then_stops_at_ready(self):
        clock=Clock()
        class DroppedFinishDevice(SessionDevice):
            def screenshot(self):
                self.frames=[1 if len(self.taps)>=2 else 6]
                return super().screenshot()
        device=DroppedFinishDevice([6],clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            session=FishingSession(device,detector=SessionDetector(),output=Path(folder),
                clock=clock.read,sleep=clock.sleep,recover_uncertain=True)
            ready,_=session._prepare_ready(after_round=True)
        self.assertTrue(ready)
        self.assertEqual(device.taps,[(1460,840),(1460,840)])
        self.assertEqual(device.swipes,[])

    def test_auto_finish_retry_is_bounded_when_game_ignores_all_taps(self):
        clock=Clock();device=SessionDevice([6]*1000,clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            session=FishingSession(device,detector=SessionDetector(),output=Path(folder),
                clock=clock.read,sleep=clock.sleep,recover_uncertain=True)
            ready,_=session._prepare_ready(after_round=True)
        self.assertFalse(ready)
        self.assertEqual(device.taps,[(1460,840)]*3)

    def test_actual_stalled_shark_result_has_verified_finish(self):
        import cv2
        from fishing.detector import FishingDetector
        from fishing.states import FishingState
        image=cv2.imread(str(Path(__file__).parent/'fixtures/shark_finish_stalled.png'))
        detection=FishingDetector(area='ca_map').detect(image)
        self.assertEqual(detection.state,FishingState.RESULT)
        self.assertTrue(detection.scene_confirmed)
        self.assertEqual(detection.matches['finish'].center,(1465,845))

    def test_auto_uncertain_round_returns_ready_then_completes(self):
        clock=Clock();device=SessionDevice([1,1,1]+[8]*20+[1,1,1,1],clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            session=FishingSession(device,settings=SessionSettings(rounds=1),trial_settings=TrialSettings(round_timeout=1),detector=SessionDetector(),solver=FakeSolver(),
                output=Path(folder),clock=clock.read,sleep=clock.sleep,recover_uncertain=True)
            result=session.run()
        self.assertEqual(result.status,'COMPLETE');self.assertEqual(result.rounds[0].outcome,'ABORTED')
        self.assertEqual(device.taps,[(100,100)])
    def test_slow_capture_after_catch_still_verifies_finish_without_recast(self):
        clock=Clock()
        class SlowDevice(SessionDevice):
            def screenshot(self):
                clock.sleep(1.8)
                return super().screenshot()
        device=SlowDevice([5,5,8,6,6,1,1],clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder,redirect_stdout(StringIO()):
            session=FishingSession(device,detector=SessionDetector(),output=Path(folder),clock=clock.read,sleep=clock.sleep)
            ready,_=session._prepare_ready(after_round=True)
        self.assertTrue(ready)
        self.assertEqual(device.taps,[(160,650),(1460,840)])
        self.assertGreater(clock.now,12)

    def test_walking_to_chair_can_exceed_popup_transition_timeout(self):
        result, device = self.run_session([10] * 30 + [1, 1, 1, 7, 7, 6, 1, 1])
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(device.taps.count((1200, 792)), 1)

    def test_real_images_enter_chair_then_out_of_bait_during_cast(self):
        import cv2
        from config.settings import ROOT
        from fishing.detector import FishingDetector
        idle = cv2.imread(str(ROOT / "tests/fixtures/idle_pond.png"))
        for ready_file, bait_file in (("ready_lower_seat.png", "no_bait_adb.png"),
                                      ("ready_vi.png", "no_bait_vi.png")):
            ready = cv2.imread(str(ROOT / "tests/fixtures" / ready_file))
            bait = cv2.imread(str(ROOT / "tests/fixtures" / bait_file))
            clock = Clock()
    
            class ImageDevice(FakeDevice):
                def screenshot(self):
                    self.clock.now += .2
                    return (self.frames.pop(0) if self.frames else self.last).copy()
    
            device = ImageDevice([idle, idle, ready, ready, ready, bait], clock)
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
                session = FishingSession(device, SessionSettings(rounds=5), detector=FishingDetector(),
                                         solver=FakeSolver(), output=Path(folder),
                                         clock=clock.read, sleep=clock.sleep)
                with redirect_stdout(StringIO()):
                    result = session.run()
                self.assertTrue((Path(folder) / "notification.json").is_file())
            self.assertEqual(result.status, "OUT_OF_BAIT")
            self.assertEqual(device.taps[0], (1200, 799))
            self.assertEqual(len(device.taps), 2)
            self.assertEqual(device.swipes, [])
    def run_session(self, frames, rounds=1, solver=None):
        clock = Clock()
        device = SessionDevice(frames, clock)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            session = FishingSession(device, SessionSettings(rounds, 3, .05),
                                     TrialSettings(round_timeout=8, unknown_timeout=.8, plan_timeout=.3),
                                     SessionDetector(), solver or FakeSolver(), Path(folder), clock.read, clock.sleep)
            with redirect_stdout(StringIO()):
                result = session.run()
            self.assertTrue((Path(folder) / "summary.json").is_file())
            notification = Path(folder) / "notification.json"
            self.assertEqual(notification.is_file(), result.status == "OUT_OF_BAIT")
        return result, device

    def test_success_then_miss_and_stops_at_limit(self):
        frames = [1, 1, 1, 2, 3, 3, 3, 4, 4, 5,
                  5, 5, 6, 6, 1, 1,
                  1, 2, 3, 7,
                  7, 6, 1, 1]
        result, device = self.run_session(frames, 2)
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual([round_.outcome for round_ in result.rounds], ["SUCCESS", "FAILED"])
        self.assertEqual(sum(round_.casts for round_ in result.rounds), 2)
        self.assertEqual(device.taps, [(100, 100), (160, 650), (1460, 840),
                                       (100, 100), (1460, 840)])
        self.assertEqual(len(device.swipes), 1)

    def test_stuck_popup_is_tapped_only_once(self):
        result, device = self.run_session([5, 5])
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(device.taps, [(160, 650)])
        self.assertEqual(result.rounds, ())

    def test_exit_confirmation_over_success_is_cancelled_then_continues(self):
        frames = [1, 1, 1, 5, 9, 9, 5, 5, 6, 6, 1, 1]
        result, device = self.run_session(frames)
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(device.taps, [(100, 100), (910, 540), (160, 650), (1460, 840)])

    def test_stuck_exit_confirmation_is_cancelled_only_once(self):
        result, device = self.run_session([9, 9])
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(device.taps, [(910, 540)])

    def test_exit_flashes_once_without_clicking_no(self):
        result, device = self.run_session([9, 1, 1, 1, 7, 7, 6, 1, 1])
        self.assertEqual(result.status, "COMPLETE")
        self.assertNotIn((910, 540), device.taps)

    def test_unsafe_puzzle_then_finish_continues_next_round(self):
        from fishing.solver import SolvePlan
        class UnsafeSolver(FakeSolver):
            def plan(self, screen):
                return SolvePlan((), False, "Không chắc chắn")
        frames = [1, 1, 1, 3, 3, 3, 6, 6, 6, 1, 1,
                  1, 7, 7, 6, 1, 1]
        result, device = self.run_session(frames, 2, UnsafeSolver())
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual([r.outcome for r in result.rounds], ["RESULT", "FAILED"])
        self.assertEqual(len(device.swipes), 0)
        self.assertEqual(sum(r.casts for r in result.rounds), 2)

    def test_stuck_finish_is_tapped_only_once(self):
        result, device = self.run_session([6, 6])
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(device.taps, [(1460, 840)])

    def test_initial_unknown_has_no_input(self):
        result, device = self.run_session([8])
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(device.taps, [])

    def test_enter_visible_chair_then_cast(self):
        result, device = self.run_session([10, 10, 1, 1, 1, 7, 7, 6, 1, 1])
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(device.taps, [(1200, 792), (100, 100), (1460, 840)])

    def test_chair_entry_is_not_repeated_if_no_response(self):
        result, device = self.run_session([10])
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(device.taps, [(1200, 792)])

    def test_out_of_bait_after_chair_stops_without_ok_or_reentry(self):
        result, device = self.run_session([10, 10, 11])
        self.assertEqual(result.status, "OUT_OF_BAIT")
        self.assertEqual(device.taps, [(1200, 792)])
        self.assertEqual(result.rounds, ())

    def test_out_of_bait_after_finish_never_casts_again(self):
        result, device = self.run_session([1, 1, 1, 7, 7, 6, 11], rounds=5)
        self.assertEqual(result.status, "OUT_OF_BAIT")
        self.assertEqual(device.taps, [(100, 100), (1460, 840)])
        self.assertEqual(len(result.rounds), 1)

    def test_out_of_bait_during_round_stops_session(self):
        result, device = self.run_session([1, 1, 1, 11], rounds=5)
        self.assertEqual(result.status, "OUT_OF_BAIT")
        self.assertEqual(device.taps, [(100, 100)])

    def test_out_of_bait_initial_sends_no_input(self):
        result, device = self.run_session([11])
        self.assertEqual(result.status, "OUT_OF_BAIT")
        self.assertEqual(device.taps, [])

    def test_does_not_interrupt_existing_fishing_round(self):
        result, device = self.run_session([3])
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(device.taps, [])

    def test_cleanup_waits_for_finish_after_transient_fishing(self):
        result, device = self.run_session([1, 1, 1, 7, 7, 3, 6, 6, 1, 1])
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(device.taps, [(100, 100), (1460, 840)])
        self.assertEqual(device.swipes, [])

    def test_cleanup_does_not_click_if_active_puzzle_persists(self):
        result, device = self.run_session([1, 1, 1, 7, 3])
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(device.taps, [(100, 100)])
        self.assertEqual(device.swipes, [])

    def test_round_error_does_not_cleanup_or_recast(self):
        result, device = self.run_session([1, 1, 1, 8])
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(device.taps, [(100, 100)])
        self.assertIn(result.rounds[0].outcome, ("STOPPED", "TIMEOUT"))

    def test_finish_without_miss_remains_unspecified_result(self):
        result, device = self.run_session([1, 1, 1, 6, 6, 6, 1, 1])
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.rounds[0].outcome, "RESULT")
        self.assertEqual(device.taps, [(100, 100), (1460, 840)])

    def test_ctrl_c_during_cleanup_does_not_send_another_tap(self):
        result, device = self.run_session([5, 5, KeyboardInterrupt()])
        self.assertEqual(result.status, "STOPPED")
        self.assertEqual(device.taps, [(160, 650)])

    def test_popup_dismiss_point_is_checked_on_real_success_frame(self):
        import cv2
        from config.settings import ROOT
        path = ROOT / "tests/fixtures/success.png"
        if not path.is_file():
            self.skipTest("Cần ảnh popup thành công thực tế")
        self.assertEqual(popup_outside_point(cv2.imread(str(path))), (160, 650))
        self.assertIsNone(popup_outside_point(np.zeros((900, 1600, 3), np.uint8)))
