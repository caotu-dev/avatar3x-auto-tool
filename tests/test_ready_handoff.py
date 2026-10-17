import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from tests.test_bot import Clock,FakeDevice,FakeDetector,FakeSolver
from fishing.bot import OneRoundBot
from config.settings import TrialSettings
import numpy as np

class ReadyHandoffTests(unittest.TestCase):
 def trial(self,age):
  clock=Clock();detector=FakeDetector()
  device=FakeDevice([5] if age==0 else [1,5],clock)
  device.screenshot=Mock(wraps=device.screenshot)
  frame=np.full((2,2,3),1,dtype=np.uint8)
  with tempfile.TemporaryDirectory(dir='debug') as folder:
   bot=OneRoundBot(device,TrialSettings(),detector,FakeSolver(),Path(folder),clock.read,clock.sleep)
   bot.verified_ready=(frame,detector.detect(frame),-age)
   result=bot.run()
  return result,device
 def test_fresh_verified_readiness_skips_only_redundant_capture(self):
  result,device=self.trial(0)
  self.assertEqual(result.outcome,'SUCCESS');self.assertEqual(device.screenshot.call_count,1)
  self.assertEqual(device.taps,[(100,100)])
 def test_old_readiness_always_observes_again_before_cast(self):
  result,device=self.trial(1)
  self.assertEqual(result.outcome,'SUCCESS');self.assertEqual(device.screenshot.call_count,2)
