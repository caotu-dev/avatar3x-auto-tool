from pathlib import Path
import sys,json,cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings
from fishing.inventory import InventoryController
s=Settings();d=AdbDevice(s.serial,s.adb_path)
c=InventoryController(d,Path('debug/live-inventory-dock/chest2'))
try:
 result=c.chest();print(json.dumps(result,ensure_ascii=True),flush=True)
 (c.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
finally:cv2.imwrite('debug/live-inventory-dock/after-chest2.png',d.screenshot())
