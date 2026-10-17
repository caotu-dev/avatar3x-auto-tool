import json
import gc
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from debug import retention


class StorageBudgetTests(unittest.TestCase):
    def setUp(self):
        # Previous GUI tests can leave destroyed Tk objects in reference cycles.
        # Their finalizers must run on the main thread before spawning a worker.
        gc.collect()
        for name, value in (('_lock', threading.Lock()), ('_last', {}), ('_snapshots', {})):
            isolate = patch.object(retention, name, value)
            isolate.start()
            self.addCleanup(isolate.stop)
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

    def test_historical_pending_backup_does_not_disable_cleanup(self):
        self.runtime('ui_inventory.before_receipt_recovery.json', {'purchase_pending': True})
        self.runtime('ui_inventory.json', {'purchase_pending': False})
        frame = self.write('ui/old/frame_0.jpg')
        retention.prune(self.root, max_bytes=0, now=self.now)
        self.assertFalse(frame.exists())

    def test_worker_atomic_state_writes_and_pending_protection_during_background_cleanup(self):
        from ui.runner import BotWorker, Options
        entered, release = threading.Event(), threading.Event()
        workers, violations, completed = [], [], []
        real_prune, real_read, real_thread = retention.prune, retention._read_json, threading.Thread
        main_thread = threading.current_thread()
        old_folder = self.root / 'ui/previous'
        self.runtime('ui_last.json', {'status': 'RUNNING', 'log': str(old_folder)})

        def read_checked(path):
            if threading.current_thread() is not main_thread and path.parent.name == 'runtime':
                violations.append(path)
                raise AssertionError('Background cleanup must not hold runtime file handles')
            return real_read(path)

        def blocked_prune(*args, **kwargs):
            entered.set()
            release.wait(5)
            kwargs.update(max_bytes=0, max_age=0)
            completed.append(real_prune(*args, **kwargs))

        def create_thread(*args, **kwargs):
            worker = real_thread(*args, **kwargs)
            workers.append(worker)
            return worker

        with patch('ui.runner.ROOT', self.base), patch.object(retention, '_read_json', side_effect=read_checked):
            worker = BotWorker(Options(free=True, area='ca_ro'), lambda *args: None,
                               device=MagicMock(serial='storage-test'))
            worker.data['status'] = 'RUNNING'
            with patch.object(retention, 'prune', side_effect=blocked_prune):
                with patch.object(retention.threading, 'Thread', side_effect=create_thread):
                    try:
                        worker.publish()
                        self.assertTrue(entered.wait(1))
                        key = str(self.root.resolve())
                        snapshot = retention._snapshots[key]
                        self.assertIn(old_folder.resolve(), snapshot[0][1])
                        evidence = worker.folder / 'frame_0.jpg'
                        evidence.write_bytes(b'pending transaction evidence')
                        worker.data['purchase_pending'] = True
                        for coins in range(20):
                            worker.data['wallet']['coins'] = coins
                            worker.publish()  # Actual atomic tmp.replace calls.
                        self.assertEqual(real_read(self.base / 'runtime/ui_inventory.json')['purchase_pending'], True)
                        self.assertEqual(real_read(self.base / 'runtime/ui_last.json')['wallet']['coins'], 19)
                        self.assertIn(worker.folder.resolve(), snapshot[0][0])
                    finally:
                        release.set()
                        for job in workers:
                            job.join(3)
                            self.assertFalse(job.is_alive())
            self.assertTrue(evidence.exists())
        self.assertFalse(violations)
        self.assertEqual(len(workers), 1)
        self.assertEqual(len(completed), 1)

    def test_oversized_runtime_record_is_rejected_without_reading_payload(self):
        path = self.runtime('ui_inventory.json', {})
        with path.open('wb') as stream:
            stream.truncate(retention.MAX_RECORD_BYTES + 1)
        with self.assertRaisesRegex(ValueError, 'too large'):
            retention._read_json(path)

    def test_completed_report_count_is_bounded_even_when_metadata_is_small(self):
        folders = []
        for index in range(6):
            folder = f'ui/current/round_{index:04d}'
            self.result(f'{folder}/round_001/result.json', self.now - 6 + index)
            self.write(f'{folder}/summary.json', b'{}', self.now)
            self.write(f'{folder}/round_001/frame_0.jpg', b'frame', self.now)
            folders.append(self.root / folder)
        self.runtime('ui_last.json', {'log': str(self.root / 'ui/current'), 'status': 'RUNNING'})
        retention.prune(self.root, now=self.now, max_reports=2)
        self.assertTrue(all(not folder.exists() for folder in folders[:4]))
        self.assertTrue(all((folder / 'round_001/result.json').exists() for folder in folders[4:]))

    def test_background_scan_does_not_delete_a_frame_refreshed_after_stat(self):
        frame = self.write('ui/current/frame_0.jpg', b'old', self.now)
        entries = retention._entries

        def refresh_after_scan(root):
            yield from entries(root)
            frame.write_bytes(b'new frame')
            os.utime(frame, (self.now + 1, self.now + 1))

        with patch.object(retention, '_entries', side_effect=refresh_after_scan):
            retention.prune(self.root, now=self.now, max_bytes=0)
        self.assertEqual(frame.read_bytes(), b'new frame')

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
                self.assertEqual(retention.maybe_prune(self.root, background=False), 123)
                self.assertIsNone(retention.maybe_prune(self.root, background=False))
                self.assertEqual(retention.maybe_prune(self.root, background=False), 123)
                self.assertEqual(retention.maybe_prune(self.root, force=True), 123)
        self.assertEqual(prune.call_count, 3)

    def test_background_prune_returns_immediately_and_only_one_job_runs(self):
        retention._last.pop(str(self.root.resolve()), None)
        entered, release = threading.Event(), threading.Event()
        workers = []
        real_thread = threading.Thread
        acquired_gate = retention._lock

        def blocked(*args, **kwargs):
            entered.set()
            release.wait(5)

        def create_thread(*args, **kwargs):
            worker = real_thread(*args, **kwargs)
            workers.append(worker)
            return worker

        with patch.object(retention, 'prune', side_effect=blocked) as prune:
            with patch.object(retention.threading, 'Thread', side_effect=create_thread):
                try:
                    started = time.monotonic()
                    self.assertIsNone(retention.maybe_prune(self.root))
                    self.assertLess(time.monotonic() - started, 1)
                    self.assertTrue(entered.wait(1))
                    retention.maybe_prune(self.root, force=True)
                    self.assertEqual(prune.call_count, 1)
                    self.assertEqual(len(workers), 1)
                    self.assertTrue(workers[0].daemon)
                finally:
                    replacement = threading.Lock()
                    # An existing job owns its original gate even if another
                    # isolated test replaces the module state in the meantime.
                    with patch.object(retention, '_lock', replacement):
                        release.set()
                        for worker in workers:
                            worker.join(2)
                            self.assertFalse(worker.is_alive())
                        self.assertFalse(acquired_gate.locked())
                        self.assertFalse(replacement.locked())

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
