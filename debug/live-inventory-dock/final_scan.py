"""Fresh full inventory after the bounded test; refuses an unfinished ledger."""
from pathlib import Path
import sys,json,cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adb.device import AdbDevice
from config.settings import Settings
from fishing.inventory import InventoryController
ledger=json.loads(Path('debug/live-inventory-dock/bounded-ledger.json').read_text(encoding='utf-8'))
assert ledger['casts']==100 and ledger['status']=='COMPLETE' and ledger['purchases']==2
s=Settings();d=AdbDevice(s.serial,s.adb_path)
c=InventoryController(d,Path('debug/live-inventory-dock/final-chest'))
a=c.chest()
(c.output/'result.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(a,ensure_ascii=True))
