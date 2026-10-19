import unittest
import threading
import tempfile
from pathlib import Path
from unittest.mock import patch
import tkinter as tk

from ui.runner import Options, ControlledDevice, Cancelled, BotWorker
from fishing.bot import TrialResult
from gui import App
from config.settings import ROOT


class UiTests(unittest.TestCase):
    def test_invalid_options_never_start(self):
        for options in (Options(), Options(free=True), Options(free=True, area='unknown')):
            with self.assertRaises(ValueError):
                options.validate()
        Options(mission=True).validate()
        Options(free=True, area='ca_ro').validate()

    def test_stop_blocks_new_inputs(self):
        class Device:
            def tap(self, *point):
                raise AssertionError('Không được gửi tap')
        stop = threading.Event()
        device = ControlledDevice(Device(), stop)
        stop.set()
        with self.assertRaises(Cancelled):
            device.tap(1, 2)

    def test_connection_error_notifies_and_finishes_without_actions(self):
        class Device:
            def is_connected(self):
                return False
        messages = []
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('ui.runner.ROOT', Path(folder)):
            worker = BotWorker(Options(free=True, area='ca_ro'), lambda k, v: messages.append((k, v)), Device())
            worker.run()
            self.assertEqual(worker.data['status'], 'ERROR')
            self.assertTrue(any(k == 'error' and 'ADB' in v for k, v in messages))
            self.assertEqual(messages[-1], ('done', 'ERROR'))

    def test_progress_only_counts_confirmed_fish_and_caps_target(self):
        worker = BotWorker.__new__(BotWorker)
        worker.data = {'casts': 0, 'bites': 0, 'misses': 0, 'unclassified_results': 0,
                       'bait_remaining': 20, 'counts': {}, 'unsold': {},
                       'targets': [{'species': 'cua', 'current': 2, 'required': 3}]}
        worker.publish = lambda: None
        worker.record(TrialResult('SUCCESS', '', 1, 1, 1, 'cua', 'Cua', 1, 'ca_noc', True))
        worker.record(TrialResult('RESULT', '', 1, 0, 0))
        self.assertEqual(worker.data['counts'], {'cua': 1})
        self.assertEqual(worker.data['targets'][0]['current'], 3)
        self.assertEqual(worker.data['bait_remaining'], 18)
        self.assertEqual(worker.data['misses'], 1)

    def test_dashboard_counts_only_success_with_a_specific_fish(self):
        worker = BotWorker.__new__(BotWorker)
        worker.data = {'casts': 0, 'bites': 0, 'misses': 0, 'unclassified_results': 0,
                       'bait_remaining': 20, 'counts': {}, 'unsold': {}, 'targets': []}
        worker.publish = lambda: None
        cases = [
            # The reported Xong/RESULT case must be a miss even after a bite.
            (TrialResult('RESULT', 'Xong', 1, 0, 0, bite_observed=True), 0, 1),
            (TrialResult('FAILED', '', 1, 0, 0, bite_observed=True), 0, 2),
            (TrialResult('SUCCESS', '', 1, 0, 0, bite_observed=True), 0, 3),
            (TrialResult('SUCCESS', '', 1, 0, 0, fish_species='unknown'), 0, 4),
            (TrialResult('SUCCESS', '', 1, 0, 0, fish_species='ca_ro'), 1, 4),
            (TrialResult('SUCCESS', '', 1, 0, 0, fish_species='cua', bite_observed=True), 2, 4),
            (TrialResult('ABORTED', '', 1, 0, 0, bite_observed=True), 2, 5),
        ]
        for result, caught, missed in cases:
            with self.subTest(outcome=result.outcome, species=result.fish_species):
                worker.record(result)
                self.assertEqual(worker.data['bites'], caught)
                self.assertEqual(worker.data['misses'], missed)
        self.assertEqual(worker.data['casts'], 7)
        self.assertEqual(worker.data['bait_remaining'], 13)
        self.assertEqual(worker.data['counts']['ca_ro'], 1)
        self.assertEqual(worker.data['counts']['cua'], 1)

    def test_widgets_require_mode_and_free_area(self):
        temporary = tempfile.TemporaryDirectory(dir=ROOT / 'debug')
        root_patch = patch('gui.ROOT', Path(temporary.name))
        root_patch.start()
        root = tk.Tk()
        root.withdraw()
        try:
            app = App(root)
            self.assertEqual(str(app.start_button['state']), 'disabled')
            app.free.set(True)
            app.options_changed()
            self.assertEqual(str(app.start_button['state']), 'disabled')
            app.area.set('Khu cá rô')
            app.options_changed()
            self.assertEqual(str(app.start_button['state']), 'normal')
            app.mission.set(True)
            app.options_changed()
            self.assertFalse(app.free.get())
            self.assertEqual(str(app.controls[1]['state']), 'disabled')
            self.assertEqual(str(app.area_widget['state']), 'disabled')
            with patch('gui.BotWorker') as worker:
                app.start()
                app.start()
                self.assertEqual(worker.call_count, 1)
        finally:
            root.destroy()
            root_patch.stop()
            temporary.cleanup()


if __name__ == '__main__':
    unittest.main()
