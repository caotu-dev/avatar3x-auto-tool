"""Approved-reference regressions for progress rendering and preserved callbacks."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from gui import App
from ui.theme import token

class ReferenceRedesignTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir='debug')
  self.patch=patch('gui.ROOT',Path(self.temp.name));self.patch.start()
  self.root=tk.Tk();self.root.withdraw();self.app=App(self.root)
 def tearDown(self):
  for job in self.root.tk.call('after','info'):self.root.after_cancel(job)
  self.root.destroy();self.patch.stop();self.temp.cleanup()
 def test_weighted_progress_and_cyan_track(self):
  bar=self.app.mission_progress
  with patch.object(bar.canvas,'winfo_width',return_value=400):
   bar.set_targets([dict(current=12,required=50),dict(current=5,required=50),dict(current=0,required=50)])
  self.assertEqual(bar.summary.get(),'17 / 150 cá • 11,3%')
  self.assertEqual(bar._fill_image.width(),44)
  self.assertEqual(bar._track_image.width(),400)
  expected=tuple(int(token('color.progress.track')[i:i+2],16) for i in (1,3,5))
  self.assertTrue(all(abs(a-b)<=1 for a,b in zip(bar._track_image.get(200,17),expected)))
  self.assertEqual(bar._track_image.get(0,0),(255,255,255))
 def test_zero_negative_and_surplus_targets_are_safe(self):
  bar=self.app.mission_progress
  with patch.object(bar.canvas,'winfo_width',return_value=400):
   for targets,summary in [([dict(current=3,required=0)],'—  Chưa đặt mục tiêu'),([dict(current=-2,required=10)],'0 / 10 cá • 0%'),([dict(current=40,required=10)],'10 / 10 cá • 100%')]:
    bar.set_targets(targets);bar.draw()
    self.assertEqual(bar.summary.get(),summary)
   self.assertEqual(bar._fill_image.width(),390)
 def test_log_folder_button_retains_real_callback(self):
  with patch('gui.os.startfile') as open_folder:
   self.app.log_folder_button.invoke()
  expected=Path(self.temp.name)/'debug/ui'
  self.assertTrue(expected.is_dir());open_folder.assert_called_once_with(expected)
 def test_session_timer_still_uses_elapsed_time(self):
  self.app.timer_started=100
  with patch('gui.time.monotonic',return_value=144):self.app.poll()
  self.assertEqual(self.app.elapsed.get(),'00:00:44')
 def test_worker_queue_updates_real_widgets(self):
  self.app.messages.put(('progress',dict(casts=10,bites=8,bait_purchased=4,counts={},targets=[dict(species='ca_ro',name='Cá rô',current=2,required=10)],tickets={},wallet={})))
  self.app.messages.put(('log','[QA] cập nhật qua hàng đợi'))
  self.app.poll()
  self.assertEqual(self.app.metric_values['misses'].get(),'2')
  self.assertEqual(self.app.mission_progress.summary.get(),'2 / 10 cá • 20%')
  self.assertIn('[QA]',self.app.log.get('1.0','end'))
  self.assertEqual(self.app.ticket_values['Vé câu cá rô'].get(),'Chưa xác định')

if __name__=='__main__':unittest.main()
