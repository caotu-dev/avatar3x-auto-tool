from pathlib import Path
import sys,cv2,json,time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings,SessionSettings
from fishing.session import FishingSession
from fishing.dock import DockDetector
s=Settings();d=AdbDevice(s.serial,s.adb_path)
a=d.screenshot()
if not DockDetector().detect(a).confirmed:raise RuntimeError('not dock')
if not DockDetector().detect(a).room_sign:d.swipe(300,520,1350,520,400);time.sleep(1)
r=FishingSession(d,SessionSettings(rounds=1),area='dock',output=Path('debug/live-inventory-dock/trial-second')).run()
from dataclasses import asdict
print(json.dumps(asdict(r),ensure_ascii=True),flush=True)
cv2.imwrite('debug/live-inventory-dock/dock-second-result.png',d.screenshot())
