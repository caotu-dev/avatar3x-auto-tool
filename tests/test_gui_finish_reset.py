import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from config.settings import ROOT
from gui import App
from ui.runner import BotWorker, Options


class GuiFinishResetTests(unittest.TestCase):
    def test_reset_removes_saved_custom_progress_without_resetting_inventory_or_game_quest(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('gui.ROOT', Path(folder)), patch('ui.runner.ROOT', Path(folder)):
            runtime = Path(folder) / 'runtime'
            runtime.mkdir()
            progress = runtime / 'custom_mission.json'
            progress.write_text(json.dumps({'plan': [['cua', 3]], 'targets': [{'species': 'cua', 'current': 2, 'required': 3}], 'status': 'STOPPED'}))
            quest = runtime / 'game_quest.json'
            quest.write_text('{"current": 7}')
            inventory = runtime / 'ui_inventory.json'
            inventory.write_text('{"bait_remaining": 12}')
            root = tk.Tk()
            root.withdraw()
            try:
                app = App(root)
                app.tabs.select(2)
                root.update()
                app.custom_list.move('cua', '', 0)
                app.custom_list.set('cua', 'chosen', '☑')
                app.custom_list.set('cua', 'quantity', 3)
                app.options_changed()
                app.reset_custom_targets()
                self.assertFalse(progress.exists())
                self.assertEqual(app.custom_targets(), ())
                self.assertEqual(app.custom_list.get_children()[0], 'ca_ro')
                self.assertTrue(all(int(app.custom_list.set(i, 'quantity')) == 1 for i in app.custom_list.get_children()))
                self.assertEqual(str(app.start_button['state']), 'disabled')
                self.assertEqual(quest.read_text(), '{"current": 7}')
                self.assertEqual(inventory.read_text(), '{"bait_remaining": 12}')
                worker = BotWorker(Options(custom_targets=(('cua', 3),)), lambda *_: None, Mock())
                self.assertEqual(worker.data['targets'][0]['current'], 0)
                app.worker = Mock()
                app.custom_list.set('cua', 'chosen', '☑')
                app.reset_custom_targets()
                self.assertEqual(app.custom_targets(), (('cua', 1),))
            finally:
                root.destroy()

    def test_completion_sound_popup_does_not_block_worker_cleanup(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('gui.ROOT', Path(folder)), patch('gui.winsound.PlaySound') as sound:
            root = tk.Tk()
            root.withdraw()
            try:
                app = App(root)
                app.table.insert('', 'end', values=('Cua', '3/3'))
                app.worker = Mock()
                app.messages.put(('notice', 'Đã hoàn thành mục tiêu; bot đã dừng.'))
                app.messages.put(('done', 'COMPLETE'))
                app.poll()
                sound.assert_called_once()
                self.assertIsNone(app.worker)
                self.assertTrue(app.completion_popup.winfo_exists())
                self.assertEqual(str(app.reset_button['state']), 'normal')
                self.assertEqual(app.status.get(), 'Hoàn thành nhiệm vụ')
                app.completion_popup.destroy()
            finally:
                root.destroy()


if __name__ == '__main__':
    unittest.main()
