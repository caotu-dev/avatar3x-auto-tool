import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import numpy as np
from ui.runner import BotWorker,Options
from fishing.quest import QuestReader
from vision.matcher import MatchResult
class QuestCycleTests(unittest.TestCase):
 def test_task_13_observed_seahorse_is_supported(self):
  from fishing.quest import parse_quest
  task=parse_quest(['Nhiệm Vụ Thợ Câu - 13','- Cäu 30 con cé 16c - 0/30','- Cäu 30 con cé ngVa - 0/30','- Cäu 50 con cé ro - 0/50'])
  self.assertEqual([t['species'] for t in task['targets']],['ca_loc','ca_ngua','ca_ro'])
  self.assertEqual([t['area'] for t in task['targets']],['ca_noc','ca_map','ca_ro'])
 def test_unknown_target_does_not_retry_world_navigation(self):
  from ui.runner import NonRecoverableError
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.MapNavigator') as nav:
   from dataclasses import replace
   w=self.worker(folder);w.options=replace(w.options,auto_resume=True)
   self.assertFalse(w.recover_error(NonRecoverableError('unknown fish')))
   nav.assert_not_called()
 def worker(self,folder):
  with patch('ui.runner.ROOT',Path(folder)):w=BotWorker(Options(mission=True),Mock(),Mock())
  w.data.update(area='ca_ro',quest_title='Nhiệm vụ - 11');w.checkpoint=Mock();w.publish=Mock();w.preparation_step=Mock();w.travel=Mock()
  return w
 def task(self,title,completed=False,ack=False,species='ca_ro'):
  return {'title_raw':title,'completed':completed,'reward_acknowledged':ack,'targets':[{'species':species,'name':'Cá rô','current':1 if completed else 0,'required':1}]}
 def test_verified_reward_moves_to_next_task_without_completing_session(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder:
   w=self.worker(folder);w.data['casts']=31;w.read_quest=Mock(return_value=self.task('Nhiệm vụ - 12',ack=True))
   self.assertTrue(w.advance_game_quest());self.assertEqual(w.data['quest_title'],'Nhiệm vụ - 12');self.assertEqual(w.data['casts'],31)
   self.assertEqual(w.data['quests_completed'],1);w.travel.center.assert_called_once_with('ca_ro')
   self.assertFalse(any(c.args[0]=='notice' for c in w.emit.call_args_list))
 def test_incomplete_server_progress_continues_same_task(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder:
   w=self.worker(folder);w.read_quest=Mock(return_value=self.task('Nhiệm vụ - 11'))
   self.assertFalse(w.advance_game_quest());self.assertEqual(w.read_quest.call_count,1)
 def test_no_new_task_after_hand_in_is_bounded(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder:
   w=self.worker(folder);w.read_quest=Mock(return_value=self.task('Nhiệm vụ - 11',completed=True))
   with self.assertRaisesRegex(RuntimeError,'Chưa xác nhận nhiệm vụ mới'):w.advance_game_quest()
   self.assertEqual(w.read_quest.call_count,2)
 def test_unsupported_new_task_does_not_start_fishing(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder:
   w=self.worker(folder);w.read_quest=Mock(return_value=self.task('Nhiệm vụ - 12',species='unknown'))
   with self.assertRaisesRegex(RuntimeError,'chưa hỗ trợ'):w.advance_game_quest()
 def test_receipt_requires_two_verified_frames_and_only_acknowledges_once(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('fishing.quest.ROOT',Path(folder)),patch('fishing.quest.read_ocr',return_value=['Bạn đã hoàn thành nhiệm vụ và bạn nhận được 5000 xu']),patch('fishing.world.WorldDetector') as world:
   reader=QuestReader(Mock());image=np.zeros((900,1600,3),dtype=np.uint8);reader.device.screenshot.return_value=image
   world.return_value.match.side_effect=[MatchResult(700,500,196,78,1),MatchResult(700,500,196,78,1),None]
   self.assertTrue(reader.dismiss_reward(image));reader.device.tap.assert_called_once_with(798,539)
   self.assertTrue(reader.reward_acknowledged)
 def test_other_ok_popup_is_never_confirmed_as_reward(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('fishing.quest.ROOT',Path(folder)),patch('fishing.quest.read_ocr',return_value=['Bạn có muốn mua vật phẩm giá 5000 xu']),patch('fishing.world.WorldDetector') as world:
   reader=QuestReader(Mock());world.return_value.match.return_value=MatchResult(700,500,196,78,1)
   self.assertFalse(reader.dismiss_reward(np.zeros((900,1600,3),dtype=np.uint8)));reader.device.tap.assert_not_called()

 def test_observed_task_12_ocr_names_map_to_supported_fish(self):
  from fishing.quest import parse_quest
  task=parse_quest(['Nhiệm vụ hiện tại: Nhiệm Vụ Thợ Câu - 12','- Câu 30 con cé chép ving - 0/30','- Câu 30 con cé 16c - 0/30','- Câu 30 con cé n6c - 0/30','Phần Thưởng:'])
  self.assertEqual([t['species'] for t in task['targets']],['ca_chep_vang','ca_loc','ca_noc'])
  self.assertEqual([t['required'] for t in task['targets']],[30,30,30])
