import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import cv2
from fishing.reconnect import ContinueScreen,ReconnectController,SessionLost
from ui.runner import BotWorker,Options,Cancelled

class RecoveryTests(unittest.TestCase):
 def test_real_continue_frames_and_world_are_distinct(self):
  reader=ContinueScreen()
  for name in ('continue','dropped_tap'):
   a=cv2.imread(str(Path(__file__).parent/'fixtures/reconnect'/f'{name}.png'))
   self.assertEqual(reader.detect(a),(659,562))
  self.assertIsNone(reader.detect(cv2.imread(str(Path(__file__).parent/'fixtures/navigation/world.png'))))

 def test_dark_login_is_detected_and_raises_session_loss_guard(self):
  import threading
  from ui.runner import ControlledDevice
  image=cv2.imread(str(Path(__file__).parent/'fixtures/login_logo_hearts.png'))
  point=ContinueScreen().detect(image)
  self.assertIsNotNone(point);self.assertTrue(539<point[0]<778 and 529<point[1]<594)
  device=Mock();device.screenshot.return_value=image
  with self.assertRaises(SessionLost):ControlledDevice(device,threading.Event()).screenshot()

 def test_dark_login_needs_both_logo_and_continue_button(self):
  image=cv2.imread(str(Path(__file__).parent/'fixtures/login_logo_hearts.png'))
  for bounds in ((400,190,1190,460),(530,520,790,610)):
   changed=image.copy();x,y,r,b=bounds;changed[y:b,x:r]=0
   self.assertIsNone(ContinueScreen().detect(changed))

 def controller(self,device,folder):
  clock=[0.0]
  def sleep(seconds):clock[0]+=seconds
  controller=ReconnectController(device,Path(folder),clock=lambda:clock[0],sleep=sleep)
  controller.event=Mock()
  return controller

 def test_real_cooldown_is_login_but_not_clickable(self):
  reader=ContinueScreen()
  image=cv2.imread(str(Path(__file__).parent/'fixtures/reconnect/cooldown.png'))
  self.assertTrue(reader.blocked(image));self.assertEqual(reader.detect(image),(659,562))
  self.assertFalse(reader.blocked(cv2.imread(str(Path(__file__).parent/'fixtures/reconnect/continue.png'))))

 def test_fifteen_second_cooldown_does_not_consume_retries(self):
  device=Mock();reader=Mock();frames=['login']*2+['cooldown']*75+['login']*2+['world']*2
  device.screenshot.side_effect=frames
  reader.blocked.side_effect=lambda a:a=='cooldown'
  reader.detect.side_effect=lambda a:(659,562) if a=='login' else None
  def tap(*point):
   self.assertEqual(device.screenshot.call_count,2 if device.tap.call_count==1 else 79)
  device.tap.side_effect=tap
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
   result=self.controller(device,folder).recover(reader,lambda a:a=='world')
  self.assertEqual(result['attempts'],2)

 def test_cooldown_can_be_cancelled_without_input(self):
  device=Mock();reader=Mock();reader.blocked.return_value=True
  calls=[0]
  def checkpoint():
   calls[0]+=1
   if calls[0]==4:raise Cancelled()
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
   with self.assertRaises(Cancelled):self.controller(device,folder).recover(reader,lambda a:False,checkpoint)
  device.tap.assert_not_called()

 def test_dropped_continue_retries_only_verified_screen(self):
  class Device:
   taps=[]
   def screenshot(self):return 'login' if len(self.taps)<2 else 'world'
   def tap(self,*p):self.taps.append(p)
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
   device=Device();device.taps=[]
   reader=Mock();reader.blocked.return_value=False;reader.detect.side_effect=lambda a:(659,562) if a=='login' else None
   result=self.controller(device,folder).recover(reader,lambda a:a=='world')
   self.assertEqual(result['attempts'],2);self.assertEqual(device.taps,[(659,562)]*2)

 def test_loading_frames_never_receive_retry(self):
  class Device:
   taps=[];frame=0
   def screenshot(self):
    self.frame+=1
    return 'login' if self.frame<=2 else 'loading' if self.frame<30 else 'pond'
   def tap(self,*p):self.taps.append(p)
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
   device=Device();device.taps=[]
   reader=Mock();reader.blocked.return_value=False;reader.detect.side_effect=lambda a:(659,562) if a=='login' else None
   result=self.controller(device,folder).recover(reader,lambda a:a=='pond')
   self.assertEqual(result['attempts'],1);self.assertEqual(len(device.taps),1)

 def test_retry_limit_and_timeout(self):
  device=Mock();device.screenshot.return_value='login'
  reader=Mock();reader.blocked.return_value=False;reader.detect.return_value=(659,562)
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
   with self.assertRaisesRegex(RuntimeError,'sau 3 lần'):
    self.controller(device,folder).recover(reader,lambda a:False,timeout=12)
   self.assertEqual(device.tap.call_count,3)

 def test_cancel_during_recovery_sends_no_input(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
   device=Mock();reader=Mock()
   def cancel():raise Cancelled()
   with self.assertRaises(Cancelled):self.controller(device,folder).recover(reader,lambda a:False,checkpoint=cancel)
   device.tap.assert_not_called()

 def test_failed_recovery_reports_error_instead_of_running(self):
  image=cv2.imread(str(Path(__file__).parent/'fixtures/reconnect/continue.png'))
  device=Mock();device.is_connected.return_value=True;device.get_screen_size.return_value=(1600,900);device.screenshot.return_value=image
  messages=[]
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.ReconnectController') as recovery:
   recovery.return_value.recover.side_effect=RuntimeError('Không khôi phục được phiên')
   worker=BotWorker(Options(free=True,area='ca_ro'),lambda k,v:messages.append((k,v)),device)
   worker.run()
   self.assertEqual(worker.data['status'],'ERROR')
   self.assertEqual(messages[-1],('done','ERROR'))
   self.assertTrue(worker.device.guard_session)
   self.assertTrue(any(k=='error' and 'khôi phục' in v for k,v in messages))

 def test_recovery_keeps_inventory_and_progress(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.ReconnectController') as recovery:
   worker=BotWorker(Options(free=True,area='ca_ro'),Mock(),Mock())
   worker.inventory_ready=True;worker.data['casts']=75
   worker.reconnect()
   self.assertTrue(worker.inventory_ready);self.assertEqual(worker.data['casts'],75)
   self.assertTrue(worker.device.guard_session);recovery.return_value.recover.assert_called_once()

if __name__=='__main__':unittest.main()
