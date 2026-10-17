from pathlib import Path
import json,cv2
from config.settings import Settings
from adb.device import AdbDevice
from fishing.inventory import InventoryController
s=Settings();d=AdbDevice(s.serial,s.adb_path)
p=Path('docs/ui/inventory-preflight/validation/live-shark');i=InventoryController(d,p)
state=i.chest();(p/'before.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
assert state['scan_complete'],state
result=i.buy_ticket('ca_map',state['wallet'],observation=state)
(p/'after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
cv2.imwrite(str(p/'after.png'),d.screenshot())
print(json.dumps(result,ensure_ascii=True))
