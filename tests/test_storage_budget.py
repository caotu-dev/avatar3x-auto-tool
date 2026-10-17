import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from debug import retention


class StorageBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir='debug')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'debug'
        self.root.mkdir()
        self.now = 100000

    def write(self, relative, contents=b'x', modified=1):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        os.utime(path, (modified, modified))
        return path

    def runtime(self, name, data):
        folder = self.base / 'runtime'
        folder.mkdir(exist_ok=True)
        path = folder / name
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def result(self, relative, modified=1):
        return self.write(relative, json.dumps({'outcome': 'SUCCESS', 'casts': 1,
                                               'drags': 4, 'confirmed': 4}).encode(), modified)

    def test_budget_evicts_fresh_diagnostic_frames_but_preserves_live_ocr(self):
        frames = [self.write(f'ui/session/round_{i}/frame_0.jpg', b'x' * 100,
                             self.now - i) for i in range(8)]
        ocr = self.write('ui/session/inventory/chest_page_01.png', b'y' * 150, self.now)
        current = frames[0]
        remaining = retention.prune(self.root, max_bytes=200, now=self.now,
                                    protected_paths=(current,))
        self.assertTrue(current.exists())
        self.assertTrue(ocr.exists())
        self.assertTrue(all(not path.exists() for path in frames[1:]))
        self.assertEqual(remaining, 150)  # Protected current frame is exempt.

    def test_completed_gui_results_expire_but_cli_mission_evidence_survives(self):
        completed = self.result('ui/old/round_0001/round_001/result.json')
        custom_ledger_result = self.result('missions/custom/round_001/result.json')
        unknown = self.write('result.json', b'custom recovery evidence')
        source = self.write('notifications.py', b'import time')
        template = self.write('templates/reference.png', b'template')
        retention.prune(self.root, max_bytes=0, max_age=1, now=self.now)
        self.assertFalse(completed.exists())
        for path in (custom_ledger_result, unknown, source, template):
            self.assertTrue(path.exists(), path)

    def test_pending_round_and_payments_preserve_evidence_without_changing_runtime(self):
        round_folder = self.root / 'ui/old/round_0001'
        result = self.result('ui/old/round_0001/round_001/result.json')
        image = self.write('ui/old/round_0001/frame_0.jpg', b'evidence')
        other = self.write('ui/completed/frame_0.jpg')
        state = self.runtime('mission.json', {'pending_round': {'path': str(round_folder)}})
        original = state.read_bytes()
        retention.prune(self.root, max_bytes=0, max_age=1, now=self.now)
        self.assertTrue(result.exists())
        self.assertTrue(image.exists())
        self.assertFalse(other.exists())
        self.assertEqual(state.read_bytes(), original)
        payment = self.runtime('ui_inventory.json', {'purchase_pending': True})
        receipt = self.write('ui/old/payment/events.jsonl', b'{"paid":true}\n' * 40)
        retention.prune(self.root, max_bytes=0, max_age=1, now=self.now, max_log_bytes=20)
        self.assertEqual(receipt.read_bytes(), b'{"paid":true}\n' * 40)
        self.assertEqual(json.loads(payment.read_text()), {'purchase_pending': True})

    def test_logs_keep_bounded_complete_utf8_lines(self):
        lines = [json.dumps({'n': i, 'message': 'Cá rô'}, ensure_ascii=False) + '\n'
                 for i in range(60)]
        path = self.write('bugs.jsonl', ''.join(lines).encode('utf-8'), self.now)
        retention.prune(self.root, now=self.now, max_log_bytes=256)
        raw = path.read_bytes()
        self.assertLessEqual(len(raw), 256)
        parsed = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
        self.assertTrue(parsed)
        self.assertEqual(parsed[-1]['n'], 59)
        self.assertEqual(parsed[-1]['message'], 'Cá rô')
        self.assertFalse(path.with_name(path.name + '.retention.tmp').exists())

    def test_empty_old_directories_are_removed_except_active_output_folders(self):
        old = self.root / 'ui/old/empty'
        active = self.root / 'ui/current/travel'
        for folder in (old, active):
            folder.mkdir(parents=True)
            os.utime(folder, (1, 1))
        self.runtime('ui_last.json', {'log': str(active.parent), 'status': 'RUNNING'})
        retention.prune(self.root, now=self.now)
        self.assertFalse(old.exists())
        self.assertTrue(active.exists())

    def test_throttle_runs_once_a_minute_and_force_bypasses_it(self):
        retention._last.pop(str(self.root.resolve()), None)
        with patch.object(retention, 'prune', return_value=123) as prune:
            with patch.object(retention.time, 'monotonic', side_effect=(100, 120, 161, 162)):
                self.assertEqual(retention.maybe_prune(self.root), 123)
                self.assertIsNone(retention.maybe_prune(self.root))
                self.assertEqual(retention.maybe_prune(self.root), 123)
                self.assertEqual(retention.maybe_prune(self.root, force=True), 123)
        self.assertEqual(prune.call_count, 3)

    def test_external_paths_and_hard_link_logs_are_not_modified(self):
        outside = self.base / 'outside.jsonl'
        self.assertIsNone(retention._within(outside, self.root))
        linked = MagicMock()
        linked.name = 'hard.jsonl'
        linked.stat.return_value.st_nlink = 2
        self.assertEqual(retention._trim_log(linked, 2000, 32), 2000)
        linked.open.assert_not_called()
        with self.assertRaises(ValueError):
            retention.prune(self.base)


if __name__ == '__main__':
    unittest.main()
