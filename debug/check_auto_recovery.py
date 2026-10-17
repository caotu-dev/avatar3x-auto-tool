from pathlib import Path
import sys,cv2,time,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config.settings import Settings
from adb.device import AdbDevice
from fishing.bot import OneRoundBot
from fishing.detector import FishingDetector
from fishing.session import FishingSession
s=Settings();real=AdbDevice(s.serial,s.adb_path);d=FishingDetector(area='ca_noc')
unknown=cv2.imread('dist/AvatarFishingBot/debug/ui/2026-10-11_21-33-18_466398/round_0054/round_001/006_STOP.png')
class ReadResult:
 frames=0;taps=[]
 def screenshot(self):
  self.frames+=1
  assert self.frames<30,'Bound live validation'
  return unknown if self.frames<=2 else real.screenshot()
 def tap(self,x,y):
  observed=d.detect(real.screenshot())
  assert 'finish' in observed.matches and observed.matches['finish'].center==(x,y)
  assert not self.taps;self.taps.append((x,y));real.tap(x,y)
proxy=ReadResult();out=Path('debug/auto-recovery-live')
bot=OneRoundBot(proxy,detector=d,area='ca_noc',output=out/'round',recover_uncertain=True)
bot.started=time.monotonic();bot.casts=1;bot.drags=1;bot.confirmed=1
result=bot.wait_for_result('Test khôi phục sau nhận diện bảng không chắc')
session=FishingSession(proxy,detector=d,area='ca_noc',output=out/'cleanup')
session.started=time.monotonic();ready,reason=session._prepare_ready(after_round=True)
summary={'outcome':result.outcome,'ready':ready,'cleanup':reason,'actual_taps':proxy.taps,'additional_casts':0,'purchases':0}
Path('docs/ui/inventory-preflight/validation/live-auto-recovery.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True));assert ready
