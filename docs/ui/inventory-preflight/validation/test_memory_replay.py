import ctypes,json,cv2
from ctypes import wintypes
from pathlib import Path
from fishing.detector import FishingDetector
from vision.matcher import find_template
class Counters(ctypes.Structure):
 _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
k=ctypes.WinDLL('kernel32');k.GetCurrentProcess.restype=wintypes.HANDLE
ps=ctypes.WinDLL('psapi');ps.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
def memory():
 c=Counters();c.cb=ctypes.sizeof(c);assert ps.GetProcessMemoryInfo(k.GetCurrentProcess(),ctypes.byref(c),c.cb);return c.PrivateUsage
image=cv2.imread('dist/AvatarFishingBot/debug/ui/2026-10-12_00-40-17_939990/error_screen.png');d=FishingDetector(area='ca_map')
for _ in range(5):d.detect(image)
samples=[memory()]
for n in range(100):
 d.detect(image)
 if n%10==9:samples.append(memory())
r={'frames':100,'private_bytes':samples,'growth_bytes':samples[-1]-samples[0]}
Path('docs/ui/inventory-preflight/validation/memory-replay.json').write_text(json.dumps(r,indent=2));print(r)
