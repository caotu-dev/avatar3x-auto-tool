from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config.settings import Settings
from adb.device import AdbDevice
from fishing.navigation import MapNavigator
from fishing.inventory import InventoryController
s=Settings();d=AdbDevice(s.serial,s.adb_path)
out=Path('debug/chest-selection-live')
MapNavigator(d,out/'navigation').go('fishing')
class ReadOnlyChest:
 dropped=False
 def screenshot(self):return d.screenshot()
 def swipe(self,*a):return d.swipe(*a)
 def tap(self,x,y):
  assert x<180 or x>1450 or (450<x<1140 and 310<y<760),'Only chest/menu inputs allowed'
  if 450<x<1140 and not self.dropped:
   self.dropped=True;return
  d.tap(x,y)
proxy=ReadOnlyChest()
result=InventoryController(proxy,out/'inventory').chest()
assert result['scan_complete'],result
assert result['tickets']['ca_noc']['status']=='active',result
result['intentionally_dropped_first_selection']=proxy.dropped
(out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
