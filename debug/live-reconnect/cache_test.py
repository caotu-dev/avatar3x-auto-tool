"""Prepare two areas from one real chest scan; purchases and casts are forbidden."""
from pathlib import Path
import sys,json,cv2
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings
from fishing.inventory import InventoryController
from ui.runner import BotWorker,Options
out=Path('debug/live-inventory-cache').resolve();out.mkdir(exist_ok=True)
s=Settings();real=AdbDevice(s.serial,s.adb_path)
class CountInventory(InventoryController):
 scans=0
 def chest(self):
  CountInventory.scans+=1
  assert CountInventory.scans==1,'No second chest scan allowed'
  return super().chest()
 def buy_ticket(self,*args,**kwargs):raise AssertionError('No ticket purchase in this validation')
 def buy_dock_bait(self,*args,**kwargs):raise AssertionError('No bait purchase in this validation')
class Device:
 def __getattr__(self,name):return getattr(real,name)
 def tap(self,x,y):
  assert not(730<=x<=868 and 825<=y<=865),'No casts allowed'
  return real.tap(x,y)
messages=[]
with patch('ui.runner.ROOT',out/'isolated'),patch('ui.runner.InventoryController',CountInventory):
 worker=BotWorker(Options(free=True,area='ca_ro'),lambda k,v:messages.append((k,v)),Device())
 worker.data['casts']=100
 def no_purchase(*args,**kwargs):raise AssertionError('No ecological purchases allowed')
 worker.travel.sell_and_buy=no_purchase
 worker.prepare_area('ca_ro')
 worker.prepare_area('ca_noc')
 assert CountInventory.scans==1 and worker.data['casts']==100
 cv2.imwrite(str(out/'after.png'),real.screenshot())
 summary={'scan_count':CountInventory.scans,'prepared_areas':['ca_ro','ca_noc'],'casts':worker.data['casts'],'bait_purchased':worker.data['bait_purchased'],'tickets':worker.data['tickets'],'bait_stocks':worker.data['bait_stocks'],'wallet':worker.data['wallet'],'messages':messages,'log':str(worker.folder)}
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:summary[k] for k in ('scan_count','prepared_areas','casts','bait_purchased','bait_stocks','wallet')},ensure_ascii=True))
