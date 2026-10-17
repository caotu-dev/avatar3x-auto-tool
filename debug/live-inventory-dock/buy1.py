from pathlib import Path
import sys,json,cv2,time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings
from fishing.inventory import InventoryController
from fishing.detector import FishingDetector
from fishing.states import FishingState
s=Settings();d=AdbDevice(s.serial,s.adb_path)
a=d.screenshot();o=FishingDetector(area='dock').detect(a)
if o.state==FishingState.READY:d.tap(*o.matches['close'].center);time.sleep(1)
c=InventoryController(d,Path('debug/live-inventory-dock/dock-buy1'))
wallet=c.wallet();print(json.dumps(wallet),flush=True)
c.buy_dock_bait(50,wallet)
cv2.imwrite('debug/live-inventory-dock/after-buy1.png',d.screenshot())
