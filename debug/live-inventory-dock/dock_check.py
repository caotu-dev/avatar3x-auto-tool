from pathlib import Path
import sys,cv2,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings
from fishing.navigation import MapNavigator
from fishing.dock import DockController
s=Settings();d=AdbDevice(s.serial,s.adb_path)
MapNavigator(d,output=Path('debug/live-inventory-dock/navigation')).go('dock')
cv2.imwrite('debug/live-inventory-dock/dock-arrival.png',d.screenshot())
c=DockController(d,output=Path('debug/live-inventory-dock/dock-check'))
print(json.dumps(c.check(),ensure_ascii=True),flush=True)
cv2.imwrite('debug/live-inventory-dock/dock-check.png',d.screenshot())
