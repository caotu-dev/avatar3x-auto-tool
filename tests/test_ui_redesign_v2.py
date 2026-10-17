"""V2 state/persistence/layout acceptance. No game input or real runtime writes."""
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from gui import App

class RedesignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug')
        self.folder = Path(self.temp.name)
        self.patch = patch('gui.ROOT', self.folder)
        self.patch.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root)
        self.root.update()
    def tearDown(self):
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        self.root.destroy()
        self.patch.stop()
        self.temp.cleanup()
    def test_modal_cancel_and_invalid_input_never_commit(self):
        self.app.show_settings()
        dialog = self.app.settings_popup
        dialog.draft['buy'].set(True)
        for invalid in ('0', '51', '', 'abc', '1.5'):
            dialog.amount.set(invalid)
            dialog.save()
            self.assertTrue(dialog.winfo_exists())
            self.assertEqual(self.app.quantity.get(), 50)
            self.assertFalse(self.app.buy.get())
            self.assertFalse((self.folder/'runtime/ui_preferences.json').exists())
        dialog.cancel()
        self.app.show_settings()
        self.assertEqual(self.app.settings_popup.amount.get(), '50')
        self.assertFalse(self.app.settings_popup.draft['buy'].get())
        self.app.settings_popup.cancel()
    def test_modal_save_commits_all_fields_and_reopens(self):
        self.app.show_settings()
        dialog = self.app.settings_popup
        dialog.amount.set('17'); dialog.draft['buy'].set(True)
        dialog.draft['sell'].set(True); dialog.draft['midnight_sale'].set(False)
        dialog.save()
        saved=json.loads((self.folder/'runtime/ui_preferences.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['bait_quantity'],17)
        self.assertTrue(saved['buy']); self.assertTrue(saved['sell'])
        self.assertFalse(saved['midnight_sale'])
        self.assertEqual(self.app.quantity.get(),17)
        self.app.show_settings()
        self.assertEqual(self.app.settings_popup.amount.get(),'17')
        self.app.settings_popup.cancel()
    def test_failed_save_preserves_draft_and_live_values(self):
        self.app.show_settings(); dialog=self.app.settings_popup
        dialog.amount.set('9'); dialog.draft['buy'].set(True)
        with patch.object(Path,'replace',side_effect=OSError('locked')):
            dialog.save()
        self.assertTrue(dialog.winfo_exists())
        self.assertEqual(dialog.amount.get(),'9')
        self.assertEqual(self.app.quantity.get(),50)
        self.assertFalse(self.app.buy.get())
        dialog.cancel()
    def test_running_modal_locks_and_recovers_after_stop(self):
        self.app.worker=object(); self.app.show_settings()
        dialog=self.app.settings_popup
        self.assertTrue(all(str(w['state'])=='disabled' for w in dialog.fields))
        dialog.amount.set('8');dialog.save()
        self.assertEqual(self.app.quantity.get(),50)
        self.app.worker=None;dialog.refresh_lock()
        self.assertTrue(all(str(w['state'])=='normal' for w in dialog.fields))
        dialog.cancel()
    def test_catalog_focus_checkbox_and_target_actions_are_separate(self):
        self.app.tabs.select(2);self.root.update()
        catalog=self.app.custom_list
        catalog.focus_row('cua')
        self.assertEqual(self.app.custom_targets(),())
        catalog.keyboard_toggle('cua')
        self.assertEqual(self.app.custom_targets(),(('cua',1),))
        self.app.target_quantity.set(13);self.app.set_target_quantity()
        self.assertEqual(self.app.custom_targets(),(('cua',13),))
        self.assertEqual(self.app.table.item('cua','values')[1],'0/13')
        self.app.move_target(-1)
        self.assertEqual(self.app.table.get_children(),('cua',))
        self.assertEqual(self.app.custom_targets(),(('cua',13),))
        self.app.worker=object();catalog.lock(True)
        catalog.keyboard_toggle('cua')
        self.assertEqual(self.app.custom_targets(),(('cua',13),))
        self.app.worker=None
    def test_poll_keeps_one_timer_and_disposes_on_destroy(self):
        self.app.poll()
        first = self.app.poll_job
        self.app.poll()
        jobs = self.root.tk.call('after', 'info')
        self.assertNotIn(first, jobs)
        self.assertIn(self.app.poll_job, jobs)
        scripts = [self.root.tk.call('after', 'info', job)[0] for job in jobs]
        self.assertEqual(sum(str(script).endswith('poll') for script in scripts), 1)

    def test_full_progress_rows_and_unknown_tickets(self):
        from fishing.catch import SPECIES
        data={'counts':dict.fromkeys(SPECIES,2),'targets':[]}
        self.app.render_progress(data)
        self.assertEqual(int(self.app.table['height']),len(SPECIES))
        self.assertEqual(self.app.table['yscrollcommand'],'')
        self.assertTrue(all(v.get()=='Chưa xác định' for v in self.app.ticket_values.values()))
        self.app.table.selection_set('cua');self.app.focus_progress_target()
        self.assertEqual(self.app.custom_list.selection(),('cua',))
        self.app.target_quantity.set(8)
        self.app.render_progress(data)
        self.assertEqual(self.app.target_quantity.get(),8)
        self.assertEqual(self.app.table.selection(),('cua',))

if __name__=='__main__':unittest.main()

