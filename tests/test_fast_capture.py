import struct,unittest,subprocess
from unittest.mock import Mock
import cv2
import numpy as np
from adb.device import AdbDevice
from adb.screenshot import decode_raw_screenshot

class FastCaptureTests(unittest.TestCase):
 def test_raw_headers_preserve_bgr_pixels(self):
  bgr=np.arange(18,dtype=np.uint8).reshape(2,3,3)
  rgba=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGBA)
  for header in (struct.pack('<III',3,2,1),struct.pack('<IIII',3,2,1,0)):
   np.testing.assert_array_equal(decode_raw_screenshot(header+rgba.tobytes()),bgr)
  for payload in (b'',struct.pack('<III',3,2,4)+bytes(24),struct.pack('<III',3,2,1)+bytes(20)):
   with self.assertRaises(ValueError):decode_raw_screenshot(payload)
 def test_invalid_raw_falls_back_once_then_uses_png(self):
  image=np.zeros((2,3,3),dtype=np.uint8);png=cv2.imencode('.png',image)[1].tobytes()
  runner=Mock(side_effect=[subprocess.CompletedProcess([],0,b'unsupported',b''),subprocess.CompletedProcess([],0,png,b''),subprocess.CompletedProcess([],0,png,b'')])
  device=AdbDevice('test',runner=runner,fast_capture=True)
  np.testing.assert_array_equal(device.screenshot(),image)
  self.assertFalse(device.fast_capture)
  device.screenshot()
  self.assertEqual([c.args[0][-1] for c in runner.call_args_list],['screencap','-p','-p'])
