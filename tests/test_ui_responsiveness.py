"""Presentation bursts stay bounded and preserve event/mission semantics."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from gui import App
from ui.theme import _header_source, banner_pixels


class ResponsivenessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'debug')
        self.folder_patch = patch('gui.ROOT', Path(self.temp.name))
        self.folder_patch.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root)
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        self.folder_patch.stop()
        self.temp.cleanup()

    @staticmethod
    def snapshot(count):
        return {'casts': count, 'bites': max(0, count - 1), 'bait_purchased': 50,
                'counts': {'cua': count}, 'targets': [],
                'wallet': {'coins': 1000, 'gold': 2}, 'tickets': {},
                'bait_stocks': {'ecological': 50 - count, 'dock': None}}

    def test_progress_and_log_burst_has_one_presentation_update(self):
        for count in range(1, 61):
            self.app.messages.put(('progress', self.snapshot(count)))
            self.app.messages.put(('log', f'round {count}'))
        with patch.object(self.app, 'render_snapshot', wraps=self.app.render_snapshot) as render:
            with patch.object(self.app, 'append_many', wraps=self.app.append_many) as append:
                self.app.poll()
        self.assertEqual(render.call_count, 1)
        self.assertEqual(append.call_count, 1)
        self.assertEqual(self.app.metric_values['casts'].get(), '60')
        self.assertEqual(self.app.table.item('cua', 'values')[1], '60')
        self.assertIn('round 1\nround 2\n', self.app.log.get('1.0', 'end'))
        self.assertIn('round 60\n', self.app.log.get('1.0', 'end'))

    def test_completion_sees_progress_and_logs_before_its_notification(self):
        observed = []
        self.app.notify_completion = lambda _: observed.append(
            (self.app.table.item('cua', 'values')[1], self.app.log.get('1.0', 'end')))
        for item in [('progress', self.snapshot(1)), ('log', 'before'),
                     ('notice', 'complete'), ('progress', self.snapshot(2))]:
            self.app.messages.put(item)
        self.app.poll()
        self.assertEqual(observed[0][0], '1')
        self.assertIn('before\n', observed[0][1])
        self.assertEqual(self.app.table.item('cua', 'values')[1], '2')

    def test_slow_completion_still_releases_worker_in_same_batch(self):
        from unittest.mock import Mock
        self.app.worker = Mock()
        self.app.messages.put(('notice', 'complete'))
        self.app.messages.put(('done', 'COMPLETE'))
        # A completion widget can exceed the old 8 ms frame budget.
        with patch('gui.winsound.PlaySound'), patch('gui.time.monotonic', side_effect=[0, .05]):
            self.app.poll()
        self.assertIsNone(self.app.worker)
        self.assertTrue(self.app.completion_popup.winfo_exists())
        self.assertEqual(self.app.status.get(), 'Hoàn thành nhiệm vụ')

    def test_error_dialog_observes_already_finished_worker_and_enabled_controls(self):
        from unittest.mock import Mock
        observed = []
        self.app.worker = Mock()
        self.app.messages.put(('error', 'failed'))
        self.app.messages.put(('done', 'ERROR'))
        with patch('gui.messagebox.showerror', side_effect=lambda *_: observed.append(
                (self.app.worker, str(self.app.reset_button['state'])))):
            self.app.poll()
        self.assertEqual(observed, [(None, 'normal')])

    def test_identical_snapshot_does_not_redraw_rows_or_rewrite_values(self):
        changes = []
        self.app.metric_values['casts'].trace_add('write', lambda *_: changes.append(1))
        with patch.object(self.app, 'schedule_workspace_resize') as resize:
            self.app.render_snapshot(self.snapshot(4))
            self.app.render_snapshot(self.snapshot(4))
        self.assertEqual(changes, [1])
        self.assertEqual(resize.call_count, 1)

    def test_log_view_is_bounded_even_for_a_large_batch(self):
        self.app.append_many([f'line {i}' for i in range(4000)])
        lines = self.app.log.get('1.0', 'end-1c').splitlines()
        self.assertEqual(len(lines), 1500)
        self.assertEqual(lines[0], 'line 2500')
        self.assertEqual(lines[-1], 'line 3999')

    def test_many_layout_requests_share_one_idle_job(self):
        for _ in range(40):
            self.app.schedule_workspace_resize()
        job = self.app.workspace_resize_job
        jobs = self.root.tk.call('after', 'info')
        self.assertIn(job, jobs)
        scripts = [self.root.tk.call('after', 'info', item)[0] for item in jobs]
        self.assertEqual(sum(str(script).endswith('resize_workspace') for script in scripts), 1)

    def test_banner_source_is_reused_and_cache_is_bounded(self):
        import cv2
        _header_source.cache_clear()
        with patch('cv2.imread', wraps=cv2.imread) as read:
            self.assertEqual(banner_pixels(1200, 120).shape, (120, 1200, 3))
            self.assertEqual(banner_pixels(1210, 125).shape, (125, 1210, 3))
        self.assertEqual(read.call_count, 1)
        self.assertEqual(_header_source.cache_info().maxsize, 2)

    def test_settings_only_reconfigures_fields_when_lock_changes(self):
        self.app.show_settings()
        dialog = self.app.settings_popup
        with patch.object(dialog.fields[0], 'configure', wraps=dialog.fields[0].configure) as configure:
            dialog.refresh_lock()
            dialog.refresh_lock()
            self.assertEqual(configure.call_count, 0)
            self.app.worker = object()
            dialog.refresh_lock()
            self.assertEqual(configure.call_count, 1)
            self.app.worker = None
            dialog.refresh_lock()
            self.assertEqual(configure.call_count, 2)
        dialog.cancel()

    def test_small_dashboard_has_visible_status_and_all_fish_without_page_scroll(self):
        from fishing.catch import SPECIES
        from fishing.inventory import TICKETS
        self.root.attributes('-alpha', 0)
        self.root.deiconify()
        self.root.geometry('1024x720')
        data = self.snapshot(4)
        data['counts'] = dict.fromkeys(SPECIES, 2)
        data['tickets'] = {key: {'status': 'active', 'expires_on': '2026-10-30'} for key in TICKETS}
        self.app.render_snapshot(data)
        self.root.update()
        self.app.resize_workspace()
        self.root.update()
        self.assertEqual(len(self.app.table.get_children()), 13)
        self.assertTrue(self.app.status_label.winfo_ismapped())
        self.assertEqual(self.app.workspace_scrollbar.winfo_manager(), '')
        self.assertLessEqual(self.app.content.winfo_reqheight(), self.app.workspace_canvas.winfo_height())


if __name__ == '__main__':
    unittest.main()
