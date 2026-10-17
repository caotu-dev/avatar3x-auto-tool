from pathlib import Path
import sys,cv2,json,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config.settings import Settings
from adb.device import AdbDevice
from fishing.detector import FishingDetector
from fishing.session import FishingSession
s=Settings();real=AdbDevice(s.serial,s.adb_path);detector=FishingDetector(area='ca_noc')
out=Path('debug/shifted-seat-live');out.mkdir(exist_ok=True)
cv2.imwrite(str(out/'before.png'),real.screenshot())
class SeatOnly:
 taps=[]
 def screenshot(self):return real.screenshot()
 def tap(self,x,y):
  observed=detector.detect(real.screenshot())
  allowed=[(m.center[0],m.center[1]+15) for k,m in observed.matches.items() if k.startswith('chair_')]
  assert (x,y) in allowed,'Only freshly verified seats allowed'
  assert not self.taps,'One seat tap maximum'
  self.taps.append((x,y));real.tap(x,y)
proxy=SeatOnly();session=FishingSession(proxy,detector=detector,area='ca_noc',output=out)
session.started=time.monotonic();ready,reason=session._prepare_ready()
cv2.imwrite(str(out/'after.png'),real.screenshot())
result={'ready':ready,'reason':reason,'seat_taps':proxy.taps,'casts':0,'purchases':0}
(out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True));assert ready
