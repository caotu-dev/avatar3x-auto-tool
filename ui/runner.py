"""Worker cho giao diện; mọi thao tác ADB chạy ngoài luồng Tk."""
import json
import copy
import threading
import time
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime

from adb.device import AdbDevice
from config.settings import ROOT, Settings, SessionSettings, TrialSettings
from fishing.inventory import InventoryController, TICKETS, BAITS, ensure_funds
from fishing.catch import SPECIES
from fishing.detector import FishingDetector
from fishing.dock import DockController, DockDetector
from fishing.navigation import MapNavigator
from fishing.quest import QuestReader, AREAS
from fishing.session import FishingSession
from fishing.travel import TravelController
from fishing.bot import OneRoundBot
from fishing.reconnect import ContinueScreen, SessionLost, ReconnectController
from fishing.rooms import RoomSwitcher
from fishing.solver import FishingSolver
from ui import state_cache

AREAS_UI = {'Khu cá rô': 'ca_ro', 'Khu cá lóc / cá nóc': 'ca_noc',
            'Khu cá mập': 'ca_map', 'Khu bến tàu': 'dock'}


@dataclass(frozen=True)
class Options:
    mission: bool = False
    free: bool = False
    area: str = ''
    buy: bool = False
    sell: bool = False
    bait_quantity: int = 50
    custom_targets: tuple[tuple[str, int], ...] = ()
    midnight_sale: bool = True
    auto_tickets: tuple[str, ...] = ()

    auto_resume: bool = False
    resume_limit: int = 3

    def validate(self):
        if type(self.resume_limit) is not int or not 1 <= self.resume_limit <= 20:
            raise ValueError('Số lần tự tiếp tục phải từ 1 đến 20')
        if any(key not in TICKETS for key in self.auto_tickets):
            raise ValueError("Loại vé tự mua không hợp lệ")
        if type(self.bait_quantity) is not int or not 1 <= self.bait_quantity <= 50:
            raise ValueError('Số mồi phải từ 1 đến 50')
        if self.mission and self.free:
            raise ValueError('Chỉ chọn một chế độ câu')
        if self.custom_targets:
            if self.mission or self.free:
                raise ValueError('Chỉ chọn một chế độ câu')
            species = [s for s, _ in self.custom_targets]
            if len(set(species)) != len(species) or any(s not in AREAS or type(n) is not int or n <= 0 for s, n in self.custom_targets):
                raise ValueError('Mục tiêu tự đặt không hợp lệ')
            return
        if not self.mission and not self.free:
            raise ValueError('Chọn Tự động làm nhiệm vụ hoặc Câu tự do')
        if not self.mission and self.area not in AREAS_UI.values():
            raise ValueError('Chọn khu câu tự do')


class NonRecoverableError(RuntimeError):
    """Navigation cannot resolve an unrecognized mission target."""


class Cancelled(Exception):
    pass


class ControlledDevice:
    def __init__(self, device, stop, on_retry=None):
        self.device, self.stop = device, stop
        self.on_retry = on_retry
        self.continue_screen = ContinueScreen()
        self.guard_session = True

    def wait_connected(self, timeout=30):
        if not isinstance(self.device, AdbDevice):
            return self.is_connected()
        def checkpoint():
            if self.stop.is_set():
                raise Cancelled()
        return self.device.wait_connected(timeout=timeout, checkpoint=checkpoint)

    def __getattr__(self, name):
        member = getattr(self.device, name)
        if not callable(member):
            return member
        def call(*args, **kwargs):
            def check_stop():
                if self.stop.is_set():
                    raise Cancelled()
            check_stop()
            if name == 'screenshot' and isinstance(self.device, AdbDevice):
                kwargs.setdefault('checkpoint', check_stop)
                kwargs.setdefault('on_retry', self.on_retry)
            result = member(*args, **kwargs)
            if name == "screenshot" and self.guard_session and self.continue_screen.detect(result):
                raise SessionLost("Game đã trở về màn hình Chơi tiếp")
            return result
        return call


