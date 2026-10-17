from pathlib import Path
import sys,time,cv2
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from config.settings import Settings
from adb.device import AdbDevice
from fishing.reconnect import ContinueScreen
s=Settings();d=AdbDevice(s.serial,s.adb_path);r=ContinueScreen()
d.tap(798,429)
end=time.monotonic()+8
while time.monotonic()<end:
 a=d.screenshot();p=r.detect(a)
 if p:break
 time.sleep(.2)
else:raise RuntimeError('Login not visible')
cv2.imwrite('debug/live-reconnect/logout.png',a)
d.tap(*p)
for i in range(5):
 time.sleep(.4)
 cv2.imwrite(f'debug/live-reconnect/login-step-{i}.png',d.screenshot())
