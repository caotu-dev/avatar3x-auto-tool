import tempfile,unittest,tkinter as tk
from pathlib import Path
from unittest.mock import Mock,patch
import numpy as np
from gui import App
from ui.runner import BotWorker,Options,Cancelled
class DashboardTests(unittest.TestCase):
 def test_popup_cancel_ordering_and_column_positions(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('gui.ROOT',Path(folder)):
   root=tk.Tk();root.withdraw();app=App(root)
   try:
    app.tabs.select(2);root.update();app.custom_list.set('ca_ro','chosen','☑');app.custom_list.set('ca_noc','chosen','☑');app.refresh_custom_preview()
    app.table.selection_set('ca_noc');app.focus_progress_target();app.move_target(-1)
    self.assertEqual(app.table.get_children(),('ca_noc','ca_ro'))
    app.show_missions();app.custom_list.set('ca_chim','chosen','☑');app.close_missions(False)
    self.assertNotIn('ca_chim',dict(app.custom_targets()))
    self.assertEqual(app.mission_popup.state(),'withdrawn')
    app.layout_changed(type('Event',(),{'widget':root,'width':1536})())
    self.assertEqual(int(app.overview.grid_info()['column']),0)
    self.assertEqual(int(app.activity.grid_info()['column']),1)
    self.assertEqual(int(app.main_column.grid_info()['column']),2)
   finally:root.destroy()
 def worker(self,folder,**kwargs):
  with patch('ui.runner.ROOT',Path(folder)):
   worker=BotWorker(Options(free=True,area='ca_ro',**kwargs),Mock(),Mock())
  worker.device.screenshot=Mock(return_value=np.zeros((900,1600,3),dtype=np.uint8))
  worker.device.is_connected=Mock(return_value=True)
  worker.checkpoint=Mock();worker.preparation_step=Mock();worker.publish=Mock();worker.issue=Mock()
  return worker
 def test_recovery_budget_and_state_preservation(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.MapNavigator') as nav:
   w=self.worker(folder,auto_resume=True,resume_limit=2);w.data['targets']=[{'current':4}];w.data['casts']=5
   self.assertTrue(w.recover_error(RuntimeError('test')));self.assertTrue(w.recover_error(RuntimeError('test')))
   self.assertFalse(w.recover_error(RuntimeError('test')));self.assertEqual(w.data['auto_restarts'],2)
   self.assertEqual(w.data['targets'][0]['current'],4);self.assertEqual(w.data['casts'],5)
   self.assertEqual(nav.return_value.open_world.call_count,2)
 def test_stop_disabled_and_pending_purchase_never_restart(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.MapNavigator') as nav:
   w=self.worker(folder);self.assertFalse(w.recover_error(RuntimeError('test')))
   w=self.worker(folder,auto_resume=True);w.stop.set();self.assertFalse(w.recover_error(RuntimeError('test')))
   w=self.worker(folder,auto_resume=True);w.data['purchase_pending']=True;self.assertFalse(w.recover_error(RuntimeError('test')))
   nav.assert_not_called()
 def test_resume_limit_validation(self):
  for value in (0,21,True):
   with self.assertRaises(ValueError):Options(free=True,area='ca_ro',resume_limit=value).validate()

 def test_recovery_stops_when_same_failure_has_no_progress(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.MapNavigator') as nav:
   w=self.worker(folder,auto_resume=True,resume_limit=20)
   nav.return_value.open_world.side_effect=RuntimeError('Không thấy Menu')
   self.assertFalse(w.recover_error(RuntimeError('ticket title')))
   self.assertEqual(w.data['auto_restarts'],3)

 def test_recovery_closes_verified_shop_without_android_back(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.MapNavigator') as nav:
   w=self.worker(folder,auto_resume=True)
   w.device.back=Mock()
   nav.return_value.is_world.side_effect=[False,True]
   nav.return_value.location.return_value=None
   w.travel.world=Mock();w.travel.world.map_name.return_value=None
   w.travel.world.match.side_effect=lambda image,name: object() if name=='fish_shop' else None
   w.travel.tap=Mock();w.travel.wait=Mock()
   self.assertTrue(w.recover_error(RuntimeError('ticket title')))
   w.travel.tap.assert_called_once_with((200,650),'Đóng shop khi khôi phục')
   w.device.back.assert_not_called()

 def test_shop_description_does_not_replace_original_failure(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('fishing.quest.read_ocr',return_value=['Vé Câu Cá Lóc','10.000xu','Mua']):
   w=self.worker(folder)
   self.assertEqual(w.explain_error('Không xác nhận được thông tin vé'),'Không xác nhận được thông tin vé')

 def test_recovery_cancels_purchase_before_closing_shop(self):
  import cv2
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.MapNavigator') as nav:
   w=self.worker(folder,auto_resume=True);w.device.back=Mock()
   image=cv2.imread(str(Path(__file__).parent/'fixtures/loc_ticket_confirmation.png'))
   w.device.screenshot.return_value=image
   nav.return_value.is_world.side_effect=[False,False,True]
   nav.return_value.location.return_value=None
   w.travel.world.map_name=Mock(return_value=None)
   w.travel.tap=Mock();w.travel.wait=Mock()
   # After cancellation, the next frame contains only the shop.
   original=w.travel.world.match
   calls={'cancel':0}
   def match(frame,name):
    if name=='cancel':
     calls['cancel']+=1
     return original(frame,name) if calls['cancel']==1 else None
    return original(frame,name)
   w.travel.world.match=match
   self.assertTrue(w.recover_error(RuntimeError('confirmation')))
   self.assertEqual(w.travel.tap.call_args_list[0].args[1],'Hủy popup mua chưa thanh toán khi khôi phục')
   self.assertEqual(w.travel.tap.call_args_list[1].args[1],'Đóng shop khi khôi phục')
   w.device.back.assert_not_called()


 def test_worker_error_returns_world_and_enters_preparation_again(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator') as nav:
   w=self.worker(folder,auto_resume=True,resume_limit=1)
   w.device.is_connected=Mock(side_effect=[False,True,True]);w.device.get_screen_size=Mock(return_value=(1600,900))
   w.dismiss_level_popup=Mock();w.rooms.is_open=Mock(return_value=False)
   w.prepare_area=Mock();w.go=Mock(side_effect=Cancelled())
   w.run()
   self.assertEqual(w.data['status'],'STOPPED');self.assertEqual(w.data['auto_restarts'],1)
   nav.return_value.open_world.assert_called_once();w.prepare_area.assert_called_once_with('ca_ro')

 def test_custom_order_change_preserves_saved_progress(self):
  import json
  from fishing.catch import SPECIES
  from fishing.quest import AREAS
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.ROOT',Path(folder)):
   path=Path(folder)/'runtime/custom_mission.json';path.parent.mkdir()
   targets=[{'species':s,'name':SPECIES[s],'current':2,'required':4,'area':AREAS[s]} for s in ('ca_ro','ca_noc')]
   path.write_text(json.dumps({'plan':[['ca_ro',4],['ca_noc',4]],'targets':targets,'status':'STOPPED'}),encoding='utf-8')
   w=BotWorker(Options(custom_targets=(('ca_noc',4),('ca_ro',4))),Mock(),Mock())
   self.assertEqual([t['species'] for t in w.data['targets']],['ca_noc','ca_ro'])
   self.assertEqual([t['current'] for t in w.data['targets']],[2,2])

 def test_cache_survives_start_stop_and_new_app(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.ROOT',Path(folder)):
   cache={};options=Options(free=True,area='ca_ro')
   first=BotWorker(options,Mock(),Mock(),inventory_cache=cache)
   first.data.update(scan_complete=True,bait_remaining=17)
   first.data['bait_stocks']['dock']=8
   for value in first.data['tickets'].values():value['status']='active'
   first.publish()
   second=BotWorker(options,Mock(),Mock(),inventory_cache=cache)
   self.assertTrue(second.inventory_ready);self.assertEqual(second.data['bait_stocks']['ecological'],17)
   self.assertEqual(second.data['bait_stocks']['dock'],8)
   third=BotWorker(options,Mock(),Mock(),inventory_cache={})
   self.assertTrue(third.inventory_ready);self.assertEqual(third.data['bait_remaining'],17)
   self.assertEqual(third.data['bait_stocks']['dock'],8)
   self.assertEqual(third.data['tickets']['ca_ro']['status'],'active')

 def test_navbar_is_below_banner_controls_above_log_and_progress_expands(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('gui.ROOT',Path(folder)):
   root=tk.Tk();root.withdraw();app=App(root)
   try:
    self.assertIs(app.topbar.master,root)
    self.assertEqual(app.topbar.winfo_manager(),'pack')
    self.assertIs(app.start_button.master,app.session_controls)
    self.assertIs(app.session_controls.master,app.overview)
    self.assertIs(app.clock.master,app.session_controls)
    self.assertEqual(int(app.stop_button.grid_info()['row']),1)
    self.assertEqual(app.table.pack_info()['fill'],'both')
    self.assertEqual(app.activity.grid_rowconfigure(0)['weight'],1)
    self.assertEqual(app.content.grid_rowconfigure(0)['weight'],1)
   finally:root.destroy()

 def test_misses_display_casts_minus_bites_even_with_unknown_fish(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('gui.ROOT',Path(folder)):
   root=tk.Tk();root.withdraw();app=App(root)
   try:
    app.messages.put(('progress',{'casts':10,'bites':6,'misses':999,'bait_purchased':0,'unclassified_results':3,'targets':[],'counts':{}}))
    app.poll();self.assertEqual(app.metric_values['misses'].get(),'4')
   finally:root.destroy()
