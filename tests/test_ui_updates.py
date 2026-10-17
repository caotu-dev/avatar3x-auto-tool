import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from types import SimpleNamespace

import cv2

from config.settings import ROOT
from fishing.travel import TravelController
from ui.runner import BotWorker, Options
from fishing.bot import TrialResult


class UpdateTests(unittest.TestCase):
    def worker(self, options):
        return BotWorker(options, lambda *_: None, Mock())

    def test_quantity_and_custom_goals_validation(self):
        for value in (0, 51):
            with self.assertRaises(ValueError):
                Options(free=True, area='ca_ro', bait_quantity=value).validate()
        Options(custom_targets=(('ca_chep_vang', 2), ('cua', 3), ('ca_chim', 2))).validate()
        for goals in ((('unknown', 1),), (('cua', 0),), (('cua', 1), ('cua', 2))):
            with self.assertRaises(ValueError):
                Options(custom_targets=goals).validate()

    def test_custom_worker_follows_target_order_and_stops_when_done(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('ui.runner.ROOT', Path(folder)):
            worker = self.worker(Options(custom_targets=(('cua', 1), ('ca_chim', 1))))
            worker.device.device.is_connected.return_value = True
            worker.device.device.screenshot.return_value = __import__('numpy').zeros((900, 1600, 3), dtype='uint8')
            worker.device.device.get_screen_size.return_value = (1600, 900)
            worker.dismiss_level_popup = Mock()
            worker.rooms.is_open = Mock(return_value=False)
            worker.go = Mock()
            worker.prepare_area = Mock()
            worker.sell_before_midnight = Mock()
            rounds = [TrialResult('SUCCESS', 'ok', 1, 4, 4, s, '', 1, area, True)
                      for s, area in [('cua', 'ca_noc'), ('ca_chim', 'ca_map')]]
            with patch('ui.runner.FishingSession') as session:
                session.return_value.run.side_effect = [SimpleNamespace(rounds=[r], status='COMPLETE') for r in rounds]
                worker.run()
            self.assertEqual(worker.data['status'], 'COMPLETE')
            self.assertEqual([call.args[0] for call in worker.go.call_args_list], ['ca_noc', 'ca_map'])
            self.assertEqual([call.args[0] for call in worker.prepare_area.call_args_list], ['ca_noc', 'ca_map'])
            self.assertEqual(worker.data['counts'], {'cua': 1, 'ca_chim': 1})
            self.assertEqual([t['current'] for t in worker.data['targets']], [1, 1])

    def test_midnight_sale_once_per_date_and_resume_area(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('ui.runner.ROOT', Path(folder)):
            worker = self.worker(Options(free=True, area='ca_ro'))
            worker.travel = Mock()
            worker.sell_before_midnight('ca_ro', datetime(2026, 10, 9, 23, 56))
            worker.travel.center.assert_not_called()
            worker.sell_before_midnight('ca_ro', datetime(2026, 10, 9, 23, 57))
            worker.sell_before_midnight('ca_ro', datetime(2026, 10, 9, 23, 58))
            worker.travel.sell_and_buy.assert_called_once_with(sell=True, buy=False)
            worker.travel.enter.assert_called_once_with('ca_ro')
            next_worker = self.worker(Options(free=True, area='ca_ro'))
            self.assertEqual(next_worker.data['last_midnight_sale'], '2026-10-09')

    def test_failed_sale_does_not_mark_done(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('ui.runner.ROOT', Path(folder)):
            worker = self.worker(Options(free=True, area='ca_ro'))
            worker.travel = Mock()
            worker.travel.sell_and_buy.side_effect = RuntimeError('Không xác nhận bán')
            with self.assertRaises(RuntimeError):
                worker.sell_before_midnight('ca_ro', datetime(2026, 10, 9, 23, 57))
            self.assertIsNone(worker.data['last_midnight_sale'])
            worker.travel.enter.assert_not_called()

    def test_midnight_reset_clears_chest_but_preserves_mission_and_history(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('ui.runner.ROOT', Path(folder)):
            worker = self.worker(Options(custom_targets=(('cua', 3),)))
            worker.data.update(fish_inventory_date='2026-10-09', counts={'cua': 2}, unsold={'cua': 2})
            worker.data['targets'][0]['current'] = 2
            worker.refresh_chest_date(datetime(2026, 10, 10, 0, 1))
            self.assertEqual(worker.data['unsold'], {})
            self.assertEqual(worker.data['counts'], {'cua': 2})
            self.assertEqual(worker.data['targets'][0]['current'], 2)

    def test_custom_state_resumes_and_keeps_bait_separate(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('ui.runner.ROOT', Path(folder)):
            options = Options(custom_targets=(('cua', 3), ('ca_chim', 2)))
            worker = self.worker(options)
            worker.data['targets'][0]['current'] = 2
            worker.data['bait_remaining'] = 12
            worker.data['bait_stocks']['dock'] = 7
            worker.publish()
            resumed = self.worker(options)
            self.assertEqual([t['species'] for t in resumed.data['targets']], ['cua', 'ca_chim'])
            self.assertEqual(resumed.data['targets'][0]['current'], 2)
            self.assertEqual(resumed.data['bait_stocks'], {'ecological': 12, 'dock': 7})
            resumed.issue('error', 'test', round=4)
            entry = json.loads((Path(folder) / 'debug/bugs.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(entry['round'], 4)
            self.assertTrue(Path(entry['session']).is_dir())

    def test_purchase_requires_exact_item_quantity_price_and_receipt(self):
        image = cv2.imread(str(ROOT / 'tests/fixtures/quantity20.png'))
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder:
            travel = TravelController(Mock(), Path(folder))
            with patch('fishing.quest.read_ocr', return_value=['Bạn có muốn mua 50 vật phẩm', 'Mồi Trùng (0 Ngày) với giá 1000 xu?']):
                self.assertTrue(travel.purchase_matches(image, 50))
                self.assertFalse(travel.purchase_matches(image, 49))
            with patch('fishing.quest.read_ocr', return_value=['Bạn đã mua 50 Mồi Trùng thành công']):
                receipt = cv2.imread(str(ROOT / 'tests/fixtures/purchase20.png'))
                self.assertTrue(travel.purchase_matches(receipt, 50, receipt=True))
                self.assertFalse(travel.purchase_matches(receipt, 49, receipt=True))
            with patch('fishing.quest.read_ocr', return_value=['Bạn có muốn mua 50 vật phẩm', 'Mồi Trùng với giá 400 xu?']):
                self.assertFalse(travel.purchase_matches(image, 50))


if __name__ == '__main__':
    unittest.main()
