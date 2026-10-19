"""Routine rounds do no diagnostic encoding; faults and receipts remain usable."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from adb.screenshot import save_event_screenshot
from fishing.travel import TravelController


class DiagnosticCapturePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path('debug'))
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        patcher=patch('config.settings.ROOT',self.root)
        patcher.start();self.addCleanup(patcher.stop)
        patcher=patch('debug.retention.maybe_prune')
        patcher.start();self.addCleanup(patcher.stop)
        self.image=np.zeros((40,40,3),np.uint8)
        self.output=self.root/'debug/ui/session/round_0001'

    def test_thousand_routine_events_create_no_images_or_encoding(self):
        events=('CAST','WAITING','FISHING','DRAG','CONFIRMED','TAP','FINISH')
        with patch('adb.screenshot.cv2.imencode') as encode:
            for i in range(1000):
                self.assertIsNone(save_event_screenshot(self.image,self.output/f'{i:03d}_STEP.png',events[i%len(events)]))
            self.assertIsNone(save_event_screenshot(self.image,self.output/'STOP.png','STOP',{'outcome':'SUCCESS'}))
            encode.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_faults_and_transaction_receipts_keep_only_three_images_per_folder(self):
        events=('TIMEOUT','UNKNOWN','WAIT_RESULT','RETRY_DRAG','PURCHASE_PENDING',
                'PURCHASE_CONFIRMED','TICKET_PURCHASE_CONFIRMED','SALE_CONFIRMED')
        for i,event in enumerate(events):
            saved=save_event_screenshot(self.image,self.output/f'{i:03d}_{event}.png',event)
            self.assertTrue(saved.is_file())
        self.assertEqual(len(list(self.output.glob('*.jpg'))),3)
        self.assertIsNotNone(save_event_screenshot(self.image,self.output/'STOP.png','STOP',{'outcome':'STOPPED'}))
        self.assertIsNotNone(save_event_screenshot(self.image,self.output/'STOP.png','STOP',{'outcome':'RESULT'}))

    def test_all_navigation_metadata_and_purchase_callbacks_survive_without_normal_images(self):
        events=[]
        travel=TravelController(None,self.output,on_event=lambda name,details:events.append(name))
        travel.screen=self.image
        for i in range(50):travel.event('TAP',point=(i,i))
        travel.event('PURCHASE_PENDING',quantity=50)
        travel.event('PURCHASE_CONFIRMED',quantity=50)
        records=[json.loads(line) for line in (self.output/'events.jsonl').read_text().splitlines()]
        self.assertEqual(len(records),52)
        self.assertTrue(all(record['image'] is None for record in records[:50]))
        self.assertEqual(events[-2:],['PURCHASE_PENDING','PURCHASE_CONFIRMED'])
        self.assertTrue(all(record['image'].endswith('.jpg') for record in records[-2:]))

    def test_manual_exports_remain_png(self):
        saved=save_event_screenshot(self.image,self.root/'manual/normal.png','DRAG')
        self.assertEqual(saved.suffix,'.png')
        self.assertTrue(saved.is_file())

    def test_idle_timer_never_reads_runtime_while_worker_is_active(self):
        from gui import App
        app=App.__new__(App)
        app.root=Mock()
        with patch('gui.ROOT',self.root),patch('debug.retention.maybe_prune') as prune:
            app.worker=object()
            app.prune_idle_diagnostics()
            prune.assert_not_called()
            app.worker=None
            app.prune_idle_diagnostics()
            prune.assert_called_once_with(self.root/'debug')
        self.assertEqual(app.root.after.call_count,2)
        self.assertEqual(app.root.after.call_args.args[0],60000)
