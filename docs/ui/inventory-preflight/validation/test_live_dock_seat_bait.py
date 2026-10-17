from pathlib import Path
import cv2,json
from config.settings import Settings,SessionSettings
from adb.device import AdbDevice
from fishing.navigation import MapNavigator
from fishing.inventory import InventoryController
from fishing.dock import DockController
from fishing.session import FishingSession
s=Settings();d=AdbDevice(s.serial,s.adb_path);p=Path('docs/ui/inventory-preflight/validation/live-dock-seat-bait');p.mkdir(parents=True,exist_ok=True)
prefs=json.loads(Path('dist/AvatarFishingBot/runtime/ui_preferences.json').read_text(encoding='utf-8'))
MapNavigator(d,output=p/'navigation').go('dock')
i=InventoryController(d,p/'inventory');state=i.chest();(p/'inventory.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');assert state['scan_complete']
stock=state['bait_stocks']['dock'];assert stock is not None
if stock==0:
 assert prefs.get('buy'), 'Auto buy disabled; no payment'
 qty=prefs.get('bait_quantity',50);assert 1<=qty<=50
 i.buy_dock_bait(qty,i.wallet())
ready=DockController(d,output=p/'seat',state_path=p/'dock.json').check();assert ready['status']=='READY',ready
result=FishingSession(d,SessionSettings(rounds=1),area='dock',output=p/'fishing').run()
(p/'result.json').write_text(json.dumps({'status':result.status,'reason':result.reason},ensure_ascii=False,indent=2),encoding='utf-8');print(result.status);cv2.imwrite(str(p/'after.png'),d.screenshot())
