from pathlib import Path
import sys,json,time,cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config.settings import Settings
from adb.device import AdbDevice
from fishing.detector import FishingDetector
from fishing.session import FishingSession
s=Settings();real=AdbDevice(s.serial,s.adb_path);detector=FishingDetector(area='ca_noc')
loading=cv2.imread('tests/fixtures/loading_vi.png')
class NoOnly:
 frames=0;taps=[]
 def screenshot(self):
  self.frames+=1
  return loading if self.frames<=3 else real.screenshot()
 def tap(self,x,y):
  observed=detector.detect(real.screenshot())
  assert 'exit_no' in observed.matches and observed.matches['exit_no'].center==(x,y)
  assert not self.taps
  self.taps.append((x,y));real.tap(x,y)
proxy=NoOnly();out=Path('debug/loading-exit-live')
session=FishingSession(proxy,detector=detector,area='ca_noc',output=out)
session.started=time.monotonic();ready,reason=session._prepare_ready(after_round=True)
observed=detector.detect(real.screenshot())
result={'ready':ready,'reason':reason,'taps':proxy.taps,'replayed_real_loading_frames':3,'casts':0,'purchases':0,
        'resumed_state':observed.state.name,'scene_confirmed':observed.scene_confirmed,
        'popup_closed':'exit_question' not in observed.matches}
Path('docs/ui/inventory-preflight/validation/live-loading-exit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
assert len(proxy.taps)==1 and result['popup_closed'] and observed.scene_confirmed
