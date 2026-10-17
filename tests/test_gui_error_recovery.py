"""Presentation-only session recovery; no ADB or game worker is executed."""
import tempfile
import threading
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gui import App
from config.settings import ROOT


class ErrorRecoveryTests(unittest.TestCase):
    def test_terminal_events_restore_selected_mode_and_start_eligibility(self):
        for mode in range(3):
            for outcome in ('ERROR', 'STOPPED', 'COMPLETE'):
                with self.subTest(mode=mode, outcome=outcome), tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('gui.ROOT', Path(folder)):
                    root = tk.Tk()
                    root.withdraw()
                    try:
                        app = App(root)
                        app.tabs.select(mode)
                        root.update()
                        if mode == 0:
                            app.mission.set(True)
                        elif mode == 1:
                            app.free.set(True)
                            app.area.set('Khu cá rô')
                        else:
                            app.custom_list.set('cua', 'chosen', '☑')
                        app.options_changed()
                        worker = SimpleNamespace(run=lambda: None, pause=threading.Event(), stop=threading.Event())
                        with patch('gui.BotWorker', return_value=worker), patch('gui.threading.Thread') as thread:
                            app.start()
                            thread.return_value.start.assert_called_once()
                        root.update()
                        self.assertEqual(app.tabs.index('current'), mode)
                        self.assertEqual(str(app.start_button['state']), 'disabled')
                        app.pause_button.configure(text='Tiếp tục')
                        app.messages.put(('done', outcome))
                        app.poll()
                        root.update()
                        self.assertIsNone(app.worker)
                        self.assertEqual(app.tabs.index('current'), mode)
                        self.assertEqual(str(app.start_button['state']), 'normal')
                        self.assertEqual(str(app.pause_button['state']), 'disabled')
                        self.assertEqual(str(app.stop_button['state']), 'disabled')
                        self.assertEqual(app.pause_button['text'], 'Tạm dừng')
                        self.assertEqual(str(app.settings_button['state']), 'normal')
                        self.assertTrue(all(str(w['state']) == 'disabled' for w in app.target_controls[:-1]))
                        self.assertEqual(str(app.reset_button['state']), 'normal')
                        self.assertTrue(all(str(row['check']['state']) == 'normal' for row in app.custom_list.rows.values()))
                    finally:
                        for job in root.tk.call('after', 'info'):
                            root.after_cancel(job)
                        root.destroy()

    def test_recovery_reselects_a_tab_if_old_session_cleared_selection(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('gui.ROOT', Path(folder)):
            root = tk.Tk()
            root.withdraw()
            try:
                app = App(root)
                root.update()
                app.mission.set(True)
                app.worker = object()
                for tab in app.tabs.tabs():
                    app.tabs.tab(tab, state='disabled')
                root.update()
                self.assertEqual(app.tabs.select(), '')
                app.messages.put(('done', 'ERROR'))
                app.poll()
                root.update()
                self.assertEqual(app.tabs.index('current'), 0)
                self.assertTrue(app.mission.get())
                self.assertEqual(str(app.start_button['state']), 'normal')
            finally:
                for job in root.tk.call('after', 'info'):
                    root.after_cancel(job)
                root.destroy()


if __name__ == '__main__':
    unittest.main()

