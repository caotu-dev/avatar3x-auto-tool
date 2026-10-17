"""Purchase just the missing perch ticket, never cast or purchase an owned ticket."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings
from fishing.inventory import InventoryController
from fishing.navigation import MapNavigator
ledger=json.loads(Path('debug/live-inventory-dock/bounded-ledger.json').read_text(encoding='utf-8'))
assert ledger['casts']==100 and ledger['status']=='COMPLETE'
s=Settings();d=AdbDevice(s.serial,s.adb_path)
MapNavigator(d,Path('debug/live-inventory-dock/return-ecological')).go('fishing')
c=InventoryController(d,Path('debug/live-inventory-dock/perch-ticket'))
a=c.chest()
(c.output/'before.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
if a['tickets']['ca_ro']['status']=='missing' and a['scan_complete']:
 a=c.buy_ticket('ca_ro',a['wallet'])
else:
 assert a['tickets']['ca_ro']['status']=='active','Unknown ticket: no purchase'
(c.output/'result.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(a,ensure_ascii=True))
