from pathlib import Path
import sys,json,cv2,time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dataclasses import asdict
from adb.device import AdbDevice
from config.settings import Settings,SessionSettings
from fishing.session import FishingSession
from fishing.inventory import InventoryController
from fishing.detector import FishingDetector
from fishing.states import FishingState
ROOT=Path('debug/live-inventory-dock');file=ROOT/'bounded-ledger.json'
state=json.loads(file.read_text(encoding='utf-8')) if file.exists() else {'casts':2,'limit':100,'remaining':49,'purchases':1,'purchased':50,'pending':False,'batches':[]}
def save():
 tmp=file.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(file)
save()
s=Settings();real=AdbDevice(s.serial,s.adb_path);detector=FishingDetector(area='dock')
class Guard:
 def screenshot(self):return real.screenshot()
 def tap(self,x,y):
  if 730<=x<=868 and 825<=y<=865:
   a=real.screenshot();o=detector.detect(a)
   if o.state is not FishingState.READY or 'toss' not in o.matches:raise RuntimeError('Cast not verified')
   t=o.matches['toss']
   if not(t.x<=x<t.x+t.width and t.y<=y<t.y+t.height):raise RuntimeError('Cast outside verified control')
   if state['casts']>=100 or state['remaining']<=0:raise RuntimeError('Cast limit/stock reached')
   state['casts']+=1;state['remaining']-=1;save()
   print('BOUNDED_CAST',state['casts'],'/100',flush=True)
  real.tap(x,y)
 def swipe(self,*args,**kwargs):return real.swipe(*args,**kwargs)
 def type_number(self,*args):return real.type_number(*args)
d=Guard()
def event(name,details):
 if name=='PURCHASE_PENDING':
  if state['purchases']>=2 or details['quantity']!=50 or state['pending']:raise RuntimeError('Purchase limit reached')
  state['pending']=True;save()
 if name=='DOCK_PURCHASE_CONFIRMED':
  state['purchases']+=1;state['purchased']+=details['quantity'];state['pending']=False;save()
if state['pending']:raise RuntimeError('Uncertain prior payment; do not retry')
while state['casts']<100:
 if state['remaining']==0:
  if state['purchases']>=2:raise RuntimeError('Maximum two bait purchases')
  o=detector.detect(real.screenshot())
  if o.state is not FishingState.READY:raise RuntimeError('Not ready before refill')
  real.tap(*o.matches['close'].center);time.sleep(1)
  c=InventoryController(d,ROOT/'dock-buy2',on_event=event)
  c.buy_dock_bait(50,c.wallet())
  observation=c.chest();(c.output/'inventory.json').write_text(json.dumps(observation,ensure_ascii=False,indent=2),encoding='utf-8')
  if observation['bait_stocks']['dock']!=50:raise RuntimeError('Refill stock not confirmed')
  state['remaining']=50;state['wallet']=observation['wallet'];save()
 rounds=min(state['remaining'],100-state['casts'])
 folder=ROOT/('bounded-'+str(state['casts']+1).zfill(3))
 result=FishingSession(d,SessionSettings(rounds=rounds),area='dock',output=folder).run()
 state['batches'].append({'folder':str(folder),**asdict(result)});save()
 if result.status!='COMPLETE':raise RuntimeError(result.reason)
state['status']='COMPLETE';save();cv2.imwrite(str(ROOT/'dock-100-complete.png'),real.screenshot())
print('BOUNDED_COMPLETE',state['casts'],state['purchases'],state['remaining'],flush=True)
