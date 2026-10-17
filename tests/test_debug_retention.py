import tempfile,unittest,os
from pathlib import Path
from unittest.mock import patch
import numpy as np
from debug.retention import prune
from adb.screenshot import save_debug_screenshot

class RetentionTests(unittest.TestCase):
 def test_prunes_only_old_diagnostics_keeps_code_results_and_recent_ocr(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder:
   root=Path(folder)/'debug';root.mkdir()
   for name in ('old.png','notifications.py','result.json','fresh.png'):
    p=root/name;p.write_bytes(b'test')
    os.utime(p,(10,10) if name!='fresh.png' else (99999,99999))
   prune(root,max_bytes=1,max_age=1000,now=100000)
   self.assertFalse((root/'old.png').exists())
   for name in ('notifications.py','result.json','fresh.png'):self.assertTrue((root/name).exists())
   with self.assertRaises(ValueError):prune(root.parent)
 def test_automatic_images_have_three_slots_manual_exports_remain_png(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('config.settings.ROOT',Path(folder)):
   root=Path(folder);image=np.zeros((40,40,3),dtype=np.uint8)
   for i in range(12):
    p=save_debug_screenshot(image,root/'debug/ui/session/round'/f'{i:03d}_STEP.png')
    self.assertEqual(p.suffix,'.jpg')
   self.assertEqual(len(list((root/'debug/ui/session/round').glob('*'))),3)
   p=save_debug_screenshot(image,root/'manual.png');self.assertEqual(p.suffix,'.png')
