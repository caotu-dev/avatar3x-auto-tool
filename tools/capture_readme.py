"""Capture real app widgets with temporary settings and synthetic example data.

Optional developer dependency: Pillow. No bot, ADB, login or user data is used.
Usage: python tools/capture_readme.py [--pillow-site PATH]
"""
import argparse
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser()
parser.add_argument('--pillow-site')
args = parser.parse_args()
if args.pillow_site:
    sys.path.append(args.pillow_site)
from PIL import ImageGrab
from gui import App
from fishing.catch import SPECIES

out = ROOT / 'docs/images'
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder, patch('gui.ROOT', Path(folder)):
    root = tk.Tk()
    root.tk.call('tk', 'scaling', 96 / 72)
    app = App(root)
    root.geometry('1534x1025+0+0')
    root.attributes('-topmost', True)

    def shot(widget, filename):
        widget.lift()
        widget.update()
        x, y = widget.winfo_rootx(), widget.winfo_rooty()
        ImageGrab.grab(bbox=(x, y, x + widget.winfo_width(), y + widget.winfo_height())).save(out / filename)

    def dashboard():
        targets = [dict(species=s, name=SPECIES[s], current=n, required=50, area='ca_noc' if s == 'cua' else 'ca_ro')
                   for s, n in [('ca_ro', 12), ('ca_long_tong', 5), ('cua', 0)]]
        data = dict(casts=20, bites=17, misses=3, bait_purchased=50,
                    bait_stocks={'ecological': 30, 'dock': 0}, bait_estimated={'ecological': True},
                    tickets={s: dict(status='unknown') for s in ('ca_ro', 'ca_noc', 'ca_map', 'dock')},
                    wallet={'coins': 10000, 'gold': 20}, counts={'ca_ro': 12, 'ca_long_tong': 5},
                    targets=targets, status='RUNNING', area='ca_ro')
        app.mission.set(True)
        app.options_changed()
        app.messages.put(('progress', data))
        app.messages.put(('log', '[MINH HỌA] Dữ liệu ví dụ cho hướng dẫn v2.0.0; chưa chạy bot.'))
        app.status.set('Giao diện minh họa — số liệu ví dụ, không phải phiên câu thực tế.')
        root.after(1000, save_dashboard)

    def save_dashboard():
        shot(root, 'dashboard-v2.png')
        app.show_missions()
        app.tabs.select(2)
        for species in ('ca_ro', 'ca_long_tong', 'cua'):
            app.custom_list.set(species, 'chosen', '☑')
            app.custom_list.set(species, 'quantity', 50)
        app.custom_list.focus_row('ca_ro')
        root.after(1000, missions)

    def missions():
        shot(app.mission_popup, 'missions-v2.png')
        app.close_missions(False)
        app.show_settings()
        root.after(1000, settings)

    def settings():
        shot(app.settings_popup, 'settings-v2.png')
        app.settings_popup.cancel()
        (out / 'README.md').write_text(
            '# UI v2.0.0\n\nCaptured from real Tk widgets by tools/capture_readme.py. '
            'Synthetic example data is explicitly labeled in the dashboard and user guide. '
            'No worker, ADB or user settings were used.\n', encoding='utf-8')
        root.destroy()

    root.after(400, lambda: root.geometry('1534x1025+0+0'))
    root.after(1200, dashboard)
    root.mainloop()
