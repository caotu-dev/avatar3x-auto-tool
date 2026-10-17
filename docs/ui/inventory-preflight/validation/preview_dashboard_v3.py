from pathlib import Path
import tempfile,json,tkinter as tk,time
from unittest.mock import patch
import sys
sys.path.append('C:/Users/ADMIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages')
from PIL import ImageGrab
from gui import App
p=Path('docs/ui/inventory-preflight/validation/dashboard-v3');p.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir='debug') as folder,patch('gui.ROOT',Path(folder)):
 root=tk.Tk();app=App(root);root.geometry('1536x960+0+0');root.attributes('-topmost',True);root.deiconify();root.lift();root.update();time.sleep(1.5)
 app.tabs.select(2);root.update()
 for species in ('ca_ngua','ca_chim','ca_lia_thia'):app.custom_list.set(species,'chosen','☑')
 app.refresh_custom_preview();app.options_changed();root.update();time.sleep(.3)
 def capture(name,window):
  window.attributes('-topmost',True);window.lift();window.update();time.sleep(1.5);ImageGrab.grab(bbox=(window.winfo_rootx(),window.winfo_rooty(),window.winfo_rootx()+window.winfo_width(),window.winfo_rooty()+window.winfo_height())).save(p/name)
 capture('dashboard.png',root)
 app.show_missions();root.update();capture('missions.png',app.mission_popup);app.close_missions(False)
 app.show_settings();root.update();capture('settings.png',app.settings_popup);app.settings_popup.cancel()
 root.destroy()
