import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from fishing.travel import TravelController

class SelectionRetryTests(unittest.TestCase):
 def test_dropped_selection_retries_without_payment(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder:
   r=TravelController(Mock(),Path(folder));r.world=Mock()
   r.world.match.side_effect=lambda image,name: name=='fish_shop'
   r.tap=Mock();r.wait=Mock(side_effect=[RuntimeError('dropped'),True])
   r.select_worm()
   self.assertEqual(r.tap.call_count,2)
   self.assertTrue(all(c.args[0]==(999,261) for c in r.tap.call_args_list))
 def test_unknown_shop_never_taps(self):
  with tempfile.TemporaryDirectory(dir='debug') as folder:
   r=TravelController(Mock(),Path(folder));r.world=Mock();r.world.match.return_value=None;r.tap=Mock()
   with self.assertRaises(RuntimeError):r.select_worm()
   r.tap.assert_not_called()
