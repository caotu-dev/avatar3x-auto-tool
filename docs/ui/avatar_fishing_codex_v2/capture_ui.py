"""Presentation capture with isolated preferences; never runs BotWorker or ADB."""
import argparse, json, sys, tempfile, time
from pathlib import Path
from unittest.mock import patch
parser=argparse.ArgumentParser();parser.add_argument('--pillow-site');args=parser.parse_args()
if args.pillow_site:sys.path.append(args.pillow_site)
project=Path(__file__).resolve().parents[3];sys.path.insert(0,str(project))
from PIL import ImageGrab
import tkinter as tk
from gui import App
out=Path(__file__).parent/'screenshots';out.mkdir(exist_ok=True)
report=[]
with tempfile.TemporaryDirectory(dir=project/'debug') as folder, patch('gui.ROOT',Path(folder)):
 root=tk.Tk();root.attributes('-topmost',True);app=App(root)
 base=float(root.tk.call('tk','scaling'))
 def capture(name,width,height):
  root.update();root.lift();time.sleep(.2);root.update()
  ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+width,root.winfo_rooty()+height)).save(out/(name+'.png'))
 try:
  for multiplier in (1,1.25,1.5):
   root.tk.call('tk','scaling',base*multiplier)
   app.layout_mode=None
   for width,height in ((1536,1024),(1280,800),(1024,720)):
    root.geometry(f'{width}x{height}+0+0');root.update()
    for index in range(3):
     app.tabs.select(index);root.update()
    app.layout_changed(type('Resize',(),{'widget':root,'width':width})())
    capture(f'{width}x{height}-scale{int(multiplier*100)}',width,height)
    buttons=(app.settings_button,app.start_button,app.pause_button,app.stop_button,app.log_folder_button)
    report.append({'viewport':[width,height],'scale':multiplier,
     'columns':[w.winfo_width() for w in (app.main_column,app.activity,app.overview)],
     'buttons_fit':all(w.winfo_width()>=w.winfo_reqwidth() for w in buttons),
     'catalog_rows':len(app.custom_list.get_children()),'progress_inner_scroll':app.table['yscrollcommand']})
  root.tk.call('tk','scaling',base);app.layout_mode=None
  root.geometry('1536x1024+0+0');root.update()
  for key in app.custom_list.get_children():app.custom_list.set(key,'chosen','☑')
  app.options_changed();app.refresh_custom_preview();app.custom_list.focus_row('cua')
  capture('dashboard-goals',1536,1024)
  app.show_settings();capture('settings-popup',1536,1024);app.settings_popup.cancel()
 finally:root.destroy()
(out/'layout-checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
