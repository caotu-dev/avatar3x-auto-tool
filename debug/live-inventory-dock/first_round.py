from pathlib import Path
import sys,cv2,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings,SessionSettings
from fishing.session import FishingSession
s=Settings();d=AdbDevice(s.serial,s.adb_path)
r=FishingSession(d,SessionSettings(rounds=1),area='dock',output=Path('debug/live-inventory-dock/trial-first')).run()
print(r,flush=True);cv2.imwrite('debug/live-inventory-dock/dock-first-result.png',d.screenshot())
