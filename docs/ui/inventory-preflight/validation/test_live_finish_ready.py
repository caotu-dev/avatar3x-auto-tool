from pathlib import Path
from config.settings import Settings
from adb.device import AdbDevice
from fishing.session import FishingSession
import json
s=Settings();d=AdbDevice(s.serial,s.adb_path)
class ReadOnlyDevice:
 def screenshot(self):return d.screenshot()
 def tap(self,*args):raise AssertionError('Already ready: must not tap')
 def swipe(self,*args,**kwargs):raise AssertionError('Must not swipe')
p=Path('docs/ui/inventory-preflight/validation/live-finish-ready')
f=FishingSession(ReadOnlyDevice(),area='ca_map',recover_uncertain=True,output=p)
r=f._prepare_ready(after_round=True);assert r[0],r
(p/'result.json').write_text(json.dumps({'ready':r[0],'reason':r[1],'taps':0,'casts':0},ensure_ascii=False,indent=2),encoding='utf-8')
print(r)
