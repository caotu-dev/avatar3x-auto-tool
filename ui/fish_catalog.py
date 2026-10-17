"""Full-height fish catalog with native checkboxes and a Treeview-compatible model API."""
import tkinter as tk
from tkinter import ttk
from ui.theme import asset


class FishCatalog(ttk.Frame):
    def __init__(self, parent, on_change, on_focus):
        super().__init__(parent, style='Inner.TFrame')
        self.rows, self.order, self.selected = {}, [], ()
        self.on_change, self.on_focus = on_change, on_focus
        for i in (1,2,4,5):self.columnconfigure(i,weight=1,uniform='catalog')
        for i,title in enumerate(('Chọn','Loại cá','Khu câu')*2):
            tk.Label(self,text=title,bg='#EAF3FF',fg='#10245C',font=('Segoe UI',10),pady=8).grid(row=0,column=i,sticky='ew')

    def insert(self, parent, index, iid, text='', image=None, values=()):
        chosen, name, quantity, area = values
        frame = ttk.Frame(self, style='Inner.TFrame')
        frame.columnconfigure(0, minsize=64)
        frame.columnconfigure(1, weight=1, uniform='fish')
        frame.columnconfigure(2, weight=1, uniform='fish')
        var = tk.BooleanVar(self, value=chosen == '☑')
        ttk.Style(self).configure('Catalog.TCheckbutton', padding=(0, 4))
        check = ttk.Checkbutton(frame, variable=var, style='Catalog.TCheckbutton', command=lambda: self.toggle(iid))
        check.grid(row=0, column=0, padx=(20, 16))
        # Keep the expanded thirteen-species catalog visible at the dashboard size.
        display_image = image.zoom(3).subsample(4) if image is not None and image.height()>32 else image
        label = ttk.Label(frame, text=name, image=display_image, compound='left')
        label.catalog_image = display_image
        label.grid(row=0, column=1, sticky='ew')
        zone = ttk.Label(frame, text=area, wraplength=180)
        zone.grid(row=0, column=2, sticky='ew', padx=8)
        for w in (frame, label, zone):
            w.bind('<Button-1>', lambda e, key=iid: self.focus_row(key))
        frame.bind('<B1-Motion>', self.drag)
        frame.bind('<Configure>', lambda e: zone.configure(wraplength=max(80, (e.width-64)//2-16)))
        label.bind('<B1-Motion>', self.drag)
        label.configure(takefocus=True)
        label.bind('<FocusIn>', lambda e, key=iid: self.focus_row(key))
        label.bind('<space>', lambda e, key=iid: self.keyboard_toggle(key))
        label.bind('<Up>', lambda e, key=iid: self.navigate(key, -1))
        label.bind('<Down>', lambda e, key=iid: self.navigate(key, 1))
        self.rows[iid] = dict(values=list(values), frame=frame, check=check, var=var, label=label, zone=zone)
        self.order.append(iid)
        self.relayout()

    def relayout(self):
        half=max(1,(len(self.order)+1)//2)
        for i, key in enumerate(self.order):
            self.rows[key]['frame'].grid(row=i%half+1,column=0 if i<half else 3,columnspan=3,sticky='ew',pady=(0,1),padx=(0,6) if i<half else (6,0))

    def keyboard_toggle(self, key):
        if str(self.rows[key]['check']['state']) != 'disabled':
            self.rows[key]['var'].set(not self.rows[key]['var'].get())
            self.toggle(key)
        return 'break'

    def toggle(self, key):
        if str(self.rows[key]['check']['state']) == 'disabled':
            return 'break'
        self.focus_row(key)
        # Keyboard toggles explicitly; checkbox invokes after its variable changes.
        self.rows[key]['values'][0] = '☑' if self.rows[key]['var'].get() else '□'
        self.on_change()
        return 'break'

    def focus_row(self, key):
        self.selected = (key,)
        for item, row in self.rows.items():
            row['label'].configure(style='SelectedFish.TLabel' if item == key else 'TLabel')
        self.on_focus()

    def navigate(self, key, delta):
        i = max(0, min(len(self.order)-1, self.order.index(key)+delta))
        self.rows[self.order[i]]['label'].focus_set()
        return 'break'

    def drag(self, event):
        if not self.selected or str(self.rows[self.selected[0]]['check']['state']) == 'disabled':
            return
        y = event.y_root
        for key in self.order:
            frame = self.rows[key]['frame']
            if (frame.winfo_rooty() <= y < frame.winfo_rooty()+frame.winfo_height()
                    and frame.winfo_rootx()<=event.x_root<frame.winfo_rootx()+frame.winfo_width()):
                self.move(self.selected[0], '', self.index(key))
                self.on_change()
                break

    def set(self, key, column, value=None):
        index = ('chosen', 'name', 'quantity', 'area').index(column)
        if value is None:
            return str(self.rows[key]['values'][index])
        self.rows[key]['values'][index] = value
        if column == 'chosen':
            self.rows[key]['var'].set(value == '☑')

    def exists(self, key): return key in self.rows
    def get_children(self): return tuple(self.order)
    def selection(self): return self.selected
    def selection_set(self, key): self.focus_row(key[0] if isinstance(key, (tuple,list)) else key)
    def selection_remove(self, *keys): self.selected = (); self.on_focus()
    def index(self, key): return self.order.index(key)
    def move(self, key, parent, index):
        self.order.remove(key)
        self.order.insert(len(self.order) if index == 'end' else int(index), key)
        self.relayout()
    def yview_moveto(self, value): pass
    def configure(self, **kwargs):
        kwargs.pop('height', None)
        if kwargs: super().configure(**kwargs)
    def lock(self, locked):
        for row in self.rows.values(): row['check'].configure(state='disabled' if locked else 'normal')
