import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings
from fishing.inventory import InventoryController
s=Settings();d=AdbDevice(s.serial,s.adb_path)
c=InventoryController(d,Path('debug/live-inventory-dock/perch-owned-guard'))
a=c.buy_ticket('ca_ro',c.wallet())
assert a['scan_complete'] and a['tickets']['ca_ro']['status']=='active'
(c.output/'result.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
p=Path('debug/live-inventory-dock/perch-ticket/result.json')
p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(a,ensure_ascii=True))

