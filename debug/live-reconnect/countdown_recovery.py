from pathlib import Path
import sys,time,cv2,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from config.settings import Settings
from adb.device import AdbDevice
from fishing.navigation import MapNavigator
from fishing.reconnect import ContinueScreen,ReconnectController
s=Settings();d=AdbDevice(s.serial,s.adb_path);r=ContinueScreen();n=MapNavigator(d)
if r.detect(d.screenshot()):
 ReconnectController(d,Path('debug/live-reconnect/initial-resume')).recover(r,n.is_world)
n.open_world();m=n.match(d.screenshot(),'world_menu');assert m
d.tap(*m.center);time.sleep(.5);d.tap(798,429)
end=time.monotonic()+8
while time.monotonic()<end:
 if r.detect(d.screenshot()):break
 time.sleep(.2)
else:raise RuntimeError('Login not visible')
class Guard:
 taps=0;blocked_frames=0
 def screenshot(self):
  a=d.screenshot()
  if r.blocked(a):self.blocked_frames+=1
  return a
 def tap(self,x,y):
  a=d.screenshot();assert not r.blocked(a)
  assert r.detect(a)==(x,y);self.taps+=1;assert self.taps<=3
  d.tap(x,y)
g=Guard();out=Path('debug/live-reconnect/countdown');start=time.monotonic()
result=ReconnectController(g,out).recover(r,n.is_world)
result.update(seconds=round(time.monotonic()-start,2),blocked_frames=g.blocked_frames,taps=g.taps)
(out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(result)
