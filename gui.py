"""Khởi động giao diện: python gui.py."""
import os
from config.native_runtime import configure_native_runtime
configure_native_runtime()

import queue
import threading
import msvcrt
import sys
import json
import time
import winsound
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox

from config.settings import ROOT
from fishing.catch import SPECIES
from ui.runner import AREAS_UI, Options, BotWorker
from ui.theme import apply_theme, token, font, banner, asset, TILE_COLORS
from ui.branding import APP_NAME, APP_VERSION, apply_identity
from ui.mission_progress import MissionProgress


class App:
    def __init__(self, root):
        self.root, self.worker = root, None
        self.messages = queue.Queue()
        self.inventory_cache = {}  # Fast in-memory layer over runtime/character_state.json.
        self.timer_started = None
        self.mini_mode = False
        self.elapsed = tk.StringVar(value='00:00:00')
        self.quantity = tk.IntVar(value=50)
        self.auto_resume = tk.BooleanVar(value=False)
        self.resume_limit = tk.IntVar(value=3)
        self.midnight = tk.BooleanVar(value=True)
        apply_identity(root)
        root.geometry(f'{min(1536, root.winfo_screenwidth()-32)}x{min(1024, root.winfo_screenheight()-50)}')
        root.minsize(1024, 720)
        tkfont.nametofont('TkDefaultFont').configure(family='Segoe UI', size=10)
        apply_theme(root)
        from ui.titlebar import WindowTitlebar
        self.titlebar = WindowTitlebar(root, self.toggle_mini, self.close)
        self.titlebar.pack(fill='x')
        self.header = banner(root)
        self.header.pack(fill='x')
        self.status = tk.StringVar(value='Sẵn sàng • Chọn chế độ để bắt đầu')
        self.mission, self.free, self.buy, self.sell = [tk.BooleanVar() for _ in range(4)]
        self.controls = []
        self.settings_popup = None
        self.preparation_popup = None
        self.auto_tickets = {key: tk.BooleanVar(value=False) for key in ("ca_ro", "ca_noc", "ca_map", "dock")} 
        top = self.topbar = ttk.Frame(root,padding=(9,10))
        top.pack(fill='x')
        self.settings_button = ttk.Button(top, text=' Thiết lập', image=asset(root, 'panel_settings_gear'), compound='left', command=self.show_settings, style='Nav.TButton')
        self.log_folder_button = ttk.Button(top, text=' Mở thư mục log', image=asset(root, 'button_folder'), compound='left', command=self.open_logs, style='Folder.Nav.TButton')
        top.rowconfigure(0, minsize=54)
        for i,weight in enumerate((302,305,303,309,296)):top.columnconfigure(i,weight=weight,uniform='nav')
        self.mini_button = self.titlebar.buttons['mini']
        self.settings_button.grid(row=0,column=0,sticky='nsew',padx=5)
        self.log_folder_button.grid(row=0,column=2,sticky='nsew',padx=5)
        self.start_reason = tk.StringVar(value='Chọn chế độ để bắt đầu.')
        body = self.body = ttk.Frame(root, padding=(16,10,14,40))
        body.pack(fill='both', expand=True)
        self.workspace = body
        self.workspace_canvas = tk.Canvas(body, background=token('color.background.app'), highlightthickness=0)
        workspace_scroll = self.workspace_scrollbar = ttk.Scrollbar(body, command=self.workspace_canvas.yview)
        workspace_scroll.pack(side='right', fill='y')
        self.workspace_canvas.pack(fill='both', expand=True)
        self.workspace_canvas.configure(yscrollcommand=workspace_scroll.set)
        content = self.content = ttk.Frame(self.workspace_canvas)
        self.workspace_window = self.workspace_canvas.create_window(0, 0, window=content, anchor='nw')
        self.workspace_canvas.bind('<Configure>', self.schedule_workspace_resize)
        content.bind('<Configure>', self.schedule_workspace_resize)
        self.main_column = ttk.Frame(content)
        self.main_column.grid(row=0, column=0, sticky='nsew', padx=(0, 7))
        self.activity = ttk.Frame(content)
        self.activity.grid(row=0, column=1, sticky='nsew', padx=7)
        self.activity.columnconfigure(0, weight=1)
        self.activity.rowconfigure(0,weight=1)
        content.rowconfigure(0,weight=1)
        self.overview = ttk.Frame(content)
        self.overview.grid(row=0, column=2, sticky='nsew', padx=(7, 0))
        self.mission_popup = tk.Toplevel(root)
        self.mission_popup.withdraw()
        self.mission_popup.title('Chọn chế độ & nhiệm vụ')
        self.mission_popup.transient(root)
        self.mission_popup.protocol('WM_DELETE_WINDOW', lambda: self.close_missions(False))
        self.mission_popup.bind('<Escape>', lambda _: self.close_missions(False))
        self.mode_bar = ttk.Frame(self.mission_popup)
        self.mode_bar.pack(fill='x', pady=(0, 12))
        self.mode_buttons = []
        self.tabs = ttk.Notebook(self.mission_popup, style='Workspace.TNotebook')
        self.tabs.pack(fill='x', pady=(0, token('sizingPx.rowGap')))
        quest_tab, free_tab, custom_tab = [ttk.Frame(self.tabs, style='Card.TFrame', padding=12) for _ in range(3)]
        for tab, title, icon in [(quest_tab, 'Nhiệm vụ game', 'tab_gamepad'), (free_tab, 'Câu tự do', 'tab_hook'), (custom_tab, 'Tự đặt mục tiêu', 'tab_target')]:
            self.tabs.add(tab, text=' '+title, image=asset(root, icon), compound='left')
            index = len(self.mode_buttons)
            self.mode_bar.columnconfigure(index, weight=1, uniform='mode')
            button = ttk.Button(self.mode_bar, text=title, style='Compact.TButton', command=lambda i=index: self.tabs.select(i))
            button.grid(row=0, column=index, sticky='nsew', padx=2)
            self.mode_buttons.append(button)
            if index == 2:
                ttk.Label(tab, text=' '+title, image=asset(root, icon), compound='left', style='Section.TLabel').pack(anchor='w', pady=(4, 12))
        mode_controls = []
        for parent, label, variable in [(quest_tab, 'Tự động đọc và làm nhiệm vụ hiện tại', self.mission),
                                         (free_tab, 'Câu tự do', self.free)]:
            widget = ttk.Checkbutton(parent, text=label, variable=variable, command=self.options_changed)
            widget.pack(anchor='w')
            mode_controls.append(widget)
        self.controls = mode_controls + self.controls
        ttk.Label(quest_tab, text='Tiến độ được đọc từ game và xác minh lại trước khi hoàn thành.', style='Card.TLabel', wraplength=430).pack(anchor='w')
        ttk.Label(free_tab, text='Khu câu tự do', style='Card.TLabel').pack(anchor='w')
        self.area = tk.StringVar()
        self.area_widget = ttk.Combobox(free_tab, textvariable=self.area, values=list(AREAS_UI), state='disabled')
        self.area_widget.pack(fill='x', pady=4)
        self.area_widget.bind('<<ComboboxSelected>>', lambda _: self.options_changed())
        ttk.Label(custom_tab, text='Chọn cá tại đây. Đặt số lượng và sắp xếp trong bảng Tiến trình.', style='Card.TLabel', wraplength=430).pack(anchor='w')
        list_frame = ttk.Frame(custom_tab, style='Inner.TFrame')
        list_frame.pack(fill='x', pady=6)
        from ui.fish_catalog import FishCatalog
        self.custom_list = FishCatalog(list_frame, self.catalog_changed, self.update_target_actions)
        from fishing.quest import AREAS
        for species, name in SPECIES.items():
            if species in AREAS:
                area_name = next(k for k, v in AREAS_UI.items() if v == AREAS[species])
                self.custom_list.insert('', 'end', iid=species, text=name, image=asset(root, 'fish_'+species), values=('□', name, 1, area_name))
        self.custom_list.pack(fill='x', expand=True)
        self.tabs.bind('<<NotebookTabChanged>>', self.mode_changed)
        footer = self.mission_footer = ttk.Frame(self.mission_popup, padding=12)
        # Reserve the action row before the variable-height catalog. Otherwise
        # the selected tab can consume the popup and hide Save/Cancel.
        footer.pack(side='bottom', fill='x', before=self.mode_bar)
        ttk.Button(footer, text='Hủy', command=lambda: self.close_missions(False)).pack(side='left')
        ttk.Button(footer, text='Lưu nhiệm vụ', style='Blue.TButton', command=lambda: self.close_missions(True)).pack(side='right')
        self.missions_button = ttk.Button(top, text=' Chọn nhiệm vụ', image=asset(root,'tab_target'), compound='left', command=self.show_missions, style='Nav.TButton')
        self.missions_button.grid(row=0,column=1,sticky='nsew',padx=5)
        for button in (self.settings_button,self.missions_button,self.log_folder_button):
            arrow = ttk.Label(button,text='›',foreground='#76A8F4',background='#F7FBFF',font=('Segoe UI',-26))
            arrow.place(relx=1,x=-22,rely=.5,anchor='center')
            arrow.bind('<Button-1>',lambda event, target=button: target.invoke())
        summary = self.summary_card = ttk.Frame(self.overview, style='Card.TFrame', padding=10)
        summary.pack(fill='x', pady=(0,6))
        ttk.Label(summary, padding=(3,0,0,0), text=' Tổng quan phiên câu', image=asset(root, 'section_overview_stats'), compound='left', style='Section.TLabel').pack(anchor='w')
        self.metric_values = {key: tk.StringVar(value='0') for key in ('casts', 'bites', 'misses', 'bait_purchased')}
        self.metric_tiles = []
        tiles = ttk.Frame(summary, style='Inner.TFrame')
        tiles.pack(fill='x', pady=(11,0))
        for index, (key, title, color) in enumerate([('casts', 'Quăng', 'castBg'), ('bites', 'Cắn câu', 'biteBg'), ('misses', 'Trật', 'missBg'), ('bait_purchased', 'Mồi mua', 'baitBg')]):
            tiles.columnconfigure(index % 2, weight=1, uniform='metric')
            tile = ttk.Frame(tiles, style=color+'.TFrame', padding=(12, 6))
            self.metric_tiles.append(tile)
            tile.grid(row=index // 2, column=index % 2, sticky='ew', padx=4, pady=(0,9) if index<2 else 0)
            icon = ('metric_cast', 'metric_bite', 'metric_miss', 'overview_cart_orange')[index]
            tk.Label(tile, image=asset(root, icon), bg=token('color.metric.'+color)).pack(side='left', padx=(0, 8))
            tk.Label(tile,text=title,bg=token('color.metric.'+color),fg=token('color.text.primary'),font=font('body')).pack(side='left',pady=(2,0))
            tk.Label(tile,textvariable=self.metric_values[key],bg=token('color.metric.'+color),fg=token('color.text.primary'),font=font('metric',True)).pack(side='right',padx=(0,7),pady=(0,2))
        self.stock_values = {key: tk.StringVar(value='Chưa xác định') for key in ('ecological', 'dock')}
        self.stock_tiles = []
        metadata = ttk.Frame(summary, style='Inner.TFrame')
        metadata.pack(fill='x', pady=(8, 0))
        for index, (key, title, icon) in enumerate([('ecological', 'Sinh thái', 'overview_bug_gray'), ('dock', 'Bến tàu', 'overview_boat_teal')]):
            metadata.columnconfigure(index, weight=1, uniform='stock')
            box = ttk.Frame(metadata, style=key+'.TFrame', padding=(12, 8))
            self.stock_tiles.append(box)
            box.grid(row=0, column=index, sticky='ew', padx=4, pady=(2,0))
            tk.Label(box, image=asset(root, icon), bg=TILE_COLORS[key]).pack(side='left', padx=(0,14 if index==0 else 12))
            label = tk.Frame(box, bg=TILE_COLORS[key])
            label.pack(side='left',pady=(2,0))
            tk.Label(label, text=title, bg=TILE_COLORS[key], fg=token('color.text.primary'), font=font('body')).pack(anchor='w')
            tk.Label(label, textvariable=self.stock_values[key], bg=TILE_COLORS[key], fg=token('color.text.primary'), font=font('body'),padx=6 if key=='ecological' else 0, wraplength=170).pack(anchor='w',pady=(3,0))
            box.bind('<Configure>', lambda e, target=label: [child.configure(wraplength=max(65,e.width-76)) for child in target.winfo_children()])
        self.currency_images={key:asset(root,'currency_'+key) for key in ('coins','gold')}
        self.ticket_images={key:asset(root,'ticket_'+key) for key in ('ca_ro','ca_map','ca_noc','dock')}
        self.wallet_values = {key: tk.StringVar(value='Chưa xác định') for key in ('coins', 'gold')}
        for index,(key, label) in enumerate([('coins', 'Xu'), ('gold', 'Lượng')]):
            line = ttk.Frame(top, style='Nav.Card.TFrame',padding=(15,3))
            line.grid(row=0,column=3+index,sticky='nsew',padx=5)
            ttk.Label(line, background='#F7FBFF', font=(token('typography.fontFamily'),12,'bold'), text=(' ' if key=='gold' else '  ')+label + ':  ', image=self.currency_images[key], compound='left').pack(side='left')
            ttk.Label(line, textvariable=self.wallet_values[key],background='#F7FBFF',font=(token('typography.fontFamily'),11,'bold'),wraplength=145).pack(side='left')
            if key=='gold':
                ttk.Label(line,text='›',foreground='#76A8F4',background='#F7FBFF',font=('Segoe UI',-26)).place(relx=1,x=-22,rely=.5,anchor='center')
        tickets = self.ticket_card = ttk.Frame(self.overview, style='Card.TFrame', padding=10)
        tickets.pack(fill='x', pady=(11,7))
        ttk.Label(tickets, padding=(2,0,0,0), text=' Vé câu (hiệu lực)', image=asset(root,'section_tickets'), compound='left', style='Section.TLabel').pack(anchor='w', pady=(0, 9))
        ticket_grid = ttk.Frame(tickets, style='Inner.TFrame')
        ticket_grid.pack(fill='x')
        self.ticket_values = {}
        self.ticket_tiles = []
        for i, title in enumerate(('Vé câu cá rô', 'Vé câu cá mập', 'Vé câu cá lóc', 'Vé câu bến tàu')):
            ticket_grid.columnconfigure(i % 2, weight=1, uniform='ticket')
            color_key = ('ticket_ro','ticket_map','ticket_loc','ticket_dock')[i]
            color = TILE_COLORS[color_key]
            tile = ttk.Frame(ticket_grid, style=color_key+'.TFrame', padding=(10,6))
            self.ticket_tiles.append(tile)
            tile.grid(row=i // 2, column=i % 2, sticky='nsew', padx=4, pady=(4,6) if i<2 else (4,2))
            ttk.Label(tile, image=self.ticket_images[('ca_ro','ca_map','ca_noc','dock')[i]], background=color).pack(side='left', anchor='n', padx=(0,5),pady=(3,0))
            detail = tk.Frame(tile, bg=color)
            detail.pack(side='left', fill='both', expand=True)
            name_label = tk.Label(detail, text=title, bg=color, fg=token('color.text.primary'), font=font('body',True), anchor='w', justify='left')
            name_label.pack(anchor='w',pady=(5,0))
            value = self.ticket_values[title] = tk.StringVar(value='Chưa xác định')
            value_label = tk.Label(detail, textvariable=value, bg=color, fg=token('color.text.secondary'), justify='left', anchor='nw', height=2, font=font('caption'))
            value_label.pack(anchor='w', pady=(1,0))
            tile.bind('<Configure>', lambda e, a=name_label, b=value_label: (a.configure(wraplength=max(75,e.width-80)), b.configure(wraplength=max(75,e.width-80))))

        self.overview.bind('<Configure>', self.resize_overview)
        catches = self.progress_card = ttk.Frame(self.activity, style='Card.TFrame', padding=(15,12,16,18))
        catches.grid(row=0, column=0, sticky='nsew')
        progress_header = ttk.Frame(catches, style='Inner.TFrame')
        progress_header.pack(fill='x', pady=(0, 12))
        self.restore_button = ttk.Button(progress_header, text='⤢  Mở rộng',
                                         style='Compact.TButton', command=self.toggle_mini)
        ttk.Label(progress_header, text=' Tiến độ nhiệm vụ', image=asset(root, 'section_table_fish'), compound='left', style='Section.TLabel').pack(side='left')
        # Reserve footer space before the expanding table: it never overlays rows.
        self.mission_progress = MissionProgress(catches)
        self.mission_progress.pack(side='bottom', fill='x', padx=(0,1), pady=(8, 0))
        table_frame = ttk.Frame(catches, style='Inner.TFrame')
        table_frame.pack(fill='both', expand=True)
        self.table_frame = table_frame
        self.table = ttk.Treeview(table_frame, columns=('name', 'progress', 'status'), show='tree headings', displaycolumns=('progress','status'), height=5)
        self.table.heading('#0', text='Loại cá')
        self.table.column('#0', width=180, minwidth=105)
        self.table.heading('name', text='Loại cá')
        self.table.heading('progress', text='Số lượng / Tiến độ')
        self.table.column('name', width=180, anchor='w')
        self.table.column('progress', width=176, minwidth=65, anchor='center')
        self.table.heading('status', text='Trạng thái',anchor='w')
        self.table.column('status', width=160, minwidth=122, anchor='w')
        self.table.tag_configure('active_even',background='#F3F9FF')
        self.table.tag_configure('completed', background='#EAF8EF', foreground='#236D3A')
        self.table.tag_configure('active', background='#EAF3FF', foreground='#1267F5')
        self.table.tag_configure('waiting', foreground='#5272A9')
        self.table.pack(side='left',fill='both', expand=True)
        self.table_scrollbar = ttk.Scrollbar(table_frame, command=self.table.yview)
        self.table_horizontal = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        self.table.configure(xscrollcommand=self.table_horizontal.set)
        self.table.configure(yscrollcommand=self.table_scrollbar.set)
        self.table.bind('<<TreeviewSelect>>', self.focus_progress_target)
        self.table.bind('<ButtonPress-1>', lambda e: setattr(self,'drag_progress',self.table.identify_row(e.y)))
        self.table.bind('<B1-Motion>', self.drag_progress_target)
        self.table.bind('<Configure>', self.update_table_scrollbar, add='+')
        row = self.target_toolbar = ttk.Frame(catches, style='Inner.TFrame')
        row.pack(fill='x')
        self.target_quantity = tk.IntVar(value=1)
        ttk.Spinbox(row, from_=1, to=9999, textvariable=self.target_quantity, width=4).pack(side='left')
        ttk.Button(row, style='Compact.TButton', text='Đặt số lượng', command=self.set_target_quantity).pack(side='left', padx=6)
        ttk.Button(row, style='Compact.TButton', width=2, text='↑', command=lambda: self.move_target(-1)).pack(side='left')
        ttk.Button(row, style='Compact.TButton', width=2, text='↓', command=lambda: self.move_target(1)).pack(side='left', padx=6)
        self.reset_button = ttk.Button(row, style='Compact.TButton', text='Reset mục tiêu', command=self.reset_custom_targets)
        self.reset_button.pack(side='left')
        self.target_controls = row.winfo_children()
        self.empty_results = ttk.Frame(self.table, style='Inner.TFrame', padding=16)
        ttk.Label(self.empty_results, image=asset(root, 'empty_fish')).pack(pady=8)
        ttk.Label(self.empty_results, text='Chưa có dữ liệu.', foreground=token('color.text.muted'), font=font('bodyLarge')).pack(pady=4)
        ttk.Label(self.empty_results, text='Bắt đầu để tự động ghi nhận cá đã câu.', wraplength=320, foreground=token('color.text.muted')).pack()
        self.empty_results.place(relx=.5, rely=.55, anchor='center')
        self.session_controls=ttk.Frame(self.overview,style='Card.TFrame',padding=(11,10,7,10))
        self.session_controls.pack(fill='x',pady=(4,0))
        self.control_images=[asset(root,key) for key in ('button_play','button_pause','button_stop')]
        self.start_button=ttk.Button(self.session_controls,text=' Bắt đầu',image=(self.control_images[0],'disabled',asset(root,'button_play_disabled')),compound='left',command=self.start,state='disabled',style='Accent.TButton')
        self.pause_button=ttk.Button(self.session_controls,text=' Tạm dừng',image=(self.control_images[1],'disabled',asset(root,'button_pause_disabled')),compound='left',command=self.pause,state='disabled')
        self.stop_button=ttk.Button(self.session_controls,text=' Kết thúc',image=(self.control_images[2],'disabled',asset(root,'button_stop_disabled')),compound='left',command=self.stop,state='disabled',style='Danger.TButton')
        for index,button in enumerate((self.start_button,self.pause_button,self.stop_button)):
            self.session_controls.rowconfigure(index//2,minsize=66 if index<2 else 62)
            self.session_controls.columnconfigure(index%2,weight=262 if index%2==0 else 250,uniform='control')
            button.grid(row=index//2,column=index%2,sticky='nsew',padx=(3,5) if index%2==0 else (6,3),pady=(1,9) if index<2 else (1,2))
        clock=self.clock=ttk.Frame(self.session_controls,style='stock.TFrame',padding=(8,4))
        clock.grid(row=1,column=1,sticky='nsew',padx=(6,3),pady=(1,2))
        ttk.Label(clock,image=asset(root,'clock'),background=token('color.background.timer')).pack(side='left',padx=(0,6))
        ttk.Label(clock,textvariable=self.elapsed,font=('Consolas',15,'bold'),foreground=token('color.brand.blue'),background=token('color.background.timer')).pack(side='left',expand=True)
        logs = ttk.Frame(self.main_column, style='Card.TFrame', padding=12)
        logs.pack(fill='both',expand=True)
        ttk.Label(logs, text=' Hoạt động', image=asset(root, 'section_log_document'), compound='left', style='Section.TLabel').pack(anchor='w', pady=(0, 11))
        status_panel = ttk.Frame(logs,style='Inner.TFrame')
        status_panel.pack(fill='x',pady=(0,8))
        status_panel.columnconfigure(0,weight=1)
        status_panel.rowconfigure(0,minsize=64)
        self.status_label = ttk.Label(status_panel, textvariable=self.status, style='Status.TLabel', wraplength=340, padding=(14, 10))
        self.status_label.grid(row=0,column=0,sticky='nsew')
        self.log = tk.Text(logs, height=14, width=1, state='disabled', wrap='none', font=('Consolas',11),
                           bg=token('color.background.surfaceAlt'), fg=token('color.text.secondary'), relief='flat', padx=12, pady=10)
        log_scroll = ttk.Scrollbar(logs, command=self.log.yview)
        log_scroll.pack(side='right', fill='y')
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.pack(fill='both', expand=True)
        self.log_empty = tk.Frame(self.log, bg=token('color.background.surfaceAlt'), padx=12, pady=12)
        tk.Label(self.log_empty, bg=token('color.background.surfaceAlt'), image=asset(root, 'empty_document')).pack(pady=(0, 16))
        tk.Label(self.log_empty, bg=token('color.background.surfaceAlt'), text='Chưa có hoạt động.', foreground=token('color.text.muted'), font=font('bodyLarge')).pack(pady=4)
        self.log_empty_text = tk.Label(self.log_empty, bg=token('color.background.surfaceAlt'), text='Nhật ký sẽ hiển thị khi bot bắt đầu chạy.', wraplength=230, foreground=token('color.text.muted'))
        self.log_empty_text.pack()
        self.log_empty.place(relx=.5, rely=.5, anchor='center')
        logs.bind('<Configure>', self.resize_log_labels)
        self.root.bind('<Configure>', self.layout_changed)
        self.root.bind('<MouseWheel>', self.scroll_workspace, add='+')
        self.layout_mode = None
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Destroy>', self.dispose, add='+')
        self.load_preferences()
        self.options_changed()

        root.after(100, lambda: self.workspace_canvas.yview_moveto(0))
        self.poll_job = root.after(100, self.poll)
        self.storage_job = root.after(60000, self.prune_idle_diagnostics)

    def resize_mode_panel(self):
        current = self.tabs.index('current')
        for index, button in enumerate(self.mode_buttons):
            button.configure(style='ModeSelected.TButton' if index == current else 'TButton', state='disabled' if self.worker is not None else 'normal')
        selected = self.tabs.nametowidget(self.tabs.select())
        self.tabs.configure(height=selected.winfo_reqheight())
        self.resize_workspace()

    def scroll_workspace(self, event):
        if isinstance(event.widget, (tk.Text, ttk.Spinbox, ttk.Combobox)):
            return
        widget = event.widget
        while widget is not None:
            if widget in (self.workspace_canvas,):
                widget.yview_scroll(-int(event.delta / 120), 'units')
                return 'break'
            widget = getattr(widget, 'master', None)

    def resize_log_labels(self, event):
        width = max(120, event.width - 48)
        self.log_empty_text.configure(wraplength=width)
        self.status_label.configure(wraplength=width)

    def schedule_workspace_resize(self, event=None):
        if getattr(self, 'workspace_resize_job', None) is None:
            self.workspace_resize_job = self.root.after_idle(self.resize_workspace)

    def resize_workspace(self, event=None):
        self.workspace_resize_job = None
        if getattr(self,'_resizing_workspace',False):
            return
        self._resizing_workspace=True
        try:
            self._resize_workspace()
        finally:
            self._resizing_workspace=False

    def _resize_workspace(self):
        canvas = self.workspace_canvas
        if hasattr(self,'table') and canvas.winfo_height()>100:
            rows=max(1,len(self.table.get_children()))
            footer_height = self.mission_progress.winfo_reqheight() + 8
            rowheight=min(60,max(20,(canvas.winfo_height()-(150 if self.mini_mode else 160)-footer_height)//rows))
            style=ttk.Style(self.root)
            if int(style.lookup('Treeview','rowheight') or 42)!=rowheight:
                style.configure('Treeview',rowheight=rowheight)
        # Read settled requests, including ticket wrapping and the caption;
        # the reentrancy guard keeps Configure callbacks from nesting this work.
        self.content.update_idletasks()
        width = canvas.winfo_width()
        height = max(canvas.winfo_height(), self.content.winfo_reqheight())
        if self.content.winfo_reqheight() > canvas.winfo_height()+2:
            if not self.workspace_scrollbar.winfo_manager():
                self.workspace_scrollbar.pack(side='right',fill='y',before=canvas)
        else:
            self.workspace_scrollbar.pack_forget()
            canvas.yview_moveto(0)
        canvas.itemconfigure(self.workspace_window, width=width, height=height)
        canvas.configure(scrollregion=(0, 0, width, height))

    def layout_changed(self, event):
        if event.widget != self.root:
            return
        dimensions=(event.width,getattr(event,'height',self.root.winfo_height()),self.mini_mode)
        if dimensions==getattr(self,'_layout_dimensions',None) and self.layout_mode is not None:
            return  # Position-only Configure events during a drag need no layout.
        self._layout_dimensions=dimensions
        if self.mini_mode:
            self.schedule_workspace_resize()
            return
        scale = max(1, float(self.root.tk.call('tk', 'scaling')) / (96/72))
        ttk.Style(self.root).configure('Nav.TButton',font=(token('typography.fontFamily'),10 if event.width < 1200 else 12,'bold'))
        wide = event.width >= 1200 * scale
        self.header.configure(height=round(max(100,min(185,event.width*148/1534))))
        if hasattr(self,'summary_card'):
            compact=self.root.winfo_height()<760
            padding=(8,2) if compact else 10
            self.summary_card.configure(padding=padding if compact else (10,10,10,13))
            self.ticket_card.configure(padding=padding)
            self.summary_card.pack_configure(pady=(0,1) if compact else (0,4))
            self.ticket_card.pack_configure(pady=1 if compact else (11,7))
            self.session_controls.pack_configure(pady=(1,0) if compact else (4,0))
        wide=True
        if wide == self.layout_mode:
            return
        self.layout_mode = wide
        for i, weight in enumerate((357, 378, 266) if wide else (35, 40, 0)):
            self.content.columnconfigure(i, weight=weight, uniform='body' if weight else '', minsize=0)
        self.overview.grid(row=0,column=0,sticky='nsew',padx=(0,7))
        self.activity.grid(row=0,column=1,sticky='nsew',padx=7)
        self.main_column.grid(row=0 if wide else 1,column=2 if wide else 0,columnspan=1 if wide else 2,sticky='nsew',padx=(7,0) if wide else 0,pady=0 if wide else 14)
        self.root.after_idle(self.resize_mode_panel)

    def toggle_mini(self):
        """Reuse the live progress table; window changes never touch the worker."""
        if not self.mini_mode:
            for popup in (self.settings_popup, self.preparation_popup, self.mission_popup):
                if popup is not None and popup.winfo_exists() and popup.winfo_viewable():
                    self.root.bell()
                    return
            self._normal_window = (self.root.geometry(), self.root.state(), self.root.minsize(),
                                   self.root.attributes('-topmost'))
            self.mini_mode = True
            self.root.state('normal')
            self.root.title(APP_NAME + ' • Mini')
            self.root.minsize(540, 380)
            self.header.pack_forget()
            self.topbar.pack_forget()
            self.overview.grid_remove()
            self.main_column.grid_remove()
            self.target_toolbar.pack_forget()
            self.restore_button.pack(side='right', padx=(8,0))
            for i in range(3):
                self.content.columnconfigure(i, weight=1 if i==0 else 0, uniform='')
            self.activity.grid(row=0,column=0,sticky='nsew',padx=0)
            width=min(620,self.root.winfo_screenwidth()-32)
            height=min(660,self.root.winfo_screenheight()-100)
            x=max(0,min(self.root.winfo_x(),self.root.winfo_screenwidth()-width-16))
            y=max(0,min(self.root.winfo_y(),self.root.winfo_screenheight()-height-60))
            self.root.geometry(f'{width}x{height}+{x}+{y}')
            self.root.attributes('-topmost',True)
        else:
            geometry,state,minsize,topmost=self._normal_window
            self.mini_mode=False
            self.root.attributes('-topmost',topmost)
            self.root.title(APP_NAME)
            self.root.minsize(*minsize)
            self.header.pack(fill='x',before=self.body)
            self.topbar.pack(fill='x',before=self.body)
            self.restore_button.pack_forget()
            self.target_toolbar.pack(fill='x')
            self.layout_mode=None
            self.root.geometry(geometry)
            self.root.state(state)
            self.layout_changed(type('LayoutEvent',(),{'widget':self.root,'width':self.root.winfo_width()})())
        self.workspace_canvas.yview_moveto(0)
        self.titlebar.set_mini(self.mini_mode)
        self.schedule_workspace_resize()

    def resize_overview(self, event):
        scale = max(1, float(self.root.tk.call('tk','scaling')) / (96/72))
        exact = self.root.winfo_width() >= 1400 and self.root.winfo_height() >= 950 and scale <= 1.01
        if exact != getattr(self,'_reference_tile_heights',None):
            self._reference_tile_heights = exact
            for i,tile in enumerate(self.metric_tiles):
                tile.configure(height=58 if i<2 else 57)
                tile.pack_propagate(not exact)
            for tile in self.stock_tiles:
                tile.configure(height=73)
                tile.pack_propagate(not exact)
            for tile in self.ticket_tiles:
                tile.configure(height=91)
                tile.pack_propagate(not exact)
        columns = 2 if event.width >= 380 * scale else 1
        ticket_columns = 2 if event.width >= 420 * scale else 1
        signature = (columns, ticket_columns, exact)
        if signature == getattr(self, 'overview_columns', None):
            return
        self.overview_columns = signature
        for widgets in (self.metric_tiles, self.stock_tiles, self.ticket_tiles):
            count = ticket_columns if widgets is self.ticket_tiles else columns
            parent = widgets[0].master
            parent.columnconfigure(1, weight=(259 if exact else 1) if count == 2 else 0, uniform='tile' if count == 2 else '')
            parent.columnconfigure(0, weight=251 if exact and count==2 else 1, uniform='tile' if count == 2 else '')
            for i, widget in enumerate(widgets):
                widget.grid(row=i//count, column=i%count, sticky='ew',padx=(6,4) if exact and count==2 and i%2 else 4)

    def update_table_scrollbar(self, event=None):
        if not self.table.winfo_ismapped():
            return
        scale = max(1, float(self.root.tk.call('tk','scaling')) / (96/72))
        for column, width in (('#0',180), ('progress',176), ('status',160)):
            minimum = round(width*scale)
            if self.table.column(column,'minwidth') != minimum:
                self.table.column(column, minwidth=minimum, width=minimum)
        if sum(self.table.column(c,'minwidth') for c in ('#0','progress','status')) > self.table.winfo_width():
            self.table_horizontal.pack(side='bottom', fill='x', before=self.table)
        else:
            self.table_horizontal.pack_forget()
        visible = self.table.yview()
        if visible != (0.0, 1.0) and visible[1] - visible[0] < .999:
            self.table_scrollbar.pack(side='right', fill='y')
        else:
            self.table_scrollbar.pack_forget()

    def focus_progress_target(self, event=None):
        selected = self.table.selection()
        if selected and self.custom_list.exists(selected[0]):
            self.custom_list.selection_set(selected[0])

    def show_missions(self):
        if self.worker is not None:
            return
        self.mission_snapshot=(self.tabs.index('current'),self.mission.get(),self.free.get(),self.area.get(),
            [(i,self.custom_list.set(i,'chosen'),self.custom_list.set(i,'quantity')) for i in self.custom_list.get_children()])
        popup=self.mission_popup
        width=min(1040,self.root.winfo_screenwidth()-40)
        height=min(600,self.root.winfo_screenheight()-90)
        popup.geometry(f'{width}x{height}+{max(0,self.root.winfo_rootx()+(self.root.winfo_width()-width)//2)}+{max(0,self.root.winfo_rooty()+(self.root.winfo_height()-height)//2)}')
        popup.deiconify();popup.lift();popup.grab_set();self.resize_mode_panel()

    def close_missions(self,save=True):
        snapshot=getattr(self,'mission_snapshot',None)
        if not save and snapshot:
            mode,mission,free,area,rows=snapshot
            for i,chosen,quantity in rows:
                self.custom_list.move(i,'','end');self.custom_list.set(i,'chosen',chosen);self.custom_list.set(i,'quantity',quantity)
            self.tabs.select(mode);self.mission.set(mission);self.free.set(free);self.area.set(area)
            self.refresh_custom_preview();self.options_changed()
        self.mission_snapshot=None
        if save and snapshot and not self.save_preferences():
            self.mission_snapshot=snapshot
            messagebox.showerror('Không lưu được nhiệm vụ','Kiểm tra quyền ghi rồi thử lại.')
            return
        self.mission_popup.grab_release();self.mission_popup.withdraw()

    def show_settings(self):
        from ui.settings_dialog import SettingsDialog
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.lift()
            return
        self.settings_popup = SettingsDialog(self)

    def update_target_actions(self):
        custom = self.tabs.index('current') == 2
        if custom:
            self.target_toolbar.pack(fill='x', pady=(10, 0))
        else:
            self.target_toolbar.pack_forget()
        selected = self.custom_list.selection()
        for widget in self.target_controls:
            widget.configure(state='normal' if self.worker is None and selected else 'disabled')
        if self.worker is None and selected:
            rows=list(self.table.get_children())
            index = rows.index(selected[0]) if selected[0] in rows else 0
            self.target_controls[2].configure(state='disabled' if index == 0 else 'normal')
            self.target_controls[3].configure(state='disabled' if index == len(rows)-1 else 'normal')
        self.reset_button.configure(state='normal' if self.worker is None else 'disabled')

    def load_preferences(self):
        path = ROOT / 'runtime/ui_preferences.json'
        if not path.exists():
            return
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            self.quantity.set(saved.get('bait_quantity', 50))
            for variable, key in ((self.buy, 'buy'), (self.sell, 'sell'), (self.midnight, 'midnight_sale')):
                variable.set(saved.get(key, variable.get()))
            for key, var in self.auto_tickets.items():
                var.set(key in saved.get('auto_tickets', []))
            self.auto_resume.set(saved.get('auto_resume',False))
            self.resume_limit.set(saved.get('resume_limit',3))
            self.area.set(saved.get('area', ''))
            for species, quantity in saved.get('custom_targets', []):
                if self.custom_list.exists(species):
                    self.custom_list.move(species, '', 'end')
                    self.custom_list.set(species, 'chosen', '☑')
                    self.custom_list.set(species, 'quantity', quantity)
        except (OSError, ValueError, tk.TclError):
            self.append('Chưa đọc được thiết lập cũ; dùng thiết lập mặc định.')

    def save_preferences(self, overrides=None):
        if getattr(self,'mission_snapshot',None) is not None and overrides is None:
            return True  # Modal draft is committed only by Lưu nhiệm vụ.
        path = ROOT / 'runtime/ui_preferences.json'
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            settings = {'bait_quantity': self.quantity.get(), 'buy': self.buy.get(), 'sell': self.sell.get(),
                        'midnight_sale': self.midnight.get(), 'area': self.area.get(),
                        'auto_tickets': [key for key, var in self.auto_tickets.items() if var.get()],
                        'custom_targets': self.custom_targets(), 'auto_resume':self.auto_resume.get(), 'resume_limit':self.resume_limit.get()}
            if overrides:
                settings.update(overrides)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(path)
            return True
        except (OSError, ValueError, tk.TclError) as exc:
            self.append('Không lưu được thiết lập: ' + str(exc))
            return False

    def options_changed(self):
        if self.worker is not None:
            return
        if self.mission.get():
            self.free.set(False)
        self.controls[1].configure(state='disabled' if self.mission.get() else 'normal')
        free = self.free.get() and not self.mission.get()
        self.area_widget.configure(state='readonly' if free else 'disabled')
        allowed = self.mission.get() or (free and self.area.get() in AREAS_UI) or (self.tabs.index('current') == 2 and bool(self.custom_targets()))
        validation_reason = ''
        if allowed:
            try:
                custom = self.custom_targets() if self.tabs.index('current') == 2 else ()
                Options(self.mission.get(), self.free.get(), AREAS_UI.get(self.area.get(), ''),
                        self.buy.get(), self.sell.get(), self.quantity.get(), custom, self.midnight.get(),
                              tuple(key for key, var in self.auto_tickets.items() if var.get()), self.auto_resume.get(), self.resume_limit.get()).validate()
            except (ValueError, tk.TclError) as exc:
                allowed = False
                validation_reason = 'Nhập số mồi từ 1 đến 50.' if isinstance(exc, tk.TclError) else str(exc)
        self.start_button.configure(state='normal' if allowed else 'disabled')
        reasons = ('Bật tự động làm nhiệm vụ để bắt đầu.',
                   'Chọn khu câu và bật Câu tự do.', 'Chọn ít nhất một mục tiêu.')
        self.update_target_actions()
        self.custom_list.lock(False)
        self.start_reason.set(validation_reason or ('Sẵn sàng bắt đầu.' if allowed
                                                  else reasons[self.tabs.index('current')]))
        self.status.set(self.start_reason.get())

    def start(self):
        if self.worker is not None:
            return
        try:
            custom = self.custom_targets() if self.tabs.index('current') == 2 else ()
            options = Options(self.mission.get(), self.free.get(), AREAS_UI.get(self.area.get(), ''),
                              self.buy.get(), self.sell.get(), self.quantity.get(), custom, self.midnight.get(),
                              tuple(key for key, var in self.auto_tickets.items() if var.get()), self.auto_resume.get(), self.resume_limit.get())
            self.worker = BotWorker(options, lambda kind, data: self.messages.put((kind, data)), inventory_cache=self.inventory_cache)
        except Exception as exc:
            messagebox.showerror('Không thể bắt đầu', str(exc))
            return
        self.close_missions(True)
        self.start_button.configure(state='disabled')
        self.start_reason.set('Phiên câu đang hoạt động.')
        for widget in self.target_controls:
            widget.configure(state='disabled')
        for button in self.mode_buttons:
            button.configure(state='disabled')
        self.custom_list.lock(True)
        self.session_tab = self.tabs.select()
        for tab in self.tabs.tabs():
            self.tabs.tab(tab, state='normal' if tab == self.session_tab else 'disabled')
        for widget in self.controls:
            widget.configure(state='disabled')
        self.area_widget.configure(state='disabled')
        self.pause_button.configure(state='disabled', text='Tạm dừng')
        self.stop_button.configure(state='normal')
        self.timer_started = None
        self.show_preparation("Đang kiểm tra thiết bị và lấy thông tin nhân vật…")
        self.save_preferences()
        self.elapsed.set('00:00:00')
        self.settings_button.configure(state='normal')
        self.status.set('Đang kiểm tra thiết bị…')
        threading.Thread(target=self.worker.run, daemon=True).start()

    def show_preparation(self, message):
        if self.preparation_popup is None or not self.preparation_popup.winfo_exists():
            popup = self.preparation_popup = tk.Toplevel(self.root)
            popup.title('Chuẩn bị phiên câu')
            popup.transient(self.root)
            popup.resizable(False, False)
            card = ttk.Frame(popup, style='Card.TFrame', padding=24)
            card.pack(fill='both', expand=True)
            ttk.Label(card, text='Đang chuẩn bị phiên câu…', style='Section.TLabel').pack(anchor='w')
            self.preparation_text = tk.StringVar()
            ttk.Label(card, textvariable=self.preparation_text, wraplength=420).pack(fill='x', pady=20)
            ttk.Style(self.root).configure('Preparation.Horizontal.TProgressbar', background='#135BFA', troughcolor='#EAF3FF', bordercolor='#EAF3FF')
            bar = self.preparation_bar = ttk.Progressbar(card, mode='indeterminate', length=420, style='Preparation.Horizontal.TProgressbar')
            bar.pack(fill='x', pady=10)
            bar.start(15)
            ttk.Button(card, text='Hủy chuẩn bị', command=self.stop).pack(anchor='e')
            popup.protocol('WM_DELETE_WINDOW', self.stop)
            popup.update_idletasks()
            popup.geometry(f'+{self.root.winfo_rootx()+(self.root.winfo_width()-popup.winfo_reqwidth())//2}+{self.root.winfo_rooty()+(self.root.winfo_height()-popup.winfo_reqheight())//2}')
        self.preparation_text.set(message)

    def close_preparation(self):
        if self.preparation_popup is not None:
            if self.preparation_popup.winfo_exists():
                self.preparation_bar.stop()
                self.preparation_popup.destroy()
            self.preparation_popup = None

    def mode_changed(self, event=None):
        if self.worker is not None:
            return
        index = self.tabs.index('current')
        self.custom_list.configure(height=len(self.custom_list.get_children()))
        self.root.after_idle(self.resize_mode_panel)
        self.update_target_actions()
        self.refresh_custom_preview()
        if index != 0:
            self.mission.set(False)
        if index != 1:
            self.free.set(False)
        self.options_changed()

    def catalog_changed(self):
        self.options_changed()
        self.save_preferences()
        self.refresh_custom_preview()

    def refresh_custom_preview(self):
        if self.worker is None and self.tabs.index('current') == 2:
            targets = [{'species': s, 'name': SPECIES[s], 'current': 0, 'required': n} for s, n in self.custom_targets()]
            try:
                saved = json.loads((ROOT / 'runtime/custom_mission.json').read_text(encoding='utf-8'))
                if sorted(saved.get('plan',[])) == sorted([[s,n] for s,n in self.custom_targets()]) and saved.get('status') != 'COMPLETE':
                    by_species={t['species']:t for t in saved['targets']}
                    targets=[by_species[s] for s,_ in self.custom_targets()]
            except (OSError, ValueError, KeyError):
                pass
            self.render_progress({'targets': targets, 'counts': {}})

    def custom_targets(self):
        return tuple((item, int(self.custom_list.set(item, 'quantity'))) for item in self.custom_list.get_children()
                     if self.custom_list.set(item, 'chosen') == '☑')

    def move_target(self, delta):
        if self.worker or self.tabs.index('current') != 2:
            return
        selected = self.table.selection() or self.custom_list.selection()
        if not selected:
            return
        item=selected[0];rows=list(self.table.get_children())
        if item not in rows:
            return
        index=rows.index(item);other=max(0,min(len(rows)-1,index+delta))
        self.custom_list.move(item,'',self.custom_list.index(rows[other]))
        self.save_preferences();self.refresh_custom_preview()
        self.table.selection_set(item);self.focus_progress_target();self.update_target_actions()

    def drag_progress_target(self,event):
        if self.worker or self.tabs.index('current') != 2:
            return
        source=getattr(self,'drag_progress','');target=self.table.identify_row(event.y)
        if source and target and source != target:
            self.custom_list.move(source,'',self.custom_list.index(target))
            self.save_preferences();self.refresh_custom_preview();self.table.selection_set(source)
            self.focus_progress_target()

    def set_target_quantity(self):
        if self.worker or not self.custom_list.selection():
            return
        try:
            value = self.target_quantity.get()
            if not 1 <= value <= 9999:
                raise ValueError()
        except (ValueError, tk.TclError):
            messagebox.showerror('Số lượng', 'Nhập số lượng từ 1 đến 9999.')
            return
        self.custom_list.set(self.custom_list.selection()[0], 'quantity', value)
        self.save_preferences()
        self.refresh_custom_preview()

    def reset_custom_targets(self):
        if self.worker is not None:
            return
        path = ROOT / 'runtime/custom_mission.json'
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            messagebox.showerror('Không thể reset', str(exc))
            return
        from fishing.quest import AREAS
        for species in SPECIES:
            if species in AREAS and self.custom_list.exists(species):
                self.custom_list.move(species, '', 'end')
                self.custom_list.set(species, 'chosen', '□')
                self.custom_list.set(species, 'quantity', 1)
        self.custom_list.selection_remove(*self.custom_list.selection())
        self.custom_list.yview_moveto(0)
        self.target_quantity.set(1)
        if self.tabs.index('current') == 2:
            self.render_progress({'targets': [], 'counts': {}})
        self.save_preferences()
        self.options_changed()
        self.append('Đã reset mục tiêu tự đặt và tiến độ đã lưu. Lần bắt đầu tiếp theo tính từ 0.')

    def notify_completion(self, message):
        try:
            winsound.PlaySound('SystemAsterisk', winsound.SND_ALIAS | winsound.SND_ASYNC)
        except RuntimeError:
            self.root.bell()
        previous = getattr(self, 'completion_popup', None)
        if previous is not None and previous.winfo_exists():
            previous.destroy()
        popup = self.completion_popup = tk.Toplevel(self.root)
        popup.title('Hoàn thành nhiệm vụ')
        popup.transient(self.root)
        popup.resizable(False, False)
        card = ttk.Frame(popup, style='Card.TFrame', padding=28)
        card.pack(fill='both', expand=True)
        ttk.Label(card, text='✓  HOÀN THÀNH!', style='Section.TLabel', foreground=token('color.semantic.success'),
                  font=('Segoe UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(card, text=message, style='Card.TLabel', wraplength=420).pack(anchor='w', pady=(12, 8))
        ttk.Label(card, text='Thời gian: ' + self.elapsed.get(), style='Card.TLabel').pack(anchor='w')
        for item in self.table.get_children():
            values = self.table.item(item, 'values')
            ttk.Label(card, text=f'{values[0]}: {values[1]}', style='Card.TLabel').pack(anchor='w', pady=2)
        ttk.Button(card, text='Tuyệt!  Đóng thông báo', style='Accent.TButton', command=popup.destroy).pack(fill='x', pady=(20, 0))
        popup.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - popup.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - popup.winfo_reqheight()) // 2
        popup.geometry(f'+{max(0, x)}+{max(0, y)}')
        popup.lift()

    def pause(self):
        if self.worker is None or self.worker.stop.is_set():
            return
        if self.worker.pause.is_set():
            self.worker.pause.clear()
            self.pause_button.configure(text='Tạm dừng')
            self.refresh_progress_status('RUNNING')
        else:
            self.worker.pause.set()
            self.pause_button.configure(text='Tiếp tục')
            self.status.set('Sẽ tạm dừng sau lượt hiện tại')
            self.refresh_progress_status('PAUSED')

    def stop(self):
        if self.worker:
            self.worker.stop.set()
            self.worker.pause.clear()
            self.status.set('Đang kết thúc…')
            if self.preparation_popup is not None:
                self.preparation_text.set('Đang hủy chuẩn bị, chờ thao tác hiện tại kết thúc…')
            self.pause_button.configure(state='disabled')
            self.stop_button.configure(state='disabled')

    def append(self, text):
        self.append_many((text,))

    def append_many(self, lines):
        """One Text update per batch; keep the user's position when reading history."""
        if not lines:
            return
        at_bottom = self.log.yview()[1] >= 0.99
        self.log_empty.place_forget()
        self.log.configure(state='normal')
        self.log.insert('end', '\n'.join(str(line) for line in lines) + '\n')
        excess = int(self.log.index('end-1c').split('.')[0]) - 1501
        if excess > 0:
            self.log.delete('1.0', f'{excess + 1}.0')
        if at_bottom:
            self.log.see('end')
        self.log.configure(state='disabled')

    def poll(self):
        previous = getattr(self, 'poll_job', None)
        if previous is not None:
            self.root.after_cancel(previous)
        if self.timer_started is not None:
            seconds = int(time.monotonic() - self.timer_started)
            self.set_changed(self.elapsed, f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}')
        pending_progress, logs = None, []
        pending_errors = getattr(self, '_pending_errors', [])
        for _ in range(200):
            try:
                kind, data = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                pending_progress = data
                continue
            if kind == 'log':
                logs.append(data)
                continue
            # Lifecycle notifications must see the latest table and log history.
            if pending_progress is not None:
                self.render_snapshot(pending_progress)
                pending_progress = None
            if logs:
                self.append_many(logs)
                logs = []
            if kind == 'preparation':
                self.pause_button.configure(state='disabled')
                self.show_preparation(data)
                self.status.set(data)
            elif kind == 'prepared':
                self.pause_button.configure(state='normal')
                self.close_preparation()
                if self.timer_started is None:
                    self.timer_started = time.monotonic()
            elif kind == 'status':
                self.status.set(data)
            elif kind in ('error', 'notice'):
                self.close_preparation()
                self.append(data)
                if kind == 'error':
                    pending_errors.append(data)
                else:
                    self.notify_completion(data)
            elif kind == 'done':
                self.close_preparation()
                self.append('Kết thúc: ' + data)
                self.status.set({'ERROR': 'Đã dừng do lỗi', 'COMPLETE': 'Hoàn thành nhiệm vụ',
                                 'STOPPED': 'Đã kết thúc'}.get(data, data))
                self.timer_started = None
                self.refresh_progress_status(data)
                self.settings_button.configure(state='normal')
                for widget in self.target_controls:
                    widget.configure(state='normal')
                # Re-enable and reselect before releasing the worker guard.
                # Disabling the selected Notebook tab clears selection in Tk.
                selected = getattr(self, 'session_tab', '') or self.tabs.select()
                if not selected:
                    selected = self.tabs.tabs()[0 if self.mission.get() else 1 if self.free.get() else 2]
                for tab in self.tabs.tabs():
                    self.tabs.tab(tab, state='normal')
                self.tabs.select(selected)
                self.worker = None
                self.resize_mode_panel()
                self.pause_button.configure(state='disabled', text='Tạm dừng')
                self.stop_button.configure(state='disabled')
                for widget in self.controls:
                    widget.configure(state='normal')
                self.options_changed()
                self.status.set({'ERROR': 'Đã dừng do lỗi • Kiểm tra nhật ký hoạt động',
                                 'COMPLETE': 'Hoàn thành nhiệm vụ', 'STOPPED': 'Đã kết thúc'}.get(data, data))
        if pending_progress is not None:
            self.render_snapshot(pending_progress)
        self.append_many(logs)
        self._pending_errors = pending_errors
        # Drain terminal progress/done first. Modal error dialogs must not hold
        # the finished worker guard or its disabled controls until dismissed.
        if self.messages.empty() and pending_errors:
            self._pending_errors = []
            self.root.bell()
            messagebox.showerror(APP_NAME, '\n\n'.join(pending_errors))
        self.poll_job = self.root.after(15 if not self.messages.empty() else 75, self.poll)

    @staticmethod
    def set_changed(variable, value):
        if variable.get() != value:
            variable.set(value)

    def render_snapshot(self, data):
        """Update presentation once for a burst of worker progress snapshots."""
        from fishing.inventory import TICKETS
        for key, var in self.wallet_values.items():
            value = data.get('wallet', {}).get(key)
            self.set_changed(var, 'Chưa xác định' if value is None else f'{value:,}'.replace(',', '.'))
        for key, (title, *_rest) in TICKETS.items():
            ticket = data.get('tickets', {}).get(key, {})
            label = {'active': 'Có • Còn hiệu lực', 'missing': 'Không có vé', 'expired': 'Đã hết hạn'}.get(ticket.get('status'), 'Chưa xác định')
            expiry = ticket.get('expires_on')
            if expiry:
                label += '\nHết hạn: ' + '-'.join(reversed(expiry.split('-')))
            self.set_changed(self.ticket_values[title], label)
        for key, variable in self.metric_values.items():
            value = max(0, data['casts'] - data['bites']) if key == 'misses' else data[key]
            self.set_changed(variable, str(value))
        estimates = data.get('bait_estimated', {})
        for key, title in (('ecological', 'mồi trùng'), ('dock', 'mồi cá trâm')):
            count = data.get('bait_stocks', {}).get(key)
            label = 'Chưa xác định' if count is None else ('≈ ' if estimates.get(key) else '') + f'{count} {title}'
            self.set_changed(self.stock_values[key], label)
        self.render_progress(data)

    def render_progress(self, data):
        """Update stable rows without rebuilding the table or losing scroll/focus."""
        from fishing.quest import AREAS
        self._last_progress = dict(data)
        self.mission_progress.set_targets(data['targets'])
        running = data.get('status') == 'RUNNING' and not data.get('preparing')
        if self.worker is not None and self.worker.pause.is_set():
            running = False
        def state(species, target=None):
            if target and target['required'] > 0 and target['current'] >= target['required']:
                return '✓ Đã hoàn thành', 'completed'
            area = (target or {}).get('area') or AREAS.get(species)
            if running and area and area == data.get('area'):
                return '● Đang tiến hành', 'active'
            return '○ Đang chờ', 'waiting'
        rows = []
        if data['targets']:
            for target in data['targets']:
                species = target.get('species') or target['name']
                label, tag = state(species, target)
                rows.append((species, (target['name'], f"{target['current']}/{target['required']}", label), tag))
        else:
            for species, count in data['counts'].items():
                label, tag = state(species)
                rows.append((species, (SPECIES.get(species, 'Chưa xác định'), count, label), tag))
        signature = tuple((key, tuple(str(value) for value in values), tag) for key, values, tag in rows)
        if signature == getattr(self, '_progress_signature', None):
            return
        self._progress_signature = signature
        desired = {key for key, _, _ in rows}
        for key in self.table.get_children():
            if key not in desired:
                self.table.delete(key)
        for index, (key, values, tag) in enumerate(rows):
            tags = (tag,'active_even') if tag=='active' and index%2==0 else (tag,)
            if self.table.exists(key):
                if tuple(self.table.item(key, 'values')) != tuple(str(v) for v in values) or self.table.item(key,'tags') != tags:
                    self.table.item(key, values=values, text=values[0], tags=tags)
                if self.table.index(key) != index:
                    self.table.move(key, '', index)
            else:
                self.table.insert('', index, iid=key, text=values[0], image=asset(self.root, 'fish_'+key) if key in SPECIES else '', values=values, tags=tags)
        self.table.configure(height=max(4 if not rows else 1, len(rows)))
        if rows:
            self.empty_results.place_forget()
        else:
            self.empty_results.place(relx=.5, rely=.55, anchor='center')
        self.schedule_workspace_resize()

    def refresh_progress_status(self, status):
        data=getattr(self,'_last_progress',None)
        if data is not None:
            self.render_progress({**data,'status':status})

    def open_logs(self):
        try:
            folder = ROOT / 'debug/ui'
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(folder)
        except OSError as exc:
            messagebox.showerror('Không mở được thư mục log', str(exc))

    def prune_idle_diagnostics(self):
        # Active workers already prune from their own write thread. Avoid a
        # competing GUI-thread reader of runtime files during atomic writes.
        if self.worker is None:
            from debug.retention import maybe_prune
            maybe_prune(ROOT/'debug')
        self.storage_job = self.root.after(60000,self.prune_idle_diagnostics)

    def dispose(self, event):
        if event.widget == self.root:
            self.close_preparation()
            for job in self.root.tk.call('after', 'info'):
                try:
                    self.root.tk.call('after', 'cancel', job)
                except tk.TclError:
                    pass

    def close(self):
        if self.settings_popup is not None and self.settings_popup.winfo_exists():
            self.settings_popup.cancel()
        self.save_preferences()
        if self.worker:
            self.stop()
            self.root.after(100, self.wait_close)
        else:
            self.root.destroy()

    def wait_close(self):
        if self.worker is None:
            self.root.destroy()
        else:
            self.root.after(100, self.wait_close)


if __name__ == '__main__':
    if '--ui-check' in sys.argv:
        # Packaging-only diagnostic: construct presentation, never start a worker.
        root = tk.Tk()
        root.withdraw()
        app = App(root)
        root.update_idletasks()
        root.update()
        (ROOT / 'gui-ui-check.json').write_text(json.dumps({
            'version': APP_VERSION, 'tk': tk.TkVersion, 'assets_loaded': len(root._ui_assets),
            'mode_tabs': len(app.tabs.tabs()), 'worker_started': app.worker is not None,
            'root': str(ROOT)}, indent=2), encoding='utf-8')
        root.destroy()
        sys.exit(0)
    if '--smoke-test' in sys.argv:
        root = tk.Tk()
        root.withdraw()
        app = App(root)
        from fishing.dock import DockDetector
        (ROOT / 'gui-smoke-test.json').write_text(json.dumps({
            'version': APP_VERSION, 'tk': tk.TkVersion, 'start_disabled': str(app.start_button['state']) == 'disabled',
            'dock_templates': len(DockDetector().templates),
            'ocr_script': (ROOT / 'vision/windows_ocr.ps1').is_file(),
            'root': str(ROOT)}, indent=2), encoding='utf-8')
        root.destroy()
        sys.exit(0)
    folder = ROOT / 'runtime'
    folder.mkdir(parents=True, exist_ok=True)
    lock = (folder / 'gui.lock').open('a+b')
    if lock.tell() == 0:
        lock.write(b'0')
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(APP_NAME, 'Giao diện đang mở. Chỉ chạy một bot để tránh thao tác trùng.')
        root.destroy()
    else:
        from debug.retention import maybe_prune
        maybe_prune(ROOT / 'debug')
        App(tk.Tk())
        tk.mainloop()
    lock.close()