class BotWorker:
    def __init__(self, options, emit, device=None, inventory_cache=None):
        options.validate()
        self.options, self.emit = options, emit
        self.inventory_cache = inventory_cache
        self.stop = threading.Event()
        self.pause = threading.Event()
        settings = Settings()
        self.device = ControlledDevice(device or AdbDevice(settings.serial, settings.adb_path,fast_capture=True), self.stop,
            lambda retry, limit: self.emit('log', f'[ADB] Kết nối/chụp màn hình gián đoạn; đang thử lại {retry}/{limit}.'))
        self.folder = ROOT / 'debug/ui' / datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')
        self.folder.mkdir(parents=True, exist_ok=True)
        self.data = {'status': 'NEW', 'counts': {}, 'unsold': {}, 'casts': 0, 'bites': 0,
                     'misses': 0, 'unclassified_results': 0, 'bait_purchased': 0,
                     'bait_remaining': None, 'purchase_pending': False,
                     'tickets': {key: {'status': 'unknown', 'expires_on': None} for key in TICKETS},
                     'wallet': {'coins': None, 'gold': None}, 'preparing': True,
                     'targets': [], 'log': str(self.folder)}
        self.started = None
        self.data.update(started_at=datetime.now().isoformat(), bait_stocks={'ecological': None, 'dock': None}, last_midnight_sale=None,
                         fish_inventory_date=datetime.now().date().isoformat(),bait_estimated={'ecological':False,'dock':False})
        inventory = ROOT / 'runtime/ui_inventory.json'
        if inventory.exists():
            saved = json.loads(inventory.read_text(encoding='utf-8'))
            for name in ('unsold', 'bait_remaining', 'purchase_pending', 'bait_stocks', 'last_midnight_sale', 'fish_inventory_date'):
                self.data[name] = saved.get(name, self.data[name])
            if 'bait_stocks' not in saved:
                self.data['bait_stocks']['ecological'] = self.data['bait_remaining']
        if options.custom_targets:
            self.data['targets'] = [{'species': s, 'name': SPECIES[s], 'current': 0, 'required': n, 'area': AREAS[s]} for s, n in options.custom_targets]
            path = ROOT / 'runtime/custom_mission.json'
            if path.exists():
                saved = json.loads(path.read_text(encoding='utf-8'))
                signature = [[s, n] for s, n in options.custom_targets]
                if sorted(saved.get('plan',[])) == sorted(signature) and saved.get('status') != 'COMPLETE':
                    by_species={t['species']:t for t in saved['targets']}
                    self.data['targets'] = [by_species[s] for s,_ in options.custom_targets]
        dock = ROOT / 'runtime/dock.json'
        if dock.exists():
            saved = json.loads(dock.read_text(encoding='utf-8'))
            self.data['bait_stocks']['dock'] = saved.get('bait', {}).get('remaining')
        self.travel = TravelController(self.device, self.folder / 'travel', on_event=self.shop_event)
        self.rooms = RoomSwitcher(self.travel)
        self.fishing_presentations = {}
        self.ready_for_next = None
        self.wallet_refresh_after = 0.0
        self.inventory_ready = False
        self.cache_serial=getattr(self.device,'serial',settings.serial)
        if not isinstance(self.cache_serial,str):self.cache_serial=settings.serial
        self.cache_path=ROOT/'runtime/character_state.json'
        durable=state_cache.load(self.cache_path,self.cache_serial)
        self.cached_quest=durable.pop('quest',None)
        for key,value in durable.items():
            if isinstance(value,dict) and isinstance(self.data.get(key),dict):self.data[key].update(value)
            else:self.data[key]=value
        if inventory_cache is not None:
            # Disk inventory remains useful for pending payments/fish stock,
            # but tickets and bait must be freshly observed after app launch.
            if not durable:
                self.data.update(bait_remaining=None,bait_stocks={'ecological':None,'dock':None},
                                 bait_estimated={'ecological':False,'dock':False},scan_complete=False)
            for key in self.inventory_cache_keys():
                if key in inventory_cache:
                    self.data[key]=copy.deepcopy(inventory_cache[key])
            self.inventory_ready=bool(self.data.get('scan_complete'))

    def reusable_quest(self):
        quest=self.cached_quest
        if not isinstance(quest,dict) or not quest.get('title') or not quest.get('targets'):return None
        if not isinstance(quest['targets'],list):return None
        for target in quest['targets']:
            if (not isinstance(target,dict) or target.get('species') not in AREAS or type(target.get('current')) is not int
                    or type(target.get('required')) is not int or target['required']<=0
                    or not 0<=target['current']<=target['required']):return None
        return {'targets':copy.deepcopy(quest['targets']),'title_raw':quest['title']}

    @staticmethod
    def inventory_cache_keys():
        return ('tickets','bait_remaining','bait_stocks','bait_estimated','wallet',
                'scan_complete','inventory_observed_at','inventory_updated_at')

    @staticmethod
    def resource_error(reason):
        return any(marker in str(reason).lower() for marker in (
            'insufficient memory', 'not enough memory', 'paging file',
            'outofmemoryerror', 'failed to allocate', 'winerror 8]', 'winerror 1455]'))

    def explain_error(self, reason):
        """Đọc popup lỗi khi luồng cũ chưa nhận diện, không bấm popup lạ."""
        # A transport failure is not a game popup. Another screenshot here
        # used to add 45 seconds of retries before recovery could even start.
        if 'adb' in reason.lower() or self.resource_error(reason):
            return reason
        from fishing.quest import read_ocr, normalize
        import cv2
        path = self.folder / 'error_screen.png'
        try:
            cv2.imwrite(str(path), self.device.screenshot())
            lines = read_ocr(path)
            plain = normalize(' '.join(lines))
            if 'cap do' in plain or 'level' in plain:
                return 'Chưa đủ cấp để câu. ' + ' '.join(lines)
            if 've' in plain and ('het han' in plain or 'chua co ve' in plain):
                return 'Chưa có vé hoặc vé đã hết hạn. ' + ' '.join(lines)
        except (OSError, RuntimeError, ValueError, SessionLost):
            pass
        return reason

    def publish(self):
        from debug.retention import maybe_prune
        maybe_prune(ROOT/'debug',
                    protected_paths=(self.folder,) if self.data.get('purchase_pending') else (),
                    keep_directories=(self.folder,))
        self.data['misses'] = max(0,self.data['casts']-self.data['bites'])
        self.data['bait_stocks']['ecological'] = self.data['bait_remaining']
        if getattr(self,'inventory_cache',None) is not None:
            self.inventory_cache.update({key:copy.deepcopy(self.data[key])
                for key in self.inventory_cache_keys() if key in self.data})
        self.data['elapsed_seconds'] = int(time.monotonic() - self.started) if self.started is not None else 0
        self.data['bait_stocks']['ecological'] = self.data['bait_remaining']
        text = json.dumps(self.data, ensure_ascii=False, indent=2)
        (self.folder / 'state.json').write_text(text, encoding='utf-8')
        destination = ROOT / 'runtime/ui_last.json'
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix('.tmp')
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(destination)
        inventory = ROOT / 'runtime/ui_inventory.json'
        temporary = inventory.with_suffix('.tmp')
        temporary.write_text(json.dumps({name: self.data[name] for name in
            ('unsold', 'bait_remaining', 'purchase_pending', 'bait_stocks', 'last_midnight_sale', 'fish_inventory_date')}, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(inventory)
        state_cache.save(self.cache_path,self.cache_serial,self.data,self.options.mission)
        if self.options.mission and self.data.get('quest_title') and self.data['targets']:
            self.cached_quest={'targets':copy.deepcopy(self.data['targets']),'title':self.data['quest_title']}
        if self.options.custom_targets:
            custom = ROOT / 'runtime/custom_mission.json'
            temporary = custom.with_suffix('.tmp')
            temporary.write_text(json.dumps({'plan': self.options.custom_targets, 'targets': self.data['targets'],
                                             'status': self.data['status']}, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(custom)
        self.emit('progress', json.loads(text))

    def issue(self, category, reason, **details):
        record = {'time': datetime.now().isoformat(), 'category': category, 'reason': reason,
                  'session': str(self.folder), 'area': self.data.get('area'), **details}
        path = ROOT / 'debug/bugs.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    def sell_before_midnight(self, area, now=None):
        now = now or datetime.now()
        day = now.date().isoformat()
        if not self.options.midnight_sale or (now.hour, now.minute) < (23, 57) or self.data['last_midnight_sale'] == day:
            return
        self.emit('log', '[ĐÊM] Về shop bán cá trước khi rương reset; sau đó câu tiếp.')
        if area=='dock':
            MapNavigator(self.device,output=self.folder/'midnight_navigation').go('fishing')
        else:
            self.travel.center(area)
        self.travel.sell_and_buy(sell=True, buy=False)
        self.data['last_midnight_sale'] = day
        self.publish()
        if area=='dock':
            self.go('dock')
        else:
            self.travel.enter(area)

    def refresh_chest_date(self, now=None):
        day = (now or datetime.now()).date().isoformat()
        if self.data.get('fish_inventory_date', day) != day:
            self.data['unsold'] = {}
            self.emit('log', '[RƯƠNG] Đã sang ngày mới; xóa tồn cá cũ, giữ số cá đã câu và tiến độ.')
        self.data['fish_inventory_date'] = day

    def shop_event(self, name, details):
        if name == 'RECONNECT_COOLDOWN':
            self.emit('log', '[KẾT NỐI] Đang chờ game hết thời gian đăng nhập lại; sẽ Chơi tiếp khi popup đóng.')
        if name == 'TICKET_PURCHASE_PENDING':
            self.data['purchase_pending'] = True
        elif name == 'TICKET_PURCHASE_CONFIRMED':
            self.data['tickets'][details['ticket']]={'status':'active','expires_on':details.get('expires_on')}
            if 'wallet' in details:
                self.data['wallet']=details['wallet']
            self.data['purchase_pending'] = False
        elif name == 'DOCK_PURCHASE_CONFIRMED':
            self.data['bait_purchased'] += details['quantity']
            self.data['bait_stocks']['dock'] = (self.data['bait_stocks']['dock'] or 0) + details['quantity']
            coins=self.data['wallet']['coins']
            if coins is not None:self.data['wallet']['coins']=max(0,coins-details['quantity']*50)
            self.data['purchase_pending'] = False
        elif name == 'PURCHASE_PENDING':
            self.data['purchase_pending'] = True
        elif name == 'PURCHASE_REJECTED_CAPACITY':
            self.data['purchase_pending'] = False
        elif name == 'SALE_CONFIRMED':
            self.data['unsold'] = {}
            self.data['wallet']['coins']=None
        elif name == 'PURCHASE_CONFIRMED':
            quantity = details['quantity']
            self.data['bait_purchased'] += quantity
            self.data['bait_remaining'] = (self.data['bait_remaining'] or 0) + quantity
            coins=self.data['wallet']['coins']
            if coins is not None:self.data['wallet']['coins']=max(0,coins-details.get('coins',quantity*20))
            self.data['purchase_pending'] = False
        self.publish()

    def checkpoint(self):
        if self.pause.is_set():
            self.emit('status', 'Đã tạm dừng — chờ Tiếp tục')
            while self.pause.is_set() and not self.stop.wait(.2):
                pass
        if self.stop.is_set():
            raise Cancelled()
        self.emit('status', 'Đang chạy')

    def dismiss_level_popup(self):
        image = self.device.screenshot()
        if DockDetector().detect(image).level_locked:
            ok = self.travel.world.match(image, 'ok')
            if ok is None:
                raise RuntimeError('Cảnh báo cấp đang mở; chưa nhận diện nút OK')
            self.device.tap(*ok.center)

    def read_quest(self):
        reader = QuestReader(self.device)
        quest = reader.read()
        # Popup nhiệm vụ không có nút đóng; điểm ngoài bên trái đã dùng ở bản CLI.
        self.device.tap(160, 650)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            image = self.device.screenshot()
            if not reader.match(image, 'quest_title') and reader.match(image, 'quest_icon'):
                return quest
            time.sleep(.2)
        raise RuntimeError('Chưa xác nhận đóng popup nhiệm vụ')

    def advance_game_quest(self):
        """Return to the quest icon, verify/claim, then read a fresh task."""
        self.checkpoint()
        self.preparation_step('Đang xác minh và trả nhiệm vụ câu cá…')
        area=self.data.get('area')
        if area in ('ca_ro','ca_noc','ca_map'):
            self.travel.center(area)
        else:
            MapNavigator(self.device,output=self.folder/'quest_navigation').go('fishing')
        previous=self.data['quest_title']
        quest=self.read_quest()
        acknowledged=bool(quest.get('reward_acknowledged'))
        if quest['title_raw']==previous and quest['completed']:
            # Some clients first show the completed task; opening the icon
            # again performs the hand-in. Each read closes its popup.
            quest=self.read_quest()
            acknowledged=acknowledged or bool(quest.get('reward_acknowledged'))
            if quest['title_raw']==previous:
                raise RuntimeError('Chưa xác nhận nhiệm vụ mới sau trả nhiệm vụ; đã dừng để tránh lặp.')
        unsupported=[t['name'] for t in quest['targets'] if t['current']<t['required'] and AREAS.get(t['species']) is None]
        if unsupported:
            raise NonRecoverableError('Nhiệm vụ mới có cá chưa hỗ trợ hoặc chưa nhận dạng được: '+', '.join(unsupported))
        self.data.update(targets=quest['targets'],quest_title=quest['title_raw'],preparing=False)
        if acknowledged:
            self.data['quests_completed']=self.data.get('quests_completed',0)+1
            self.data['wallet']['coins']=None
        changed=quest['title_raw']!=previous
        self.emit('log','[NHIỆM VỤ] '+('Đã nhận nhiệm vụ mới: ' if changed else 'Đã cập nhật tiến độ từ game: ')+quest['title_raw'])
        self.publish();self.emit('prepared',None)
        return changed

    def go(self, area, _bait_retry=True):
        if area == 'dock':
            MapNavigator(self.device, output=self.folder / 'navigation').go('dock')
            result = DockController(self.device, output=self.folder / 'dock').check()
            if result['status']=='READY':
                return
            if result['status']=='OUT_OF_BAIT':
                self.data['bait_stocks']['dock']=0
                self.data['bait_estimated']['dock']=False
                self.publish()
                if not self.options.buy:
                    raise RuntimeError('Hết Mồi Câu Cá Trâm. Bật tự mua mồi hoặc mua thêm tại shop Bến Tàu.')
                if not _bait_retry:
                    raise RuntimeError('Game vẫn báo thiếu Mồi Câu Cá Trâm sau mua; không mua lặp.')
                self.travel.leave_chair('dock')
                self.prepare_area('dock')
                return self.go('dock',_bait_retry=False)
            if result['status']=='NO_SEAT':
                self.data['room']=self.rooms.choose('dock')
                self.publish()
                return self.go('dock')
            raise RuntimeError(result['reason'])
        image = self.device.screenshot()
        current = self.travel.world.map_name(image, require_menu=False)
        if current == area:
            return
        if current not in ('center', 'ca_ro', 'ca_noc', 'ca_map'):
            MapNavigator(self.device, output=self.folder / 'navigation').go('fishing')
        elif current != 'center':
            self.travel.center(current)
        if self.options.sell and self.data['unsold']:
            self.travel.sell_and_buy(sell=True, buy=False)
        self.travel.enter(area)

    def take_ready_handoff(self, area):
        saved, self.ready_for_next = getattr(self, 'ready_for_next', None), None
        if saved is not None and saved[0] == area and 0 <= time.monotonic()-saved[1][2] <= .25:
            return saved[1]
        return None

    def refresh_wallet_display(self, index):
        """Unknown display OCR must not delay every cast; purchases read afresh."""
        unknown = any(self.data['wallet'].get(key) is None for key in ('coins','gold'))
        if index % 20 and (not unknown or time.monotonic() < self.wallet_refresh_after):
            return
        balances = InventoryController(self.device,self.folder/'balances').wallet()
        self.wallet_refresh_after=time.monotonic()+120
        for currency,value in balances.items():
            if value is not None:self.data['wallet'][currency]=value

    def preparation_step(self, message):
        self.emit('preparation', message)
        self.emit('log', '[CHUẨN BỊ] ' + message)

    def apply_inventory(self, observation, scanned=True):
        self.data.update(observation)
        self.data['bait_remaining'] = observation['bait_stocks']['ecological']
        if scanned:
            self.data['bait_estimated']={'ecological':False,'dock':False}
        self.publish()

    def prepare_area(self, area):
        bait_key='dock' if area=='dock' else 'ecological'
        ticket=self.data['tickets'][area]
        expiry=ticket.get('expires_on')
        if expiry and expiry<datetime.now().date().isoformat():ticket.update(status='unknown',expires_on=None)
        stock=self.data['bait_stocks'][bait_key]
        if ticket['status']=='active' and type(stock) is int and stock>0 and not self.data['purchase_pending']:
            self.preparation_step('Đã có vé và mồi trong trạng thái đã lưu; đi thẳng tới khu câu.')
            self.data['preparing']=False
            if self.started is None:self.started=time.monotonic()
            self.publish();self.emit('prepared',None)
            return
        self.data['preparing'] = True
        self.preparation_step('Đang điều hướng tới ' + ('Bến Tàu…' if area == 'dock' else 'Khu Sinh Thái…'))
        navigator = MapNavigator(self.device, output=self.folder / 'preparation_navigation')
        current = self.travel.world.map_name(self.device.screenshot(), require_menu=False)
        if area != 'dock' and current in ('ca_ro', 'ca_noc', 'ca_map'):
            self.travel.center(current)
        else:
            navigator.go('dock' if area == 'dock' else 'fishing')
        inventory = InventoryController(self.device, self.folder / 'inventory', on_event=self.shop_event)
        bait_key = 'dock' if area == 'dock' else 'ecological'
        if (self.data['tickets'][area]['status'] == 'unknown'
                or self.data['bait_stocks'][bait_key] is None
                or (self.data['tickets'][area]['status'] != 'active' and not self.data.get('scan_complete'))):
            self.preparation_step('Đang mở rương, kiểm tra vé, mồi và số dư…')
            self.apply_inventory(inventory.chest())
            self.inventory_ready=bool(self.data['scan_complete'])
        if not self.data.get('scan_complete') and self.data['tickets'][area]['status'] != 'active':
            raise RuntimeError('Chưa quét hết rương; kiểm tra lại trước khi mua hoặc bắt đầu câu.')
        ticket = self.data['tickets'][area]
        name = TICKETS[area][0]
        if ticket['status'] == 'unknown':
            raise RuntimeError('Chưa xác định hiệu lực ' + name + '; kiểm tra rương trước khi chạy.')
        if ticket['status'] != 'active':
            if area not in self.options.auto_tickets:
                raise RuntimeError(name + ' chưa có hoặc đã hết hạn. Bật tự mua vé tương ứng trong Thiết lập.')
            if self.data['wallet'].get(TICKETS[area][2]) is None:
                self.data['wallet']=inventory.wallet()
            self.preparation_step('Đang mua ' + name + '…')
            self.apply_inventory(inventory.buy_ticket(area, self.data['wallet'],observation=copy.deepcopy(self.data)),scanned=False)
            if self.data['tickets'][area]['status'] != 'active':
                raise RuntimeError('Chưa xác nhận vé còn hiệu lực sau mua; không mua lặp.')
        bait_key = 'dock' if area == 'dock' else 'ecological'
        remaining = self.data['bait_stocks'][bait_key]
        if remaining is None:
            raise RuntimeError('Chưa đọc được số lượng ' + BAITS[bait_key][0] + '; kiểm tra rương.')
        if remaining == 0 and not self.data.get('bait_estimated',{}).get(bait_key):
            if not self.options.buy:
                raise RuntimeError('Hết '+BAITS[bait_key][0]+'. Bật tự mua mồi hoặc mua thêm đúng loại trong game.')
            if self.data['wallet']['coins'] is None:
                self.data['wallet']=inventory.wallet()
            ensure_funds(self.data['wallet'], 'coins', self.options.bait_quantity * BAITS[bait_key][1])
            self.preparation_step('Đang mua ' + BAITS[bait_key][0] + '…')
            if area == 'dock':
                quantity=inventory.buy_dock_bait(self.options.bait_quantity, self.data['wallet'])
            else:
                quantity=self.travel.sell_and_buy(sell=self.options.sell and bool(self.data['unsold']), buy=True,
                                         quantity=self.options.bait_quantity)
            if quantity != self.options.bait_quantity or self.data['purchase_pending']:
                raise RuntimeError('Chưa xác nhận biên nhận mua đủ mồi; không mua lặp.')
            self.data['wallet']=inventory.wallet()
        self.data['preparing'] = False
        if self.started is None:
            self.started = time.monotonic()
        self.publish()
        self.emit('prepared', None)

    def record(self, result):
        self.refresh_chest_date()
        self.data['casts'] += result.casts
        # The dashboard counts fish actually received, not the earlier bite
        # signal. Xong/RESULT alone (or a failed pull after a bite) is a miss.
        caught = result.outcome == 'SUCCESS' and result.fish_species in SPECIES
        self.data['bites'] += int(caught)
        self.data['misses']=max(0,self.data['casts']-self.data['bites'])
        if result.area=='dock':
            stock=self.data['bait_stocks']['dock']
            if stock is not None:
                self.data['bait_stocks']['dock']=max(0,stock-result.casts)
        elif self.data['bait_remaining'] is not None:
            self.data['bait_remaining'] = max(0, self.data['bait_remaining'] - result.casts)
        if result.casts:
            self.data.setdefault('bait_estimated',{})['dock' if result.area=='dock' else 'ecological']=True
        if result.outcome == 'FAILED':
            pass  # Misses are casts minus confirmed named catches.
        elif result.outcome in ('RESULT','ABORTED'):
            self.data['unclassified_results'] += 1
        elif result.outcome == 'SUCCESS':
            species = result.fish_species or 'unknown'
            for field in ('counts', 'unsold'):
                self.data[field][species] = self.data[field].get(species, 0) + 1
            for target in self.data['targets']:
                if target['species'] == species:
                    target['current'] = min(target['required'], target['current'] + 1)
        self.publish()

    def reconnect(self):
        if self.data['purchase_pending']:
            raise RuntimeError('Game mất phiên khi mua mồi chưa có biên nhận; không tự mua lại.')
        self.checkpoint()
        self.device.guard_session = False
        try:
            navigator = MapNavigator(self.device, output=self.folder / 'reconnect')
            recovery = ReconnectController(self.device,self.folder/'reconnect',on_event=self.shop_event)
            recovery.recover(self.device.continue_screen,
                             lambda image: navigator.is_world(image) or navigator.location(image) is not None
                             or self.travel.world.map_name(image,require_menu=False) is not None,
                             checkpoint=self.checkpoint)
            self.rooms.tried.clear()
            self.data['status'] = 'RUNNING'
            self.publish()
            self.emit('log', '[KẾT NỐI] Đã vào lại bản đồ; tiếp tục tìm đường tới khu câu.')
        finally:
            self.device.guard_session = True

    def recover_error(self, error):
        if not self.options.auto_resume or isinstance(error,(Cancelled,NonRecoverableError)) or self.stop.is_set():
            return False
        previous_failure = None
        repeated_failures = 0
        while self.data.get('auto_restarts',0) < self.options.resume_limit:
            self.checkpoint()
            self.data['auto_restarts']=self.data.get('auto_restarts',0)+1
            count=self.data['auto_restarts']
            self.issue('auto_restart',str(error),attempt=count,limit=self.options.resume_limit)
            self.emit('log',f'[KHÔI PHỤC] Lần {count}/{self.options.resume_limit}: {error}')
            self.preparation_step('Đang về bản đồ thế giới để tiếp tục tiến trình…')
            self.publish()
            self.ready_for_next = None
            try:
                # A lost purchase receipt cannot be reconstructed by retrying payment.
                if self.data['purchase_pending']:
                    raise RuntimeError('Giao dịch chưa có biên nhận; không tự chạy lại để tránh mua lặp.')
                if self.resource_error(error):
                    # Drop optional solver workspaces and allow Windows/emulator
                    # resources to settle instead of burning all retries at once.
                    import gc
                    self.fishing_presentations.clear()
                    if isinstance(self.device.device, AdbDevice):
                        self.device.device.fast_capture = False
                    gc.collect()
                    self.emit('log', '[KHÔI PHỤC] Thiếu bộ nhớ hệ thống; đã giải phóng cache và chờ 5 giây.')
                    self.stop.wait(5)
                self.checkpoint()
                self.emit('log', '[KHÔI PHỤC] Đang chờ kết nối giả lập ổn định (tối đa 30 giây)…')
                if not self.device.wait_connected(timeout=30):
                    raise RuntimeError('ADB chưa kết nối khi khôi phục')
                try:
                    self.travel.wait(lambda image:True,'màn hình khôi phục sau popup',timeout=10,observations=1)
                    image=self.device.screenshot()
                except SessionLost:
                    self.reconnect()
                    self.travel.wait(lambda image:True,'màn hình sau kết nối lại',timeout=10,observations=1)
                    image=self.device.screenshot()
                detector=FishingDetector(area=self.data.get('area','ca_ro'))
                navigator=MapNavigator(self.device,output=self.folder/f'restart_{count:02d}')
                from fishing.states import FishingState
                initial=detector.detect(image)
                state=initial.state
                if state in (FishingState.WAITING,FishingState.FISHING):
                    close=initial.matches.get('close')
                    if close is None:
                        raise RuntimeError('Chưa xác nhận nút Đóng để hủy lượt khi khôi phục')
                    self.travel.tap(close.center,'Đóng lượt để khởi động lại')
                    def cancellation_screen(image):
                        observed=detector.detect(image)
                        if observed.state is FishingState.EXIT_CONFIRM:return 'confirm'
                        if observed.state in (FishingState.IDLE,FishingState.READY) and observed.scene_confirmed:
                            return 'outside'
                        if observed.state is FishingState.UNKNOWN and (
                                navigator.is_world(image) or navigator.location(image) is not None
                                or self.travel.world.map_name(image,require_menu=False) is not None):
                            return 'outside'
                        return None
                    response=self.travel.wait(cancellation_screen,'hủy lượt hoặc map ngoài ghế',timeout=10,
                                              handle_interruptions=False)
                    if response=='confirm':
                        self.travel.button('exit_yes','Có: hủy lượt để khôi phục')
                # Close unknown overlays via Android Back, inspecting each
                # resulting frame. Never confirm an exit from the game.
                for _ in range(3):
                    image=self.device.screenshot()
                    if navigator.is_world(image) or navigator.location(image) is not None or self.travel.world.map_name(image,require_menu=False) is not None:
                        break
                    state=detector.detect(image)
                    if state.state is FishingState.EXIT_CONFIRM:
                        close=state.matches.get('exit_no')
                        if close is not None:self.travel.tap(close.center,'Không: giữ game khi khôi phục')
                        self.stop.wait(.5);self.checkpoint()
                        continue
                    if state.state is FishingState.OUT_OF_BAIT:
                        self.travel.button('ok','Đóng thông báo hết mồi khi khôi phục');continue
                    cancel=self.travel.world.match(image,'cancel')
                    if cancel is not None and (self.travel.world.match(image,'buy_coin') is not None
                                               or self.travel.world.match(image,'purchase_confirm') is not None):
                        self.travel.tap(cancel.center,'Hủy popup mua chưa thanh toán khi khôi phục')
                        self.travel.wait(lambda a:self.travel.world.match(a,'cancel') is None,
                                         'đóng popup mua khi khôi phục',timeout=8)
                        continue
                    if self.travel.world.match(image,'fish_shop') is not None:
                        self.travel.tap((200,650),'Đóng shop khi khôi phục')
                        self.travel.wait(lambda a:self.travel.world.match(a,'fish_shop') is None,
                                         'đóng shop khi khôi phục',timeout=8)
                        continue
                    self.device.back();self.stop.wait(.5);self.checkpoint()
                area=self.data.get('area')
                if area in ('ca_ro','ca_noc','ca_map') and navigator.location(self.device.screenshot()) != 'world':
                    self.travel.center(area)
                navigator.open_world()
                self.inventory_ready=bool(self.data.get('scan_complete'))
                self.fishing_presentations.clear();self.rooms.tried.clear()
                self.data.update(status='RUNNING',preparing=True)
                self.publish()
                return True
            except Cancelled:
                raise
            except Exception as failure:
                error=failure
                self.emit('log','[KHÔI PHỤC] Chưa thành công: '+str(failure))
                if self.resource_error(failure):
                    self.emit('log','[KHÔI PHỤC] Vẫn thiếu bộ nhớ sau khi giải phóng cache; dừng để tránh lặp thao tác khôi phục. Đóng bớt ứng dụng rồi chạy lại.')
                    break
                repeated_failures = repeated_failures + 1 if str(failure) == previous_failure else 1
                previous_failure = str(failure)
                if repeated_failures >= 3:
                    self.emit('log','[KHÔI PHỤC] Cùng lỗi lặp lại 3 lần, chưa có tiến triển; dừng khôi phục.')
                    break
                if self.data['purchase_pending']:
                    break
        return False

    def run(self):
        connected = False
        original_log = OneRoundBot._log
        def log(message):
            with (self.folder / 'bot.log').open('a', encoding='utf-8') as stream:
                stream.write(datetime.now().isoformat() + ' ' + message + '\n')
            self.emit('log', message)
            from debug.retention import maybe_prune
            maybe_prune(ROOT/'debug', keep_directories=(self.folder,))
            if sys.stdout is not None:
                original_log(message)
        OneRoundBot._log = staticmethod(log)
        try:
            reconnects = 0
            index = 0
            prepared_area = None
            while True:
                try:
                    if self.data['purchase_pending']:
                        raise RuntimeError('Lần mua trước chưa có biên nhận xác nhận; kiểm tra log trước khi chạy lại để tránh mua lặp.')
                    if not self.device.is_connected():
                        raise RuntimeError('ADB chưa kết nối')
                    connected = True
                    if self.device.get_screen_size() != (1600, 900):
                        raise RuntimeError('Bot hiện cần độ phân giải 1600×900')
                    self.dismiss_level_popup()
                    if self.rooms.is_open(self.device.screenshot()):
                        self.data['room'] = self.rooms.choose(self.options.area or 'ca_ro')
                    if self.options.mission and self.reusable_quest() is not None:
                        quest=self.reusable_quest()
                        self.data.update(targets=quest['targets'],quest_title=quest['title_raw'])
                        self.emit('log','[NHIỆM VỤ] Dùng nhiệm vụ và tiến độ đã lưu.')
                    elif self.options.mission:
                        reader = QuestReader(self.device)
                        image = self.device.screenshot()
                        if not any(reader.match(image, name) for name in ('quest_icon', 'quest_title', 'quest_current_button')):
                            MapNavigator(self.device, output=self.folder / 'navigation').go('fishing')
                        quest = self.read_quest()
                        self.data['targets'] = quest['targets']
                        self.data['quest_title'] = quest['title_raw']
                        self.publish()
                        unsupported = [t['name'] for t in self.data['targets']
                                       if t['current'] < t['required'] and AREAS.get(t['species']) is None]
                        if unsupported:
                            raise NonRecoverableError('Chưa nhận dạng hoặc chưa hỗ trợ mục tiêu: ' + ', '.join(unsupported)
                                                      + '. Kiểm tra ảnh nhiệm vụ trong log; không tự khởi động lại cùng lỗi này.')
                    while True:
                        self.checkpoint()
                        self.refresh_chest_date()
                        needed = [t for t in self.data['targets'] if t['current'] < t['required']]
                        if self.options.custom_targets and not needed:
                            self.data['status'] = 'COMPLETE'
                            self.emit('notice', 'Đã hoàn thành các mục tiêu tự đặt; bot đã dừng.')
                            break
                        if self.options.mission and not needed:
                            if self.advance_game_quest():
                                prepared_area=None
                                continue
                            needed = [t for t in self.data['targets'] if t['current'] < t['required']]
                        area = AREAS[needed[0]['species']] if self.options.mission or self.options.custom_targets else self.options.area
                        if area != prepared_area:
                            self.prepare_area(area)
                            prepared_area = area
                        ready_handoff=self.take_ready_handoff(area)
                        if ready_handoff is None:
                            self.go(area)
                        if self.data.get('area') != area or self.data['status'] != 'RUNNING':
                            self.data.update(area=area,status='RUNNING')
                            self.publish()
                        self.sell_before_midnight(area)
                        index += 1
                        if area not in self.fishing_presentations:
                            detector = FishingDetector(area=area)
                            self.fishing_presentations[area] = (detector, FishingSolver(detector))
                        detector, solver = self.fishing_presentations[area]
                        session = FishingSession(self.device, SessionSettings(rounds=1,poll_interval=.03), area=area,
                                                 trial_settings=TrialSettings(poll_interval=.02),
                                                 detector=detector, solver=solver,
                                                 recover_uncertain=True,reuse_ready=True,
                                                 ready_handoff=ready_handoff,
                                                 output=self.folder / f'round_{index:04d}')
                        result = session.run()
                        for round_ in result.rounds:
                            self.record(round_)
                            if round_.outcome in ('FAILED', 'RESULT', 'ABORTED'):
                                self.issue('game_result', round_.reason, outcome=round_.outcome, round=index)
                        if result.status == 'OUT_OF_BAIT':
                            if area=='dock':
                                self.data['bait_stocks']['dock']=0
                                self.data['bait_estimated']['dock']=False
                                self.publish()
                                if not self.options.buy:
                                    raise RuntimeError('Hết mồi bến tàu. Bật tự mua mồi hoặc mua thêm trong game.')
                                self.travel.leave_chair('dock')
                                self.prepare_area('dock')
                                continue
                            self.data['bait_remaining'] = 0
                            self.data['bait_estimated']['ecological']=False
                            self.publish()
                            if not self.options.buy:
                                raise RuntimeError('Hết mồi câu. Bật tự mua mồi hoặc mua thêm trong game.')
                            self.checkpoint()
                            self.travel.center(area)
                            inventory = InventoryController(self.device, self.folder / 'refill')
                            self.data['wallet'] = inventory.wallet()
                            ensure_funds(self.data['wallet'], 'coins', self.options.bait_quantity * 20)
                            quantity = self.travel.sell_and_buy(
                                sell=self.options.sell and bool(self.data['unsold']), buy=True, quantity=self.options.bait_quantity)
                            if not quantity:
                                raise RuntimeError('Shop chưa xác nhận mua mồi; không mua lặp')
                            self.travel.enter(area)
                            continue
                        if result.status != 'COMPLETE':
                            if not result.rounds and 'ghế trống' in result.reason:
                                self.data['room'] = self.rooms.choose(area)
                                self.publish()
                                continue
                            raise RuntimeError(self.explain_error(result.reason))
                        verified = session.verified_ready
                        self.ready_for_next=(area,verified) if isinstance(verified,tuple) and len(verified)==3 else None
                        self.refresh_wallet_display(index)
                        self.data['status'] = 'RUNNING'
                        self.rooms.tried.clear()
                        self.publish()
                    break
                except SessionLost:
                    reconnects += 1
                    try:
                        if reconnects > 3:
                            raise RuntimeError('Game mất phiên liên tiếp 3 lần; đã dừng.')
                        self.emit('log', '[KẾT NỐI] Game về màn hình đăng nhập; đang khôi phục phiên.')
                        self.reconnect()
                    except Cancelled:
                        raise
                    except Exception as failure:
                        if not self.recover_error(failure):
                            raise
                        reconnects=0
                    prepared_area = None
                except Cancelled:
                    raise
                except Exception as exc:
                    if not self.recover_error(exc):
                        raise
                    prepared_area=None
                    reconnects=0
        except Cancelled:
            self.data.update(status='STOPPED', reason='Đã kết thúc theo yêu cầu')
        except Exception as exc:
            self.data['status'] = 'ERROR'
            reason = self.explain_error(str(exc)) if connected and not self.stop.is_set() else str(exc)
            self.data.update(status='ERROR', reason=reason)
            self.issue('error', reason, traceback=traceback.format_exc(), screenshot=str(self.folder / 'error_screen.png'))
            self.emit('error', reason)
        finally:
            OneRoundBot._log = staticmethod(original_log)
            if self.data['status'] not in ('COMPLETE','STOPPED','ERROR'):
                self.data.update(status='ERROR',reason='Worker đã kết thúc mà chưa xác nhận trạng thái hoàn tất.')
            self.publish()
            from debug.retention import maybe_prune
            maybe_prune(ROOT/'debug', force=True, keep_directories=(self.folder,))
            self.emit('done', self.data['status'])
