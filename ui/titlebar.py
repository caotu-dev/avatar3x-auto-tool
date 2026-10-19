"""Application caption controls, retaining the Windows resize/taskbar frame.

Only this application's own HWND is changed; no global hooks or subprocesses.
"""
import ctypes
import sys
import tkinter as tk
from ctypes import wintypes
from ui.theme import asset


class WindowTitlebar(tk.Frame):
    def __init__(self, root, mini, close):
        super().__init__(root, background='#F3F6FA', height=43)
        self.root = root
        self.user32 = None
        self._drag_origin = None
        self.pack_propagate(False)
        self.icon = tk.Label(self, image=asset(root,'app_icon_small'),
                             background='#F3F6FA', padx=6)
        self.icon.pack(side='left',fill='y')
        self.title = tk.Label(self, text=root.title(), background='#F3F6FA',
                              foreground='#263653', font=('Segoe UI', 10), padx=4)
        self.title.pack(side='left', fill='y')
        actions = tk.Frame(self, background='#F3F6FA')
        actions.pack(side='right', fill='y')
        self.buttons = {}
        for key, glyph, command in (
                ('mini', '▣', mini), ('minimize', '—', self.minimize),
                ('maximize', '□', self.maximize), ('close', '×', close)):
            button = tk.Button(actions, text=glyph, command=command, width=3,
                               font=('Segoe UI', 12), background='#F3F6FA',
                               foreground='#263653', activebackground='#DFE8F5',
                               relief='flat', borderwidth=0, highlightthickness=0,
                               takefocus=True, padx=4, pady=0)
            button.pack(side='left', fill='y')
            button.bind('<Enter>', lambda _, b=button, k=key: b.configure(
                background='#E5484D' if k=='close' else '#DFE8F5',
                foreground='white' if k=='close' else '#1459E8'))
            button.bind('<Leave>', lambda _, b=button: b.configure(
                background='#F3F6FA', foreground='#263653'))
            self.buttons[key] = button
        for widget in (self, self.title, self.icon):
            widget.bind('<ButtonPress-1>', self.drag)
            widget.bind('<B1-Motion>', self.drag_move)
            widget.bind('<ButtonRelease-1>', self.drag_end)
            widget.bind('<Double-Button-1>', lambda _: self.maximize())
        root.bind('<Map>', self.on_map, add='+')
        root.bind('<Configure>', self.on_configure, add='+')
        root.after_idle(self.apply_frame)

    def _api(self):
        if self.user32 is None and sys.platform == 'win32':
            api = ctypes.WinDLL('user32', use_last_error=True)
            api.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            api.GetAncestor.restype = wintypes.HWND
            api.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
            api.GetWindowLongW.restype = wintypes.LONG
            api.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
            api.SetWindowLongW.restype = wintypes.LONG
            api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            api.SetWindowPos.restype = wintypes.BOOL
            api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            api.GetWindowRect.restype = wintypes.BOOL
            self.user32 = api
        return self.user32

    def hwnd(self):
        return self._api().GetAncestor(self.root.winfo_id(), 2)

    def apply_frame(self):
        if not self.root.winfo_exists() or self._api() is None:
            return
        window = self.hwnd()
        style = self.user32.GetWindowLongW(window, -16)
        # Remove only the native caption. Keep WS_THICKFRAME, system menu,
        # minimize/maximize boxes and Tk's existing taskbar ownership.
        if style & 0x00C00000 == 0x00C00000:
            # WS_CAPTION is WS_BORDER | WS_DLGFRAME. Keep the thin border so
            # Tk's client-size bookkeeping does not drift by 2 px on restore.
            self.user32.SetWindowLongW(window, -16, style & ~0x00400000)
            self.user32.SetWindowPos(window, None, 0, 0, 0, 0, 0x0037)

    def on_map(self, event):
        if event.widget is self.root:
            self.apply_frame()

    def on_configure(self, event):
        if event.widget is self.root:
            title=self.root.title()
            if self.title['text'] != title:
                self.title.configure(text=title)
            glyph='❐' if self.root.state()=='zoomed' else '□'
            if self.buttons['maximize']['text'] != glyph:
                self.buttons['maximize'].configure(text=glyph)

    def set_mini(self, enabled):
        self.title.configure(text=self.root.title())
        self.buttons['mini'].configure(text='⤢' if enabled else '▣')

    def minimize(self):
        self.root.iconify()

    def maximize(self):
        self._drag_origin = None
        self.root.state('normal' if self.root.state()=='zoomed' else 'zoomed')
        self.apply_frame()

    def drag(self, event):
        x,y=self.window_position()
        self._drag_origin = (event.x_root,event.y_root,x,y,self.root.winfo_width())
        return 'break'

    def window_position(self):
        if self._api() is not None:
            rect=wintypes.RECT()
            if self.user32.GetWindowRect(self.hwnd(),ctypes.byref(rect)):
                return rect.left,rect.top
        return self.root.winfo_x(),self.root.winfo_y()

    def move_window(self, x, y):
        if self._api() is not None:
            # A position-only native move preserves the actual client size.
            # wm geometry recalculates the removed caption on every motion,
            # alternating client heights and repainting exposed black/white
            # strips. Keep DWM's normal copy/composition and never enter the
            # nested SendMessage/SC_MOVE loop (unsafe inside a Tk callback).
            if self.user32.SetWindowPos(self.hwnd(),None,x,y,0,0,0x0015):
                return  # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
        self.root.geometry(f'+{x}+{y}')

    def drag_move(self, event):
        if self._drag_origin is None:
            return
        start_x,start_y,x,y,width=self._drag_origin
        dx,dy=event.x_root-start_x,event.y_root-start_y
        if abs(dx)+abs(dy)<3:
            return 'break'
        if self.root.state()=='zoomed':
            fraction=max(0,min(1,(start_x-x)/max(1,width)))
            self.root.state('normal')
            self.root.update_idletasks()
            x=event.x_root-round(self.root.winfo_width()*fraction)
            y=event.y_root-min(self.winfo_height(),max(0,start_y-y))
            self._drag_origin=(event.x_root,event.y_root,x,y,self.root.winfo_width())
        else:
            x,y=x+dx,y+dy
        self.move_window(x,y)
        return 'break'

    def drag_end(self, event=None):
        self._drag_origin=None
        return 'break'
