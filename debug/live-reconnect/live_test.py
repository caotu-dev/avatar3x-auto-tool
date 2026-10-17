"""Recovery only: intentionally drop the first Continue tap, never cast or purchase."""
from pathlib import Path
import sys,json,cv2
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings
from fishing.reconnect import ContinueScreen
from ui.runner import BotWorker,Options
out=Path('debug/live-reconnect').resolve();s=Settings();real=AdbDevice(s.serial,s.adb_path);reader=ContinueScreen()
a=real.screenshot();assert reader.detect(a)
cv2.imwrite(str(out/'before.png'),a)
class DropFirst:
 requests=0;sent=0
 def __getattr__(self,name):return getattr(real,name)
 def screenshot(self):return real.screenshot()
 def tap(self,x,y):
  point=reader.detect(real.screenshot())
  assert point and abs(point[0]-x)<5 and abs(point[1]-y)<5,'Only verified Continue input allowed'
  self.requests+=1
  if self.requests==1:return
  assert self.sent<2,'Maximum live Continue taps'
  real.tap(x,y);self.sent+=1
proxy=DropFirst();messages=[]
with patch('ui.runner.ROOT',out/'isolated'):
 worker=BotWorker(Options(free=True,area='ca_ro'),lambda k,v:messages.append((k,v)),proxy)
 worker.inventory_ready=True;worker.data['casts']=100
 try:
  worker.reconnect();status='READY'
 finally:
  cv2.imwrite(str(out/'after.png'),real.screenshot())
  summary={'status':worker.data['status'],'requests':proxy.requests,'sent':proxy.sent,'dropped':1,'casts':worker.data['casts'],'inventory_cache_preserved':worker.inventory_ready,'guard_restored':worker.device.guard_session,'log':str(worker.folder),'messages':messages}
  (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
assert status=='READY' and proxy.requests==2 and proxy.sent==1 and worker.data['casts']==100
print(json.dumps({k:summary[k] for k in ('requests','sent','casts','inventory_cache_preserved','guard_restored')},ensure_ascii=True))
