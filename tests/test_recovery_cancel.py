import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from fishing.detector import Detection
from fishing.states import FishingState
from ui.runner import BotWorker, Options
from vision.matcher import MatchResult


class RecoveryCancellationTests(unittest.TestCase):
    def recover(self, response):
        worker=BotWorker.__new__(BotWorker)
        worker.options=Options(free=True,area='ca_ro',auto_resume=True,resume_limit=1)
        worker.data={'area':'ca_ro','purchase_pending':False,'auto_restarts':0,'scan_complete':True}
        worker.device=Mock();worker.device.is_connected.return_value=True
        worker.device.screenshot.return_value=np.zeros((2,2,3),np.uint8)
        worker.stop=threading.Event();worker.folder=Path('debug/recovery-test')
        worker.travel=Mock();worker.rooms=Mock();worker.fishing_presentations={}
        for method in ('checkpoint','issue','emit','preparation_step','publish'):
            setattr(worker,method,Mock())
        close=MatchResult(1450,830,30,30,1)
        observations=[Detection(FishingState.WAITING,{'close':close},True),response]
        with patch('ui.runner.FishingDetector') as detector,patch('ui.runner.MapNavigator') as nav:
            detector.return_value.detect.side_effect=observations
            nav.return_value.is_world.return_value=True
            nav.return_value.location.return_value='world'
            worker.travel.wait.side_effect=lambda predicate,*a,**k:predicate(worker.device.screenshot())
            self.assertTrue(worker.recover_error(RuntimeError('stalled')))
            nav.return_value.open_world.assert_called_once()
        self.assertEqual(worker.data['auto_restarts'],1)
        self.assertEqual(worker.data['status'],'RUNNING')
        return worker

    def test_waiting_close_can_return_directly_to_map_without_confirmation(self):
        worker=self.recover(Detection(FishingState.IDLE,{},True))
        worker.travel.button.assert_not_called()

    def test_only_verified_confirmation_is_answered_yes_for_recovery(self):
        worker=self.recover(Detection(FishingState.EXIT_CONFIRM,{},True))
        worker.travel.button.assert_called_once_with('exit_yes','Có: hủy lượt để khôi phục')
