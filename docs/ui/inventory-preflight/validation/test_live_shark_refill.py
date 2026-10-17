from pathlib import Path
from config.settings import Settings
from adb.device import AdbDevice
from fishing.travel import TravelController
import cv2,json
s=Settings();d=AdbDevice(s.serial,s.adb_path);p=Path('docs/ui/inventory-preflight/validation/live-shark-refill');t=TravelController(d,p)
t.center('ca_map');t.open_shop();cv2.imwrite(str(p/'shop-open.png'),d.screenshot())
(p/'result.json').write_text(json.dumps({'center_and_shop':True,'purchases':0,'casts':0}),encoding='utf-8')
t.tap((200,650),'Đóng menu shop sau kiểm thử')
