from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

AUTOMATIC_FOLDERS = frozenset(('ui','runs','trials','navigation','dock','tours','missions'))


def _automatic_destination(path):
    from config.settings import ROOT
    try:
        relative = Path(path).resolve().relative_to((ROOT/'debug').resolve())
    except ValueError:
        return False
    return bool(relative.parts and relative.parts[0] in AUTOMATIC_FOLDERS)


def save_event_screenshot(image, path, event, details=None):
    """Normal automation keeps text events; capture faults/payment evidence only.

    Detection still uses the original in-memory image. Explicit manual exports
    and recording outside automatic folders retain their existing behavior.
    """
    details = details or {}
    event = event.upper()
    capture = (
        any(marker in event for marker in ('ERROR','TIMEOUT','UNKNOWN','RETRY'))
        or event in ('WAIT_RESULT','RECOVER_RESULT','EXIT_CONFIRM','SALE_CONFIRMED',
                     'INVENTORY_TICKET','INVENTORY_BAIT','RECONNECT_COOLDOWN','OUT_OF_BAIT')
        or event.startswith('CANCEL_EXIT')
        or ('PURCHASE' in event and 'SKIPPED' not in event)
        or (event == 'STOP' and str(details.get('outcome',details.get('status',''))).upper()
            not in ('SUCCESS','COMPLETE','FAILED','OUT_OF_BAIT'))
    )
    if _automatic_destination(path) and not capture:
        from config.settings import ROOT
        from debug.retention import maybe_prune
        maybe_prune(ROOT/'debug')
        return None
    return save_debug_screenshot(image,path)

def decode_raw_screenshot(data: bytes) -> NDArray[np.uint8]:
    import struct
    if len(data)<12:raise ValueError('Ảnh ADB thô thiếu header')
    width,height,format_=struct.unpack_from('<III',data)
    if not (0<width<=8192 and 0<height<=8192) or format_ not in (1,2):
        raise ValueError('Định dạng ADB thô chưa hỗ trợ')
    offset=len(data)-width*height*4
    if offset not in (12,16):raise ValueError('Kích thước dữ liệu ADB thô không khớp')
    pixels=np.frombuffer(data,dtype=np.uint8,offset=offset).reshape(height,width,4)
    return cv2.cvtColor(pixels,cv2.COLOR_RGBA2BGR)


def decode_screenshot(data: bytes) -> NDArray[np.uint8]:
    if not data:
        raise ValueError("ADB trả về ảnh rỗng")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Không giải mã được ảnh chụp ADB")
    return image


def save_debug_screenshot(image: NDArray[np.uint8], path: str | Path) -> Path:
    destination = Path(path)
    from config.settings import ROOT
    try:
        relative=destination.resolve().relative_to((ROOT/'debug').resolve())
    except ValueError:
        relative=None
    if relative is not None and relative.parts and relative.parts[0] in AUTOMATIC_FOLDERS:
        # Three recent compressed frames per diagnostic folder, never inputs
        # used by OCR/template matching. Manual screenshot exports remain PNG.
        prefix=destination.stem.split('_')[0]
        slot=int(prefix)%3 if prefix.isdigit() else 0
        destination=destination.with_name(f'frame_{slot}.jpg')
    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix=destination.suffix.lower()
    success, encoded = cv2.imencode(suffix, image, [cv2.IMWRITE_JPEG_QUALITY,65] if suffix=='.jpg' else [])
    if not success:
        raise ValueError("Không mã hóa được ảnh PNG")
    destination.write_bytes(encoded.tobytes())
    if relative is not None and relative.parts and relative.parts[0] in AUTOMATIC_FOLDERS:
        from debug.retention import maybe_prune
        maybe_prune(ROOT/'debug', protected_paths=(destination,))
    return destination
