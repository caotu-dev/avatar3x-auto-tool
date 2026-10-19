"""Position-only caption dragging, without a nested native move loop."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ui.titlebar import WindowTitlebar


class TitlebarDragTests(unittest.TestCase):
    def titlebar(self):
        bar=WindowTitlebar.__new__(WindowTitlebar)
        bar.root=Mock()
        bar.root.winfo_x.return_value=10
        bar.root.winfo_y.return_value=20
        bar.root.winfo_width.return_value=620
        bar.root.state.return_value='normal'
        bar.winfo_height=Mock(return_value=34)
        bar._drag_origin=None
        bar._api=Mock(return_value=None)
        return bar

    def test_non_windows_move_preserves_pointer_offset(self):
        bar=self.titlebar()
        self.assertEqual(bar.drag(SimpleNamespace(x_root=120,y_root=60)),'break')
        self.assertEqual(bar.drag_move(SimpleNamespace(x_root=270,y_root=160)),'break')
        bar.root.geometry.assert_called_once_with('+160+120')

    def test_windows_move_keeps_size_and_uses_outer_window_position(self):
        bar=self.titlebar()
        api=Mock()
        bar.user32=api
        bar._api.return_value=api
        bar.hwnd=Mock(return_value=123)
        def rect(window, result):
            result._obj.left=8
            result._obj.top=15
            return True
        api.GetWindowRect.side_effect=rect
        bar.drag(SimpleNamespace(x_root=120,y_root=60))
        bar.drag_move(SimpleNamespace(x_root=270,y_root=160))
        api.SetWindowPos.assert_called_once_with(123,None,158,115,0,0,0x0015)
        bar.root.geometry.assert_not_called()
        api.SendMessageW.assert_not_called()
        api.PostMessageW.assert_not_called()

    def test_negative_screen_coordinates_and_mouse_release(self):
        bar=self.titlebar()
        bar.drag(SimpleNamespace(x_root=120,y_root=60))
        bar.drag_move(SimpleNamespace(x_root=-1500,y_root=-40))
        bar.root.geometry.assert_called_once_with('+-1610+-80')
        bar.drag_end()
        bar.drag_move(SimpleNamespace(x_root=500,y_root=500))
        self.assertEqual(bar.root.geometry.call_count,1)
        self.assertIsNone(bar._drag_origin)

    def test_click_without_drag_does_not_move_or_restore_maximized_window(self):
        bar=self.titlebar();bar.root.state.return_value='zoomed'
        bar.drag(SimpleNamespace(x_root=120,y_root=60))
        bar.drag_move(SimpleNamespace(x_root=121,y_root=61))
        bar.root.geometry.assert_not_called()
        bar.root.state.assert_not_called()

    def test_dragging_maximized_window_restores_under_the_pointer(self):
        bar=self.titlebar()
        bar.root.winfo_x.return_value=0;bar.root.winfo_y.return_value=0
        bar.root.winfo_width.side_effect=[2000,1000,1000]
        bar.root.state.side_effect=['zoomed',None]
        bar.drag(SimpleNamespace(x_root=500,y_root=20))
        bar.drag_move(SimpleNamespace(x_root=600,y_root=100))
        bar.root.state.assert_any_call('normal')
        bar.root.geometry.assert_called_once_with('+350+80')
        self.assertEqual(bar._drag_origin,(600,100,350,80,1000))
