import tempfile,unittest,json
from pathlib import Path
from unittest.mock import Mock,patch
from ui import state_cache
from ui.runner import BotWorker,Options

class StateCacheTests(unittest.TestCase):
 def test_restart_reuses_individual_observations_and_quest(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.ROOT',Path(folder)):
   w=BotWorker(Options(mission=True),Mock())
   w.data.update(quest_title='Nhiệm vụ - 13',targets=[{'species':'ca_loc','current':3,'required':30}])
   w.data['tickets']['ca_noc']={'status':'active','expires_on':'2099-01-01'}
   w.data['bait_remaining']=12;w.publish()
   again=BotWorker(Options(mission=True),Mock(),inventory_cache={})
   self.assertEqual(again.reusable_quest()['targets'][0]['current'],3)
   self.assertEqual(again.data['bait_stocks']['ecological'],12)
   again.travel=Mock();again.publish=Mock()
   with patch('ui.runner.MapNavigator') as nav:
    again.prepare_area('ca_noc');nav.assert_not_called();again.travel.center.assert_not_called()
   self.assertEqual(again.data['tickets']['dock']['status'],'unknown')
 def test_wrong_device_expired_ticket_and_corrupt_file(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder:
   path=Path(folder)/'character_state.json'
   payload={'version':1,'serial':'one','inventory':{'tickets':{'ca_ro':{'status':'active','expires_on':'2000-01-01'}},'bait_stocks':{'dock':7,'ecological':-2}}}
   path.write_text(json.dumps(payload))
   self.assertEqual(state_cache.load(path,'two'),{})
   state=state_cache.load(path,'one')
   self.assertEqual(state['tickets']['ca_ro']['status'],'unknown')
   self.assertEqual(state['bait_stocks'],{'dock':7})
   path.write_text('{broken');self.assertEqual(state_cache.load(path,'one'),{})
 def test_unknown_quest_is_not_reused(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.ROOT',Path(folder)):
   w=BotWorker(Options(mission=True),Mock())
   w.cached_quest={'title':'task','targets':[{'species':None,'current':0,'required':30}]}
   self.assertIsNone(w.reusable_quest())
