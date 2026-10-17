from pathlib import Path
import cv2,json
from config.settings import Settings
from adb.device import AdbDevice
from fishing.reconnect import ContinueScreen,ReconnectController
from fishing.navigation import MapNavigator
s=Settings();d=AdbDevice(s.serial,s.adb_path);p=Path('docs/ui/inventory-preflight/validation/live-dark-login');nav=MapNavigator(d,output=p/'navigation');r=ReconnectController(d,p)
result=r.recover(ContinueScreen(),lambda image:nav.is_world(image) or nav.location(image) is not None or nav.world.map_name(image,require_menu=False) is not None)
(p/'result.json').write_text(json.dumps(result,indent=2));cv2.imwrite(str(p/'after.png'),d.screenshot());print(result)
