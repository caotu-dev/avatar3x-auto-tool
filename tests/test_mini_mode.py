"""Mini presentation preserves the live session and area-based task states."""
import tempfile
import tkinter as tk
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

from gui import App
from fishing.catch import SPECIES
from fishing.quest import AREAS


class MiniModeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug')
        self.patch=patch('gui.ROOT',Path(self.temp.name));self.patch.start()
        self.root=tk.Tk();self.root.withdraw()
        self.app=App(self.root);self.root.update()

    def tearDown(self):
        self.root.destroy();self.patch.stop();self.temp.cleanup()

    def targets(self):
        return [{'species':s,'name':SPECIES[s],'area':AREAS[s],'current':0,'required':10}
                for s in ('ca_ro','ca_chep_vang','cua','ca_ngua')]

    def test_two_unfinished_fish_in_current_area_are_both_active(self):
        data={'targets':self.targets(),'counts':{},'status':'RUNNING','area':'ca_ro'}
        self.app.render_progress(data)
        for species in ('ca_ro','ca_chep_vang'):
            self.assertEqual(self.app.table.item(species,'values')[2],'● Đang tiến hành')
        self.assertEqual(self.app.table.item('cua','values')[2],'○ Đang chờ')
        data['targets'][0]['current']=10
        self.app.render_progress(data)
        self.assertEqual(self.app.table.item('ca_ro','tags'),('completed',))
        self.assertEqual(self.app.table.item('ca_ro','values')[2],'✓ Đã hoàn thành')
        self.app.refresh_progress_status('ERROR')
        self.assertEqual(self.app.table.item('ca_chep_vang','values')[2],'○ Đang chờ')
        self.assertEqual(self.app.table.item('ca_ro','values')[2],'✓ Đã hoàn thành')

    def test_state_updates_when_area_changes_without_count_changes(self):
        data={'targets':self.targets(),'counts':{},'status':'RUNNING','area':'ca_ro'}
        self.app.render_progress(data)
        self.app.render_progress({**data,'area':'ca_noc'})
        self.assertIn('active',self.app.table.item('cua','tags'))
        self.assertEqual(self.app.table.item('ca_ro','tags'),('waiting',))
        self.app.render_progress({**data,'preparing':True})
        self.assertEqual(self.app.table.item('ca_ro','tags'),('waiting',))

    def test_mini_only_shows_progress_and_restores_window_without_worker_action(self):
        self.root.attributes('-alpha',0);self.root.deiconify()
        self.root.geometry('1200x800+40+40');self.root.update()
        original=self.root.geometry()
        worker=Mock();worker.pause.is_set.return_value=False
        self.app.worker=worker
        data={'targets':[{'species':s,'name':n,'current':0,'required':10} for s,n in SPECIES.items()],
              'counts':{},'status':'RUNNING','area':'dock'}
        self.app.render_progress(data)
        self.app.toggle_mini();self.root.update();self.app.resize_workspace();self.root.update()
        self.assertTrue(self.app.mini_mode)
        for widget in (self.app.header,self.app.topbar,self.app.overview,self.app.main_column,self.app.target_toolbar):
            self.assertFalse(widget.winfo_ismapped())
        self.assertTrue(self.app.table.winfo_ismapped())
        self.assertTrue(self.app.restore_button.winfo_ismapped())
        self.assertEqual(len(self.app.table.get_children()),13)
        self.assertEqual(self.app.workspace_scrollbar.winfo_manager(),'')
        self.assertGreaterEqual(self.app.table.yview()[1],.999)
        self.app.toggle_mini();self.root.update()
        # Allow Tk's deferred row-height/layout reconciliation to finish.
        self.root.after(40,self.root.quit);self.root.mainloop()
        self.assertFalse(self.app.mini_mode)
        self.assertEqual(self.root.geometry(),original)
        self.assertFalse(bool(self.root.attributes('-topmost')))
        self.assertTrue(self.app.overview.winfo_ismapped())
        self.assertTrue(self.app.main_column.winfo_ismapped())
        self.assertTrue(self.app.target_toolbar.winfo_ismapped())
        self.assertEqual(self.app.workspace_scrollbar.winfo_manager(),'pack' if self.app.content.winfo_reqheight()>self.app.workspace_canvas.winfo_height()+2 else '',
                         {'canvas':self.app.workspace_canvas.winfo_height(),
                          'content':self.app.content.winfo_reqheight(),
                          'activity':self.app.activity.winfo_reqheight(),
                          'table':self.app.table.winfo_reqheight(),
                          'rowheight':self.root.tk.call('ttk::style','lookup','Treeview','-rowheight'),
                          'toolbar':self.app.target_toolbar.winfo_reqheight()})
        self.assertGreaterEqual(self.app.table.yview()[1],.999)
        worker.stop.set.assert_not_called()
        worker.pause.set.assert_not_called()
        self.assertIs(self.app.worker,worker)

    def test_done_message_clears_active_status_in_mini(self):
        self.app.render_progress({'targets':self.targets(),'counts':{},'status':'RUNNING','area':'ca_ro'})
        self.app.toggle_mini()
        self.app.messages.put(('done','STOPPED'));self.app.poll()
        self.assertEqual(self.app.table.item('ca_ro','tags'),('waiting',))

    def test_caption_controls_keep_windows_resize_and_taskbar_styles(self):
        self.root.attributes('-alpha',0);self.root.deiconify();self.root.update()
        bar=self.app.titlebar
        style=bar.user32.GetWindowLongW(bar.hwnd(),-16)
        self.assertNotEqual(style & 0x00C00000,0x00C00000)  # One caption.
        for bit in (0x00040000,0x00020000,0x00010000,0x00080000):
            self.assertTrue(style & bit)  # Resize, minimize, maximize, system menu.
        self.assertTrue(bar.winfo_ismapped())
        self.assertIs(self.app.mini_button,bar.buttons['mini'])
        bar.buttons['mini'].invoke();self.root.update()
        self.assertTrue(self.app.mini_mode)
        self.assertTrue(bar.winfo_ismapped())
        self.assertEqual(bar.buttons['mini']['text'],'⤢')
        bar.buttons['mini'].invoke();self.root.update()
        self.assertFalse(self.app.mini_mode)

    def test_caption_minimize_maximize_and_close_actions(self):
        self.root.attributes('-alpha',0);self.root.deiconify();self.root.update()
        bar=self.app.titlebar
        bar.buttons['maximize'].invoke();self.root.update()
        self.assertEqual(self.root.state(),'zoomed')
        bar.buttons['maximize'].invoke();self.root.update()
        self.assertEqual(self.root.state(),'normal')
        bar.buttons['minimize'].invoke();self.root.update()
        self.assertEqual(self.root.state(),'iconic')
        self.root.deiconify();self.root.update()
        self.assertNotEqual(bar.user32.GetWindowLongW(bar.hwnd(),-16) & 0x00C00000,0x00C00000)
        with patch.object(self.app,'save_preferences') as save,patch.object(self.root,'destroy') as destroy:
            bar.buttons['close'].invoke()
        save.assert_called_once();destroy.assert_called_once()

    def test_real_tk_drag_events_move_mini_and_full_window_without_changing_session(self):
        self.root.attributes('-alpha',0);self.root.deiconify()
        self.root.geometry('1100x760+80+80');self.root.update()
        failures=[]
        self.root.report_callback_exception=lambda *error:failures.append(error)
        worker=Mock();worker.pause.is_set.return_value=False
        self.app.worker=worker
        for gesture,mini in enumerate((True,False,True,False),1):
            if self.app.mini_mode != mini:self.app.toggle_mini()
            self.root.attributes('-topmost',False)
            self.root.update()
            widget=self.app.titlebar.title
            x,y=self.root.winfo_x(),self.root.winfo_y()
            width,height=self.root.winfo_width(),self.root.winfo_height()
            pointer_x,pointer_y=widget.winfo_rootx()+20,widget.winfo_rooty()+10
            timestamp=gesture*1000
            sizes=[]
            def record_size(event):
                if event.widget is self.root:sizes.append((event.width,event.height))
            binding=self.root.bind('<Configure>',record_size,add='+')
            widget.event_generate('<ButtonPress-1>',x=20,y=10,rootx=pointer_x,rooty=pointer_y,time=timestamp)
            for distance in (10,30,60,90):
                widget.event_generate('<B1-Motion>',x=20,y=10,
                                      rootx=pointer_x+distance,rooty=pointer_y+distance//2,time=timestamp+distance)
                self.root.update()
            widget.event_generate('<ButtonRelease-1>',x=20,y=10,
                                  rootx=pointer_x+90,rooty=pointer_y+45,time=timestamp+100)
            self.root.update()
            self.root.unbind('<Configure>',binding)
            self.assertTrue(all(size==(width,height) for size in sizes),sizes)
            self.assertAlmostEqual(self.root.winfo_x()-x,90,delta=2)
            self.assertAlmostEqual(self.root.winfo_y()-y,45,delta=2)
            self.assertEqual((self.root.winfo_width(),self.root.winfo_height()),(width,height))
            self.assertIsNone(self.app.titlebar._drag_origin)
            self.assertIs(self.app.worker,worker)
        # Tk's positive anchor syntax also supports negative desktop positions.
        self.root.geometry('+-20+40');self.root.update()
        self.assertAlmostEqual(self.root.winfo_x(),-20,delta=2)
        self.assertFalse(failures)
        worker.stop.set.assert_not_called();worker.pause.set.assert_not_called()

    def test_position_only_configure_does_not_relayout_dashboard(self):
        event=SimpleNamespace(widget=self.root,width=1100,height=760)
        self.app.layout_changed(event)
        with patch.object(self.app.header,'configure') as header,patch.object(self.app,'schedule_workspace_resize') as resize:
            for _ in range(100):self.app.layout_changed(event)
        header.assert_not_called();resize.assert_not_called()
