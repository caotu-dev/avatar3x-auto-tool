"""Read fishing tasks and acknowledge verified completion rewards."""
import json
import re
import subprocess
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import cv2

from config.settings import ROOT
from fishing.catch import SPECIES
from vision.matcher import find_template
from vision.game_text import catalog_label

AREAS = {"ca_ro": "ca_ro", "ca_chep_vang": "ca_ro", "ca_long_tong": "ca_ro",
         "ca_noc": "ca_noc", "ca_loc": "ca_noc", "cua": "ca_noc",
         "ca_chim": "ca_map", "ca_duoi": "ca_map", "ca_ngua": "ca_map",
         "ca_vang": "dock", "ca_chep": "dock", "ca_he": "dock", "ca_lia_thia": "dock"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").split())


def parse_quest(lines: list[str]) -> dict:
    catalog = {normalize(name): (species, name) for species, name in SPECIES.items()}
    targets = []
    title = None
    for line in lines:
        plain = normalize(line)
        if "nhi" in plain and re.search(r"-\s*\d+", plain):
            title = line
        if re.match(r"phan\b", plain):
            break
        match = re.search(r"\b(\d+)\s+con\s+(.+?)\s*[-–]\s*(.+)$", plain)
        if not match:
            if re.search(r"\bcon\b", plain):
                raise ValueError(f"Không đọc đủ dòng nhiệm vụ: {line}")
            continue
        total = int(match[1])
        fish = re.sub(r"^ce\s+", "ca ", match[2])
        # Exact repeated OCR forms observed on the game's task-12 popup.
        fish = {'ca chep ving':'ca chep vang','ca 16c':'ca loc','ca n6c':'ca noc',
                'ca ngva':'ca ngua'}.get(fish,fish)
        status = match[3].strip()
        fraction = re.fullmatch(r"(\d+)\s*/\s*(\d+)", status)
        if status == "xong":
            current = total
        elif fraction and int(fraction[2]) == total:
            current = int(fraction[1])
        else:
            raise ValueError(f"Tiến độ chưa rõ: {line}")
        if total <= 0 or not 0 <= current <= total:
            raise ValueError(f"Số lượng không hợp lệ: {line}")
        species, name = catalog_label(fish,catalog) or (None, match[2])
        targets.append({"species": species, "name": name, "current": current,
                        "required": total, "completed": current == total,
                        "area": AREAS.get(species), "raw": line})
    if not targets or title is None:
        raise ValueError("Chưa đọc được tiêu đề và danh sách nhiệm vụ")
    return {"title_raw": title, "targets": targets,
            "completed": all(target["completed"] for target in targets),
            "claimed": False}


def read_ocr(path: Path) -> list[str]:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(ROOT / "vision/windows_ocr.ps1"), "-ImagePath", str(path.resolve())],
        capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError("Windows OCR thất bại: " + result.stderr.decode("utf-8", errors="replace"))
    payload = result.stdout.decode("utf-8-sig").strip()
    # No text can be visible while a dialog is transitioning. Let callers
    # continue their bounded observation loop rather than fail JSON decoding.
    if not payload:
        return []
    lines = json.loads(payload)
    return [lines] if isinstance(lines, str) else lines


