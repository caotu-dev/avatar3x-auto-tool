"""Draft-only settings editor. Persistence succeeds before live variables change."""
import tkinter as tk
from tkinter import ttk


class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.overlay = tk.Toplevel(app.root)
        self.overlay.overrideredirect(True)
        self.overlay.configure(background='#0A245E')
        self.overlay.attributes('-alpha', .35)
        self.overlay.geometry(f'{app.root.winfo_width()}x{app.root.winfo_height()}+{app.root.winfo_rootx()}+{app.root.winfo_rooty()}')
        self.overlay.transient(app.root)
        if app.root.attributes('-topmost'):
            self.overlay.attributes('-topmost', True)
            self.attributes('-topmost', True)
        self.transient(self.overlay)
        self.lift(self.overlay)
        self.title('Thiết lập phiên câu')
        self.transient(self.overlay)
        self.resizable(False, False)
        self.configure(background='#FFFFFF')
        self.draft = {key: tk.BooleanVar(self, value=var.get()) for key, var in
                      [('buy', app.buy), ('sell', app.sell), ('midnight_sale', app.midnight), ('auto_resume', app.auto_resume)]}
        self.draft.update({key: tk.BooleanVar(self, value=var.get()) for key, var in app.auto_tickets.items()})
        self.amount = tk.StringVar(self, value=str(app.quantity.get()))
        self.restart_amount = tk.StringVar(self,value=str(app.resume_limit.get()))
        self.error = tk.StringVar(self)
        card = ttk.Frame(self, style='Card.TFrame', padding=16)
        card.pack(fill='both',expand=True)
        ttk.Label(card, text='⚙  Thiết lập phiên câu', style='Section.TLabel', font=('Segoe UI', 18, 'bold')).pack(anchor='w', pady=(0,12))
        groups=ttk.Frame(card,style='Inner.TFrame')
        groups.pack(fill='both',expand=True)
        for column in range(2):groups.columnconfigure(column,weight=1,uniform='settings')
        self.fields = []
        for index,(title, options) in enumerate([('🛒  Mồi & mua sắm', [('Mua mồi khi hết', 'buy')]),
                               ('Vé câu • Chỉ mua vé cần cho khu câu', [('Tự mua vé cá rô — 1.000 xu', 'ca_ro'), ('Tự mua vé cá lóc — 10.000 xu', 'ca_noc'), ('Tự mua vé cá mập — 2 lượng', 'ca_map'), ('Tự mua vé bến tàu — 12.000 xu', 'dock')]),
                               ('Bán cá', [('Bán cá khi về shop', 'sell'), ('Bán cá lúc 23:57 (giờ cố định)', 'midnight_sale')]),
                               ('Khôi phục tiến trình', [('Tự động tiếp tục tiến trình nếu bị lỗi', 'auto_resume')])]):
            group = ttk.Frame(groups, style='Card.TFrame', padding=8)
            group.grid(row=index//2,column=index%2,sticky='nsew',padx=5,pady=5)
            tk.Label(group, text=title, bg='#EAF3FF', fg='#135BFA', font=('Segoe UI',12,'bold'), anchor='w',wraplength=360,padx=8,pady=8).pack(fill='x')
            for label, key in options:
                field = ttk.Checkbutton(group, text=label, variable=self.draft[key])
                field.pack(anchor='w', fill='x')
                self.fields.append(field)
            if options[0][1] == 'buy':
                line = ttk.Frame(group, style='Inner.TFrame')
                line.pack(fill='x', pady=8)
                ttk.Label(line, text='Số mồi mỗi lần mua (1–50)').pack(side='left', padx=(0, 20))
                self.spinner = ttk.Spinbox(line, from_=1, to=50, textvariable=self.amount, width=8)
                self.spinner.pack(side='right')
                self.fields.append(self.spinner)
            if options[0][1] == 'auto_resume':
                ttk.Label(group,text='Số lần tự chạy lại tối đa trong một phiên (1–20)').pack(anchor='w')
                retry=ttk.Spinbox(group,from_=1,to=20,textvariable=self.restart_amount,width=8)
                retry.pack(anchor='w');self.fields.append(retry)
        ttk.Label(card, textvariable=self.error, foreground='#E11D48', wraplength=530).pack(fill='x', pady=8)
        footer = ttk.Frame(self, style='Inner.TFrame',padding=12)
        footer.pack(side='bottom',fill='x')
        ttk.Button(footer, text='✕  Hủy', command=self.cancel).pack(side='left', ipady=8)
        self.save_button = ttk.Button(footer, text='▣  Lưu thay đổi', command=self.save, style='Blue.TButton')
        self.save_button.pack(side='right', ipady=8)
        self.protocol('WM_DELETE_WINDOW', self.cancel)
        self.bind('<Escape>', lambda _: self.cancel())
        self.bind('<Control-Return>', lambda _: self.save())
        self.update_idletasks()
        w = min(1020,app.root.winfo_screenwidth()-40)
        h = min(620,app.root.winfo_screenheight()-90)
        self.geometry(f'{w}x{h}+{app.root.winfo_rootx()+(app.root.winfo_width()-w)//2}+{app.root.winfo_rooty()+(app.root.winfo_height()-h)//2}')
        self.overlay.update_idletasks()
        self.overlay.lift(app.root)
        self.lift(self.overlay)
        self.grab_set()
        self.spinner.focus_set()
        self.refresh_lock()

    def refresh_lock(self):
        previous = getattr(self, 'lock_job', None)
        if previous is not None:
            self.after_cancel(previous)
        locked = self.app.worker is not None
        if locked != getattr(self, '_locked', None):
            self._locked = locked
            for field in self.fields:
                field.configure(state='disabled' if locked else 'normal')
            self.save_button.configure(state='disabled' if locked else 'normal')
            if not locked and self.error.get() == 'Kết thúc phiên câu trước khi thay đổi thiết lập.':
                self.error.set('')
            if locked:
                self.error.set('Kết thúc phiên câu trước khi thay đổi thiết lập.')
        self.lock_job = self.after(500, self.refresh_lock)

    def save(self):
        if self.app.worker is not None:
            return
        try:
            value = int(self.amount.get())
            if not 1 <= value <= 50:
                raise ValueError()
        except ValueError:
            self.error.set('Vui lòng nhập số từ 1 đến 50.')
            self.spinner.focus_set()
            return
        try:
            retries=int(self.restart_amount.get())
            if not 1 <= retries <= 20:raise ValueError()
        except ValueError:
            self.error.set('Số lần tự tiếp tục phải từ 1 đến 20.');return
        settings = {key: var.get() for key, var in self.draft.items()}
        settings['bait_quantity'] = value
        settings['resume_limit'] = retries
        settings['auto_tickets'] = [key for key in self.app.auto_tickets if settings.pop(key)]
        if not self.app.save_preferences(settings):
            self.error.set('Không lưu được thiết lập. Kiểm tra quyền ghi rồi thử lại.')
            return
        self.app.buy.set(settings['buy'])
        self.app.sell.set(settings['sell'])
        self.app.midnight.set(settings['midnight_sale'])
        for key, var in self.app.auto_tickets.items():
            var.set(key in settings['auto_tickets'])
        self.app.quantity.set(value)
        self.app.auto_resume.set(settings['auto_resume'])
        self.app.resume_limit.set(retries)
        self.app.options_changed()
        self.cancel()

    def cancel(self):
        self.after_cancel(self.lock_job)
        self.grab_release()
        self.destroy()
        self.overlay.destroy()
        self.app.settings_popup = None
        self.app.settings_button.focus_set()
