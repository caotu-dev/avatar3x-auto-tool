from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from config.settings import ROOT
from vision.matcher import MatchResult, ROI, find_template
from vision.layout import find_target_board
from .states import FishingState


@dataclass(frozen=True)
class Detection:
    state: FishingState
    matches: dict[str, MatchResult]
    scene_confirmed: bool = False


class FishingDetector:
    """MVP chỉ nhận ảnh 1600x900; trạng thái không đủ bằng chứng là UNKNOWN."""

    REGIONS = {
        "no_bait": ROI(.20, .18, .60, .50),
        "idle_menu": ROI(.0, .0, .14, .18),
        "exit_question": ROI(.35, .42, .30, .12),
        "exit_no": ROI(.52, .56, .16, .12),
        "toss": ROI(.40, .87, .18, .12),
        "close": ROI(.84, .87, .15, .12),
        "finish": ROI(.84, .87, .15, .12),
        "success": ROI(.30, .08, .40, .28),
        "timer": ROI(.30, .77, .40, .07),
        "miss": ROI(.66, .30, .18, .60),
    }
    CHAIR_REGIONS = tuple(ROI(.72, (y - 35) / 900, .07, 70 / 900)
                          for y in (566, 639, 711, 784))

    def __init__(self, templates_path: Path = ROOT / "vision" / "templates", area: str = "ca_ro"):
        self.area = area
        self.loading_template = cv2.imread(str(templates_path / 'loading_vi.png'),cv2.IMREAD_GRAYSCALE)
        seated_loading=templates_path/'loading_seated_vi.png'
        self.seated_loading_template=cv2.imread(str(seated_loading),cv2.IMREAD_GRAYSCALE) if seated_loading.exists() else None
        self.dock_detector=None
        if area=='dock':
            from .dock import DockDetector
            self.dock_detector=DockDetector()
        self.exit_question_reference = cv2.imread(str(templates_path / 'reconnect/exit_question.png'))
        menu_path = templates_path / 'world/menu.png'
        self.menu_template = cv2.imread(str(menu_path), cv2.IMREAD_GRAYSCALE) if menu_path.exists() else None
        self.room_sign_template = cv2.imread(str(templates_path / 'world/room_sign.png'), cv2.IMREAD_GRAYSCALE)
        self.templates = {}
        for name in self.REGIONS:
            path = templates_path / f"{name}.png"
            if not path.is_file():
                raise ValueError(f"Thiếu ảnh mẫu: {path}")
            image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"Ảnh mẫu hỏng: {path}")
            self.templates[name] = image
        self.localized_templates = {}
        for name in self.REGIONS:
            path = templates_path / f"{name}_vi.png"
            if path.is_file():
                image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise ValueError(f"Ảnh mẫu hỏng: {path}")
                self.localized_templates[name] = image
        self.no_bait_templates = [cv2.cvtColor(self.templates["no_bait"], cv2.COLOR_BGR2GRAY)]
        dock_bait=templates_path/'no_bait_dock.png'
        if dock_bait.exists():
            self.no_bait_templates.append(cv2.imread(str(dock_bait),cv2.IMREAD_GRAYSCALE))
        reference_path = templates_path / "no_bait_reference.png"
        if reference_path.is_file():
            reference = cv2.imdecode(np.frombuffer(reference_path.read_bytes(), np.uint8),
                                     cv2.IMREAD_GRAYSCALE)
            if reference is None:
                raise ValueError(f"Ảnh mẫu hỏng: {reference_path}")
            self.no_bait_templates.append(reference)
        self.no_bait_variants = [cv2.resize(template, None, fx=scale, fy=scale)
                                for template in self.no_bait_templates
                                for scale in (.95, 1.0, 1.075)]
        self.localized_gray = {name: cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                               for name, template in self.localized_templates.items()}
        self.miss_masks = {name: cv2.inRange(cv2.cvtColor(template, cv2.COLOR_BGR2HSV),
                                           (22, 160, 140), (35, 255, 255))
                           for name, template in [('base', self.templates['miss']),
                                                  *self.localized_templates.items()] if name in ('base', 'miss')}
        self.chair_templates = []
        for name in ("chair_top", "chair_bottom"):
            path = templates_path / f"{name}.png"
            image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise ValueError(f"Ảnh mẫu hỏng: {path}")
            # Mặt trên ghế ít bị tên nhân vật và vật nuôi che hơn phần chân ghế.
            self.chair_templates.append(image[:15])
        for specific_chair in templates_path.glob(f"chair_{area}*.png"):
            image = cv2.imdecode(np.frombuffer(specific_chair.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)
            if image is not None:
                self.chair_templates.append(image[:15])

    def interruption(self, screen: NDArray[np.uint8]) -> Detection | None:
        """Cheap scene-independent guard for navigation/shop waits."""
        if screen.shape != (900, 1600, 3):
            return None
        gray=cv2.cvtColor(screen,cv2.COLOR_BGR2GRAY)
        for template in (self.loading_template,self.seated_loading_template):
            if template is not None:
                match=find_template(gray,template,threshold=.98,
                                    roi=ROI(.25,.35,.5,.3),contrast_invariant=True)
                if match:return Detection(FishingState.LOADING,{'loading':match})
        matches={}
        for name in ('exit_no','exit_question'):
            for template in (self.templates[name],self.localized_templates.get(name)):
                if template is None:continue
                match=find_template(gray,cv2.cvtColor(template,cv2.COLOR_BGR2GRAY),
                                    threshold=.98,roi=self.REGIONS[name],contrast_invariant=True)
                if match:
                    matches[name]=match
                    break
            if name=='exit_no' and name not in matches:return None
        if 'exit_question' not in matches and self.exit_question_reference is not None:
            question=find_template(cv2.resize(screen,(824,463)),self.exit_question_reference,threshold=.94)
            if question is not None:
                matches['exit_question']=MatchResult(round(question.x*1600/824),round(question.y*900/463),
                    round(question.width*1600/824),round(question.height*900/463),question.confidence)
        if 'exit_question' in matches:
            return Detection(FishingState.EXIT_CONFIRM,matches)
        return None

    def detect(self, screen: NDArray[np.uint8]) -> Detection:
        if screen.shape != (900, 1600, 3):
            return Detection(FishingState.UNKNOWN, {})
        matches = {}
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        board_checked = False
        board = None
        def target_board():
            nonlocal board_checked, board
            if not board_checked:
                board = find_target_board(screen)
                board_checked = True
            return board
        loading = find_template(gray,self.loading_template,threshold=.98,
                                roi=ROI(.25,.35,.5,.3),contrast_invariant=True) if self.loading_template is not None else None
        if loading is None and self.seated_loading_template is not None:
            loading=find_template(gray,self.seated_loading_template,threshold=.98,
                                  roi=ROI(.25,.35,.5,.3),contrast_invariant=True)
        if loading is not None:
            return Detection(FishingState.LOADING,{'loading':loading})
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        yellow_mask = cv2.inRange(hsv, (22, 160, 140), (35, 255, 255))
        for name, template in self.templates.items():
            if name == "miss":
                # Tách chữ vàng khỏi nền thay đổi khi thông báo bay lên.
                match = find_template(yellow_mask, self.miss_masks['base'], threshold=.94, roi=self.REGIONS[name])
            elif name == "no_bait":
                # Giữ cả mẫu ADB sắc nét và mẫu cửa sổ cũ có tỉ lệ font khác.
                candidates = [find_template(gray, gray_template, threshold=.90, roi=self.REGIONS[name],
                              contrast_invariant=True)
                              for gray_template in self.no_bait_variants]
                found = [candidate for candidate in candidates if candidate is not None]
                match = max(found, key=lambda candidate: candidate.confidence) if found else None
            else:
                match = find_template(screen, template, threshold=.98, roi=self.REGIONS[name])
            if match:
                matches[name] = match
        for name, template in self.localized_templates.items():
            if name == "miss":
                match = find_template(yellow_mask, self.miss_masks[name], threshold=.94, roi=self.REGIONS[name])
                if match:
                    matches[name] = match
                continue
            # Nền vàng chiếm phần lớn nút: so tương quan chữ để phân biệt Đóng/Xong.
            match = find_template(gray, self.localized_gray[name],
                                  threshold=.98, roi=self.REGIONS[name], contrast_invariant=True)
            if match:
                matches[name] = match
        if 'idle_menu' not in matches and self.menu_template is not None:
            menu = find_template(gray, self.menu_template, threshold=.98,
                                 roi=self.REGIONS['idle_menu'], contrast_invariant=True)
            if menu:
                matches['idle_menu'] = menu
        if self.area == 'dock':
            # Dock boats replace all ecology chair matches below. Do not spend
            # time finding chairs that cannot affect the returned detection.
            chair_regions = ()
        elif self.area == "ca_noc":
            chair_regions = tuple(ROI(.67, (y - 30) / 900, .075, 60 / 900) for y in (496, 570, 644))
            # Changing rooms can center a different pier. Derive both sides from
            # the visible sign instead of assuming a fixed camera offset.
            # Two visually identical signs can have scores differing only by
            # floating-point noise on different CPUs. Inspect both banks and
            # select by verified chairs, rather than the highest sign score.
            signs = []
            if self.room_sign_template is not None:
                for region in (ROI(0,0,.55,1),ROI(.45,0,.55,1)):
                    sign=find_template(gray,self.room_sign_template,threshold=.98,
                                       roi=region,contrast_invariant=True)
                    if sign is not None and (sign.x,sign.y) not in {(s.x,s.y) for s in signs}:
                        signs.append(sign)
            sign_groups = []
            for sign in signs:
                regions = tuple(ROI((sign.center[0]+dx-55)/1600,
                                    (sign.y+dy-25)/900,110/1600,65/900)
                                for dx in (-140,145) for dy in (142,215,288))
                sign_groups.append(tuple(r for r in regions
                                   if 0 <= r.x and r.x+r.width <= 1 and 0 <= r.y and r.y+r.height <= 1))
        elif self.area == "ca_map":
            chair_regions = tuple(ROI(x, (y - 30) / 900, .075, 60 / 900)
                                  for x in (.70, .34) for y in (574, 645, 716))
        else:
            chair_regions = self.CHAIR_REGIONS
        chair_groups = sign_groups if self.area == 'ca_noc' and sign_groups else (chair_regions,)
        verified_chairs = {}
        for regions in chair_groups:
            group = {}
            for index, roi in enumerate(regions):
                candidates = [find_template(gray, template, threshold=.94, roi=roi,
                                            contrast_invariant=True)
                              for template in self.chair_templates]
                found = [match for match in candidates if match is not None]
                if found:
                    group[f"chair_{index + 1}"] = max(found, key=lambda match: match.confidence)
            if len(group) > len(verified_chairs):
                verified_chairs = group
        matches.update(verified_chairs)
        pond = screen[515:700, 330:400] if self.area == "ca_noc" else screen[558:756, 80:400]
        pond_hsv = cv2.cvtColor(pond, cv2.COLOR_BGR2HSV)
        water = cv2.inRange(pond_hsv, (80, 60, 35), (115, 255, 255))
        # Người chơi có thể che toàn bộ ghế. Nhãn đỏ là bằng chứng phụ,
        # vẫn cần nước và điều khiển câu cá đúng vị trí; không dùng tên để chọn ghế.
        label_region = (screen[400:750, 1030:1240] if self.area == "ca_noc"
                        else screen[400:780, 500:1270] if self.area == "ca_map"
                        else screen[400:750, 1100:1310])
        label_hsv = cv2.cvtColor(label_region, cv2.COLOR_BGR2HSV)
        red = (cv2.inRange(label_hsv, (0, 120, 100), (12, 255, 255))
               | cv2.inRange(label_hsv, (170, 120, 100), (179, 255, 255)))
        label = np.count_nonzero(np.count_nonzero(red, axis=1) >= 40) >= 5
        fishing_controls = any(name in matches for name in ("close", "finish", "timer"))
        scene = (float(np.count_nonzero(water)) / water.size > .80
                 and (sum(name.startswith("chair_") for name in matches) >= (1 if self.area == "ca_ro" else 2)
                      or (label and fishing_controls)))
        if (not scene and self.area == 'ca_ro' and label
                and 'toss' in matches and 'close' in matches):
            # Players/pets can cover the upper pond sample while both native
            # fishing buttons remain visible. Require an independent lower
            # water sample as well as substantial water in the original sample.
            lower_water = cv2.inRange(cv2.cvtColor(screen[700:795, 80:400], cv2.COLOR_BGR2HSV),
                                     (80, 60, 35), (115, 255, 255))
            scene = (float(np.mean(water > 0)) > .60 and
                     float(np.mean(lower_water > 0)) > .90)
        if self.area == "ca_map":
            sea = cv2.inRange(cv2.cvtColor(screen[558:756, 1250:1380], cv2.COLOR_BGR2HSV),
                             (80, 60, 35), (115, 255, 255))
            scene = (np.count_nonzero(water) / water.size > .80
                     and np.count_nonzero(sea) / sea.size > .80
                     and (any(name.startswith("chair_") for name in matches) or label))
            # Người ngồi ghế trái có thể che đầu thanh thời gian và nhãn đỏ.
            # Có thể nhận trạng thái để chờ kết quả khi mép bảng bị che;
            # solver vẫn cần đo đầy đủ bảng trước khi gửi thao tác.
            # Đo mép dưới; các ô đã ghép sáng lên nên không đo cả mặt bảng.
            board_value = cv2.cvtColor(screen[658:666, 650:950], cv2.COLOR_BGR2HSV)[:, :, 2]
            if scene and "timer" not in matches and np.mean(board_value < 150) > .6:
                orange = cv2.inRange(cv2.cvtColor(screen[714:728, 520:1080], cv2.COLOR_BGR2HSV),
                                     (5, 150, 120), (30, 255, 255))
                # Nút tròn đang chạy chia thanh thành hai đoạn ngắn hơn 300 px.
                orange = cv2.morphologyEx(orange, cv2.MORPH_CLOSE, np.ones((1, 35), np.uint8))
                panel = cv2.cvtColor(screen[350:800, 1400:1408], cv2.COLOR_BGR2HSV)[:, :, 2]
                for contour in cv2.findContours(orange, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
                    x, y, width, height = cv2.boundingRect(contour)
                    if width > 300 and height >= 3 and np.mean(panel < 150) > .8:
                        matches["timer"] = MatchResult(520 + x, 714 + y, width, height, 1.)
                        break
        if self.area == 'dock':
            dock = self.dock_detector.detect(screen, gray=gray)
            scene = bool(dock.confirmed and not dock.level_locked and not dock.room_menu)
            matches = {key:value for key,value in matches.items() if not key.startswith('chair_')}
            # Convert the verified boat edge to the existing session chair interface.
            for index,boat in enumerate(sorted(dock.boats,key=lambda b:b.y)):
                px,py=boat.x+boat.width-3,boat.y+boat.height-15
                matches[f'chair_{index+1}']=MatchResult(px-1,py-16,2,2,boat.confidence)
            if scene and 'timer' not in matches and target_board() is not None:
                orange=cv2.inRange(hsv[714:728,520:1080],(5,150,120),(30,255,255))
                orange=cv2.morphologyEx(orange,cv2.MORPH_CLOSE,np.ones((1,35),np.uint8))
                panel=hsv[350:800,1400:1408,2]
                for contour in cv2.findContours(orange,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
                    x,y,width,height=cv2.boundingRect(contour)
                    if width>300 and height>=3 and np.mean(panel<150)>.8:
                        matches['timer']=MatchResult(520+x,714+y,width,height,1.)
                        break
        if self.area in ('ca_noc','ca_ro') and target_board() is not None:
            # The camera can center the other bank and hide all chair/name
            # anchors. Require independent board, timer, source panel and water.
            orange=cv2.inRange(hsv[714:728,520:1080],(5,150,120),(30,255,255))
            orange=cv2.morphologyEx(orange,cv2.MORPH_CLOSE,np.ones((1,35),np.uint8))
            panel=hsv[350:800,1400:1408,2]
            if np.mean(panel<150)>.8 and np.mean(water>0)>.8:
                for contour in cv2.findContours(orange,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
                    x,y,width,height=cv2.boundingRect(contour)
                    if width>300 and height>=3:
                        matches['timer']=MatchResult(520+x,714+y,width,height,1.)
                        scene=True
                        break
        if 'exit_no' in matches and 'exit_question' not in matches and self.exit_question_reference is not None:
            normalized = cv2.resize(screen, (824, 463))
            question = find_template(normalized, self.exit_question_reference, threshold=.94)
            if question is not None:
                matches['exit_question'] = MatchResult(
                    round(question.x * 1600 / 824), round(question.y * 900 / 463),
                    round(question.width * 1600 / 824), round(question.height * 900 / 463), question.confidence)
        if "no_bait" in matches:
            state = FishingState.OUT_OF_BAIT
        elif "exit_question" in matches and "exit_no" in matches:
            state = FishingState.EXIT_CONFIRM
        elif "success" in matches:
            state = FishingState.SUCCESS
        elif "timer" in matches and scene and target_board() is not None:
            # Miss của người khác không kết thúc bảng ghép đang hoạt động của mình.
            state = FishingState.FISHING
        elif "miss" in matches and "finish" in matches and scene:
            state = FishingState.FAILED
        elif "timer" in matches and scene:
            state = FishingState.FISHING
        elif "finish" in matches and scene:
            state = FishingState.RESULT
        elif "toss" in matches and "close" in matches and scene:
            state = FishingState.READY
        elif "close" in matches and scene:
            state = FishingState.WAITING
        elif (scene and "idle_menu" in matches
              and sum(name.startswith("chair_") for name in matches) >= (1 if self.area in ("ca_map", "ca_ro", "dock") else 2)
              and (self.area == 'dock' or float(np.mean(pond_hsv[:, :, 2])) > 120)):
            state = FishingState.IDLE
        else:
            state = FishingState.UNKNOWN
        return Detection(state, matches, scene)