class QuestReader:
    def __init__(self, device):
        self.device = device
        self.reward_acknowledged = False
        self.folder = ROOT / "debug/quests" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        self.folder.mkdir(parents=True, exist_ok=True)
        self.templates = {name: cv2.imread(str(ROOT / f"vision/templates/{name}.png"))
                          for name in ("quest_icon", "quest_current_button", "quest_title")}

    def match(self, screen, name):
        return find_template(screen, self.templates[name], threshold=.97)

    def wait(self, name):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            screen = self.device.screenshot()
            if self.dismiss_reward(screen):
                continue
            if name == 'quest_current_button' and self.match(screen,'quest_title'):
                return screen
            if self.match(screen, name):
                return screen
            time.sleep(.15)
        raise ValueError(f"Chưa thấy {name}; không bấm tiếp")

    def dismiss_reward(self, screen):
        """Only acknowledge the verified fishing-quest completion receipt."""
        from .world import WorldDetector
        world=WorldDetector()
        ok=world.match(screen,'ok')
        if ok is None:
            return False
        path=self.folder/'quest_reward.png'
        def verified(image):
            cv2.imwrite(str(path),image)
            plain=normalize(' '.join(read_ocr(path)))
            return all(word in plain for word in ('hoan thanh','nhi','nhan'))
        if not verified(screen):
            return False
        fresh=self.device.screenshot()
        button=world.match(fresh,'ok')
        if button is None or button.center != ok.center or not verified(fresh):
            raise ValueError('Thông báo thưởng nhiệm vụ chưa ổn định; chưa xác nhận.')
        self.device.tap(*button.center)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if world.match(self.device.screenshot(),'ok') is None:
                self.reward_acknowledged=True
                return True
            time.sleep(.15)
        raise ValueError('Chưa xác nhận đóng thưởng nhiệm vụ; không bấm lặp.')

    def read(self):
        screen = self.device.screenshot()
        if self.dismiss_reward(screen):
            screen=self.device.screenshot()
        if screen.shape != (900, 1600, 3):
            raise ValueError("Đọc nhiệm vụ hiện cần ảnh Android 1600x900")
        if not self.match(screen, "quest_title"):
            button = self.match(screen, "quest_current_button")
            if button is None:
                icon = self.match(screen, "quest_icon")
                if icon is None:
                    raise ValueError("Không thấy nút nhiệm vụ câu cá")
                self.device.tap(*icon.center)
                screen = self.wait("quest_current_button")
                button = self.match(screen, "quest_current_button")
            if button is not None:
                self.device.tap(*button.center)
                screen = self.wait("quest_title")
        snapshots = []
        for index in range(2):
            if index:
                screen = self.wait("quest_title")
            path = self.folder / f"quest_{index}.png"
            cv2.imwrite(str(path), screen)
            state=parse_quest(read_ocr(path))
            if any(t['species'] is None for t in state['targets']):
                # Read only the popup's blue lettering on a clean background.
                crop=screen[200:800,220:1375]
                mask=cv2.inRange(cv2.cvtColor(crop,cv2.COLOR_BGR2HSV),(85,80,65),(120,255,255))
                clean=cv2.resize(255-mask,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
                retry=self.folder/f'quest_{index}_clean.png'
                cv2.imwrite(str(retry),cv2.copyMakeBorder(clean,15,15,15,15,cv2.BORDER_CONSTANT,value=255))
                try:
                    candidate=parse_quest(read_ocr(retry))
                    if [(t['current'],t['required']) for t in candidate['targets']]==[(t['current'],t['required']) for t in state['targets']] and all(t['species'] for t in candidate['targets']):
                        state=candidate
                except ValueError:
                    pass
            snapshots.append(state)
        def identity(state):
            number=re.search(r'-\s*(\d+)\s*:?\s*$',normalize(state['title_raw']))
            return (number[1] if number else normalize(state['title_raw']),
                    [(t['species'], t['name'] if t['species'] is None else None,t['current'],t['required']) for t in state['targets']])
        if identity(snapshots[0]) != identity(snapshots[1]):
            raise ValueError("Nhiệm vụ thay đổi giữa hai ảnh; chưa lưu state")
        state = snapshots[1]
        if self.reward_acknowledged:
            state['reward_acknowledged']=True
        state.update({"observed_at": datetime.now(timezone.utc).isoformat(),
                      "source_image": str(path), "source": "game_quest_popup"})
        destination = ROOT / "runtime/game_quest.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(destination)
        return state


def read_ocr_boxes(path: Path) -> list[dict]:
    """OCR text positions, without changing existing quest OCR semantics."""
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
         str(ROOT / 'vision/windows_ocr.ps1'), '-ImagePath', str(path.resolve()), '-IncludeBoxes'],
        capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('Windows OCR vị trí thất bại: ' + result.stderr.decode('utf-8', errors='replace'))
    payload = result.stdout.decode('utf-8-sig').strip()
    parsed = json.loads(payload) if payload else []
    return [parsed] if isinstance(parsed, dict) else parsed
