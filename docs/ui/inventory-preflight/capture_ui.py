"""Render isolated UI examples, without workers or game inputs."""
import sys,tempfile,time,json
from pathlib import Path
from unittest.mock import patch
sys.path.append(r'C:/Users/ADMIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages')
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from PIL import ImageGrab
import tkinter as tk
from gui import App
from fishing.inventory import TICKETS
out=Path(__file__).parent/'screenshots'
project=Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(dir=project/'debug') as folder,patch('gui.ROOT',Path(folder)):
 root=tk.Tk();root.attributes('-topmost',True);root.geometry('1536x960+0+0');app=App(root)
 def capture(name):
  root.update();app.workspace_canvas.yview_moveto(0);root.lift()
  if app.settings_popup:
   app.settings_popup.overlay.lift(root);app.settings_popup.lift(app.settings_popup.overlay)
  if app.preparation_popup:app.preparation_popup.lift(root)
  time.sleep(.3);root.update()
  ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save(out/(name+'.png'))
 try:
  app.tabs.select(2);root.update()
  report_path=Path(__file__).parent/'validation/live-results.json'
  report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
  observed=report.get('after_ticket_test',report.get('final_inventory',report.get('after_second_purchase',{})))
  rows=report.get('records',[])
  app.messages.put(('progress',dict(wallet=observed.get('wallet',{}),tickets=observed.get('tickets',{}),bait_stocks=observed.get('bait_stocks',{}),targets=[],counts=report.get('fish_counts',{}),casts=report.get('attempts',0),bites=sum(bool(r.get('bite_observed')) for r in rows),misses=report.get('outcomes',{}).get('FAILED',0),unclassified_results=report.get('outcomes',{}).get('RESULT',0),bait_purchased=report.get('bait_purchased',0))))
  app.poll();capture('overview')
  app.show_settings();capture('settings');app.settings_popup.cancel()
  app.show_preparation('Đang mở rương, kiểm tra vé, mồi và số dư…');capture('preparation');app.close_preparation()
 finally:root.destroy()
