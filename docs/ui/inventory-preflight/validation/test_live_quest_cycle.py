from pathlib import Path
import json,cv2
from config.settings import Settings
from adb.device import AdbDevice
from fishing.navigation import MapNavigator
from fishing.quest import QuestReader
s=Settings();d=AdbDevice(s.serial,s.adb_path);p=Path('docs/ui/inventory-preflight/validation/live-quest-cycle');p.mkdir(parents=True,exist_ok=True)
from vision.matcher import find_template
current=d.screenshot()
reference=cv2.imread('docs/ui/inventory-preflight/validation/quest-cycle-navigation.png')
if find_template(current,reference[185:350,600:1060],threshold=.97) is not None:
 d.back()
 import time;time.sleep(.5)
MapNavigator(d,output=p/'navigation_retry').go('fishing')
reader=QuestReader(d);q=reader.read();(p/'quest.json').write_text(json.dumps(q,ensure_ascii=False,indent=2),encoding='utf-8');cv2.imwrite(str(p/'quest.png'),d.screenshot());print(json.dumps(q,ensure_ascii=True))
if reader.match(d.screenshot(),'quest_title'):d.tap(160,650)
