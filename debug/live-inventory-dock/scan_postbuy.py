from pathlib import Path
import sys,json,cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings
from fishing.inventory import InventoryController
s=Settings();d=AdbDevice(s.serial,s.adb_path)
c=InventoryController(d,Path('debug/live-inventory-dock/post-buy1'))
a=c.buy_ticket('dock',c.wallet())
print(json.dumps(a,ensure_ascii=True),flush=True)
(c.output/'result.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
cv2.imwrite('debug/live-inventory-dock/after-postbuy-scan.png',d.screenshot())
