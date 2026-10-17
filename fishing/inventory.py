"""Fresh chest observations and guarded purchases, in Android 1600x900 coordinates."""
import re
import copy
import time
from datetime import date, datetime
import cv2
import numpy as np
from config.settings import ROOT
from vision.matcher import find_template, MatchResult
from fishing.quest import read_ocr, normalize
from fishing.travel import TravelController
from vision.game_text import catalog_label

TICKETS = {
    'ca_ro': ('Vé câu cá rô', 1000, 'coins'),
    'ca_noc': ('Vé câu cá lóc', 10000, 'coins'),
    'ca_map': ('Vé câu cá mập', 2, 'gold'),
    'dock': ('Vé câu bến tàu', 12000, 'coins'),
}
BAITS = {'ecological': ('Mồi Trùng', 20), 'dock': ('Mồi Câu Cá Trâm', 50)}

def number(text):
    text = text.strip()
    return int(re.sub(r'[.,\s]', '', text)) if re.fullmatch(r'\d+(?:[.,\s]\d+)*', text) else None

def wallet_number(lines, currency):
    text = re.sub(r'\s+', '', ' '.join(lines))
    value = number(text)
    if currency == 'coin' and value is not None and value >= 1000:
        # Game formats xu with thousands separators. Reject OCR that joins digits.
        if not re.fullmatch(r'\d{1,3}(?:[.,]\d{3})+', text):
            return None
    return value

def item_kind(lines):
    title = normalize(' '.join(lines))
    # Observed Windows OCR output for the selected snakehead ticket title.
    # Keep this product-specific rather than accepting approximate fish names.
    for observed in ('ve cau ca lac', 've cau ca l6c', 've cau ca 16c'):
        title = title.replace(observed, 've cau ca loc')
    for key, (name, *_rest) in TICKETS.items():
        if normalize(name) in title:
            return 'ticket', key
    # Match complete ticket phrases only; unrelated text cannot become a fish.
    phrase=re.search(r'\bve\s+cau\s+(?:ca\s+\S+|ben\s+\S+)',title)
    if phrase:
        key=catalog_label(phrase[0],{name:key for key,(name,*_) in TICKETS.items()})
        if key is not None:
            return 'ticket',key
    if ('moi' in title and 'tram' in title) or 'cau ca tram' in title:
        return 'bait', 'dock'
    if 'moi' in title and 'trung' in title:
        return 'bait', 'ecological'
    return None, None

def ticket_info(lines, today=None):
    """An observed ticket is valid: expired tickets disappear from the chest."""
    plain = re.sub(r'(?<=\d)\s+(?=\d)', '', ' '.join(lines))
    match = re.search(r'\b(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(20\d{2})\b', plain)
    expiry = None
    if match:
        try:
            expiry = date(int(match[3]), int(match[2]), int(match[1])).isoformat()
        except ValueError:
            pass
    return {'status': 'active', 'expires_on': expiry}

def ensure_funds(wallet, currency, cost):
    value = wallet.get(currency)
    label = 'xu' if currency == 'coins' else 'lượng'
    if type(value) is not int:
        raise RuntimeError(f'Chưa xác định số {label}; không tự mua vật phẩm.')
    if value < cost:
        raise RuntimeError(f'Không đủ {label}: cần {cost:,}, hiện có {value:,}.')

def viewport_still(before, after):
    """Compare static stack labels and row positions, allowing animated item sprites."""
    def labels(image):
        mask=cv2.inRange(image,(200,170,130),(255,230,205))
        boxes=[cv2.boundingRect(c) for c in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]]
        rows=sorted({y for x,y,w,h in boxes if 105<=w<=135 and 105<=h<=135})
        parts=[image[y+5:y+36,10+136*col+90:10+136*col+124] for y in rows for col in range(5)]
        return rows,np.concatenate(parts,axis=0) if parts else None
    rows1,patch1=labels(before);rows2,patch2=labels(after)
    if patch1 is None or patch2 is None or len(rows1)!=len(rows2) or any(abs(a-b)>6 for a,b in zip(rows1,rows2)):
        return False
    if patch1.shape!=patch2.shape or np.mean(cv2.absdiff(patch1,patch2))>2:
        return False
    return np.mean(cv2.absdiff(cv2.GaussianBlur(before,(25,25),0),cv2.GaussianBlur(after,(25,25),0))) < 8

def cell_fingerprint(image):
    """Selection changes the slot background, not the observed item identity."""
    image=image.copy()
    background=cv2.inRange(image,(200,170,130),(255,230,205)) | cv2.inRange(image,(245,245,245),(255,255,255))
    image[background>0]=0
    return tuple((cv2.resize(image,(20,20))//24).flatten())

class InventoryController(TravelController):
    def __init__(self, device, output, **kwargs):
        super().__init__(device, output, **kwargs)
        self.templates = {p.stem: cv2.imread(str(p)) for p in (ROOT/'vision/templates/inventory').glob('*.png')}
        self.digits = {p.stem: cv2.imread(str(p),cv2.IMREAD_GRAYSCALE)
                       for p in (ROOT/'vision/templates/inventory/digits').glob('*.png')}

    def match(self, screen, name):
        template = self.templates.get(name)
        if template is None:
            return None
        # Supplied screenshots have small capture-scale differences.
        scales = (1., 1.01, .99, 1.02, .98, .95, .9, .85, 1.05) if name.endswith('_symbol') else (1.,1.01,.99,1.02,.98)
        if name.endswith('_symbol'):
            screen = screen[:150]
        for scale in scales:
            candidate = cv2.resize(template, None, fx=scale, fy=scale)
            if name.endswith('_symbol'):
                # Exclude changing sky/water around the currency icon.
                margin=round(8*scale)
                inner=candidate[margin:-margin,margin:-margin]
                found = find_template(cv2.cvtColor(screen,cv2.COLOR_BGR2GRAY),cv2.cvtColor(inner,cv2.COLOR_BGR2GRAY),threshold=.97,contrast_invariant=True)
                if found:
                    found=MatchResult(found.x-margin,found.y-margin,candidate.shape[1],candidate.shape[0],found.confidence)
            else:
                found = find_template(cv2.cvtColor(screen,cv2.COLOR_BGR2GRAY),cv2.cvtColor(candidate,cv2.COLOR_BGR2GRAY),threshold=.97,contrast_invariant=True)
            if found:
                if name.endswith('_symbol') and screen.shape[1]==1600 and found.x < 1000:
                    continue
                if name == 'chest_title' and not (60 < found.x < 400 and 10 < found.y < 100):
                    continue
                if name == 'basket' and not (found.x < 180 and 350 < found.y < 600):
                    continue
                return found
        return None

    def text(self, screen, bounds, name):
        x,y,r,b = bounds
        raw = screen[y:b,x:r]
        raw = cv2.copyMakeBorder(raw,8,8,8,8,cv2.BORDER_CONSTANT,value=(255,255,255))
        crop = cv2.resize(raw, None, fx=3, fy=3)
        path = self.output/(name+'.png')
        cv2.imwrite(str(path), crop)
        lines = read_ocr(path)
        if name.startswith('bait_count') and number(' '.join(lines)) is None:
            value = self.stack_number(raw[8:-8,8:-8])
            return [str(value)] if value is not None else []
        return lines

    def stack_number(self, crop):
        """Read the game's fixed stack font; reject borders and unfamiliar glyphs."""
        mask = cv2.inRange(cv2.cvtColor(crop,cv2.COLOR_BGR2HSV),(15,130,170),(40,255,255))
        boxes = sorted(cv2.boundingRect(c) for c in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0])
        result = []
        for x,y,w,h in boxes:
            if h < 16:
                continue
            if not 16 <= h <= 26 or not 4 <= w <= 18:
                return None
            glyph = mask[y:y+h,x:x+w]
            scores = sorted((float(np.mean(cv2.resize(glyph,(t.shape[1],t.shape[0])) == t)),digit)
                            for digit,t in self.digits.items())
            if not scores or scores[-1][0] < .96 or (len(scores)>1 and scores[-1][0]-scores[-2][0]<.05):
                return None
            result.append(scores[-1][1])
        return int(''.join(result)) if result else None

    def wallet(self):
        results = []
        for observation in range(2):
            screen = self.device.screenshot()
            symbols = {key:self.match(screen,key+'_symbol') or self.match(screen,key+'_night_symbol') for key in ('coin','gold')}
            values = {'coins':None, 'gold':None}
            for key, symbol in symbols.items():
                if symbol is None:
                    continue
                x = symbol.x + symbol.width
                end = symbols['gold'].x-5 if key == 'coin' and symbols['gold'] else min(1600,x+170)
                if key == 'gold':
                    next_symbol = (self.match(screen[:,x:], 'gold_locked_day_symbol')
                                   or self.match(screen[:,x:], 'gold_locked_symbol')
                                   or self.match(screen[:,x:], 'gold_symbol')
                                   or self.match(screen[:,x:], 'gold_night_symbol'))
                    if next_symbol:
                        end = x + next_symbol.x - 3
                if end <= x:
                    continue
                bounds = (x, symbol.y, end, min(900,symbol.y+symbol.height+1))
                crop = screen[bounds[1]:bounds[3],bounds[0]:bounds[2]]
                prepared = cv2.copyMakeBorder(crop,8,8,8,8,cv2.BORDER_CONSTANT,value=(255,255,255))
                path = self.output/(key+'_balance.png')
                cv2.imwrite(str(path),cv2.resize(prepared,None,fx=3,fy=3))
                value = wallet_number(read_ocr(path), key)
                if value is None:
                    # The narrow gold font becomes readable after removing its dark outline.
                    digits=screen[max(0,symbol.y-2):symbol.y+symbol.height-10,x+6:end]
                    for minimum in (170,200):
                        mask=cv2.inRange(cv2.cvtColor(digits,cv2.COLOR_BGR2HSV),(15,150,minimum),(40,255,255))
                        prepared=cv2.resize(255-mask,None,fx=4,fy=3)
                        prepared=cv2.copyMakeBorder(prepared,30,30,30,30,cv2.BORDER_CONSTANT,value=255)
                        cv2.imwrite(str(path),prepared)
                        lines=read_ocr(path)
                        value=wallet_number(lines,key)
                        if value is None and key == 'coin':
                            # The yellow-digit mask can remove tiny thousands dots.
                            # This crop is bounded by verified currency symbols;
                            # require digits only and agreement of both frames.
                            plain=''.join(lines).replace(' ','')
                            if re.fullmatch(r'\d{1,10}',plain):value=int(plain)
                        if value is not None:
                            break
                if value is None:
                    crop = screen[max(0,symbol.y-2):min(900,symbol.y+symbol.height+4),x:end]
                    prepared = cv2.copyMakeBorder(crop,8,8,8,8,cv2.BORDER_CONSTANT,value=(255,255,255))
                    cv2.imwrite(str(path),cv2.resize(prepared,None,fx=3,fy=3))
                    value = wallet_number(read_ocr(path), key)
                if value is None:
                    crop = screen[symbol.y+8:symbol.y+symbol.height-10,x:end]
                    prepared = cv2.copyMakeBorder(crop,8,8,8,8,cv2.BORDER_CONSTANT,value=(255,255,255))
                    cv2.imwrite(str(path),cv2.resize(prepared,None,fx=2,fy=2))
                    value = wallet_number(read_ocr(path), key)
                values['coins' if key == 'coin' else 'gold'] = value
            results.append(values)
        return {key:results[0][key] if results[0][key]==results[1][key] else None for key in results[0]}

    def chest(self):
        screen = self.device.screenshot()
        from .dock import DockDetector
        from .detector import FishingDetector
        from .states import FishingState
        if DockDetector().detect(screen).confirmed:
            phase=FishingDetector(area='dock').detect(screen).state
            if phase in (FishingState.READY,FishingState.RESULT,FishingState.FAILED,FishingState.SUCCESS):
                self.leave_chair('dock')
                screen=self.device.screenshot()
            elif phase in (FishingState.WAITING,FishingState.FISHING):
                raise RuntimeError('Đang có lượt câu bến tàu; chờ kết thúc trước khi quét rương.')
        if not self.match(screen,'chest_title'):
            basket = self.match(screen,'basket')
            if not basket:
                menu = self.world.match(screen,'menu')
                if not menu:
                    raise RuntimeError('Không nhận diện MENU để mở rương.')
                for attempt in range(2):
                    self.tap(menu.center,'MENU → rương đồ')
                    try:
                        basket = self.wait(lambda a:self.match(a,'basket'),'icon giỏ hàng',timeout=8)
                        break
                    except RuntimeError:
                        screen = self.device.screenshot()
                        menu = self.world.match(screen,'menu')
                        if attempt or not menu:
                            raise
            self.tap(basket.center,'Mở rương đồ')
            self.wait(lambda a:self.match(a,'chest_title'),'Rương đồ',timeout=10)
        # Start from top even if the chest remembers its previous scroll offset.
        stable_top = 0
        for _ in range(30):
            before = self.device.screenshot()[310:760,450:1140].copy()
            self.device.swipe(790,360,790,730,400)
            self.sleep(.9)
            after = self.device.screenshot()[310:760,450:1140]
            stable_top = stable_top+1 if viewport_still(before,after) else 0
            if stable_top >= 2:
                break
        else:
            raise RuntimeError('Chưa xác nhận đầu danh sách rương; không kết luận thiếu vật phẩm.')
        tickets = {key:{'status':'unknown','expires_on':None} for key in TICKETS}
        stocks = {key:None for key in BAITS}
        found_tickets, found_baits = set(), set()
        uncertain_baits = set()
        visited = set()
        inspected_cells = 0
        unreadable = False
        complete = False
        for page in range(30):
            screen = self.device.screenshot()
            if not self.match(screen,'chest_title'):
                raise RuntimeError('Mất xác nhận rương trong lúc quét.')
            cv2.imwrite(str(self.output/f'chest_page_{page:02d}.png'),screen)
            # Full cells only; partial rows are handled on the next overlapping page.
            mask = cv2.inRange(screen[310:760,450:1140],(200,170,130),(255,230,205))
            contours,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            blue_cells = [cv2.boundingRect(c) for c in contours]
            rows = sorted({y for x,y,w,h in blue_cells if 105 <= w <= 135 and 105 <= h <= 135})
            # Selected cells turn white: infer their slot from the neighboring blue cells.
            cells = [(10+136*column,y,125,125) for y in rows for column in range(5)]
            for x,y,w,h in cells:
                if not 105 <= w <= 135 or not 105 <= h <= 135:
                    continue
                x,y = x+450,y+310
                inspected_cells += 1
                icon = screen[y+25:y+100,x+20:x+105]
                # Empty blue cells are not item observations.
                if float(np.std(icon[:,:,2])) < 4:
                    continue
                candidates = [('ticket',key) for key in TICKETS if self.match(icon,key)]
                candidates += [('bait',key) for key in BAITS if self.match(icon,key+'_bait')]
                if not candidates:
                    continue
                if len(candidates) != 1:
                    unreadable = True
                    continue
                visual_kind, visual_key = candidates[0]
                fingerprint = cell_fingerprint(screen[y+4:y+100,x+20:x+118])
                if fingerprint in visited:
                    continue
                detail = self.select_chest_cell(x,y,w,h)
                if detail is None:
                    unreadable = True
                    continue
                visited.add(fingerprint)
                lines = self.text(detail,(1150,320,1580,750),'item_detail')
                kind,key = item_kind(lines)
                if kind is not None and (kind,key) != (visual_kind,visual_key):
                    raise RuntimeError('Tên item và sprite trong rương không khớp; không tự mua.')
                kind,key = visual_kind,visual_key
                verify = self.text(self.device.screenshot(),(1150,320,1580,750),'item_detail_verify')
                checked_kind = item_kind(verify)
                if checked_kind != (None,None) and checked_kind != (kind,key):
                    raise RuntimeError('Thông tin item chưa ổn định; không kết luận thiếu vật phẩm.')
                if kind == 'ticket':
                    found_tickets.add(key)
                    info = ticket_info(lines)
                    if info != ticket_info(verify):
                        info = {'status':'active','expires_on':None}
                    previous = tickets[key]
                    if previous['status'] != 'active' or (info['status'] == 'active' and (info['expires_on'] or '') > (previous['expires_on'] or '')):
                        tickets[key] = info
                    self.screen = detail
                    self.event('INVENTORY_TICKET',ticket=key,**info)
                else:
                    found_baits.add(key)
                    bounds = (x+w-65,y+8,x+w-3,y+40)
                    count = number(' '.join(self.text(detail,bounds,'bait_count')))
                    checked = number(' '.join(self.text(self.device.screenshot(),bounds,'bait_count_verify')))
                    if count is None or count != checked:
                        uncertain_baits.add(key)
                    if key in stocks and stocks[key] is not None and count is not None and count == checked:
                        stocks[key] += count
                    else:
                        stocks[key] = count if count == checked else None
                    self.screen = detail
                    self.event('INVENTORY_BAIT',bait=key,remaining=stocks[key])
            before = self.device.screenshot()[310:760,450:1140].copy()
            self.device.swipe(790,715,790,390,450)
            self.sleep(.9)
            after = self.device.screenshot()[310:760,450:1140]
            if viewport_still(before,after):
                self.sleep(.9)
                self.device.swipe(790,715,790,390,450)
                self.sleep(.9)
                if viewport_still(after,self.device.screenshot()[310:760,450:1140]):
                    complete = True
                    break
        complete = complete and not unreadable and inspected_cells > 0
        if complete:
            for key in TICKETS.keys()-found_tickets:
                tickets[key] = {'status':'missing','expires_on':None}
            for key in BAITS.keys()-found_baits:
                stocks[key] = 0
        for key in uncertain_baits:
            stocks[key] = None
        self.tap((1510,35),'Đóng rương đồ')
        self.wait(lambda a:not self.match(a,'chest_title'),'đóng rương',timeout=8)
        self.sleep(.9)
        return {'tickets':tickets,'bait_stocks':stocks,'scan_complete':complete,'wallet':self.wallet(),
                'inventory_observed_at':datetime.now().isoformat()}

    def select_chest_cell(self, x, y, w, h):
        """Verify a dropped/delayed selection before marking an item unreadable."""
        for attempt in range(3):
            self.tap((x+w//2,y+h//2),'Đọc thông tin item trong rương')
            for _ in range(3):
                self.sleep(.4)
                detail = self.device.screenshot()
                if not self.match(detail,'chest_title'):
                    raise RuntimeError('Mất xác nhận rương khi chọn vật phẩm; đã dừng.')
                border = detail[y:y+h,x:x+w]
                amber = cv2.inRange(cv2.cvtColor(border,cv2.COLOR_BGR2HSV),(15,120,140),(40,255,255))
                if np.mean(amber[:8]>0) >= .08 and np.mean(amber[:,:8]>0) >= .08:
                    return detail
            self.screen = detail
            self.event('INVENTORY_SELECTION_RETRY',point=(x+w//2,y+h//2),attempt=attempt+1)
        return None

    def buy_ticket(self, key, wallet, observation=None):
        name,cost,currency = TICKETS[key]
        ensure_funds(wallet,currency,cost)
        # Start's complete scan is reusable. Direct callers obtain one scan themselves.
        observation = self.chest() if observation is None else copy.deepcopy(observation)
        status = observation['tickets'][key]['status']
        if status == 'active':
            self.event('TICKET_PURCHASE_SKIPPED',ticket=key,reason='already_owned')
            return observation
        if status != 'missing' or not observation['scan_complete']:
            raise RuntimeError('Chưa xác nhận thiếu vé sau quét toàn rương; không tự mua.')
        wallet = observation['wallet']
        ensure_funds(wallet,currency,cost)
        if key == 'dock':
            self.open_dock_shop()
        else:
            self.open_shop()
            self.button('shop_menu','Cửa Hàng Cá')
            self.wait(lambda a:self.world.match(a,'fish_shop'),'cửa hàng cá')
        icon = self.wait(lambda a:self.match(a,key),name,timeout=10)
        self.tap(icon.center,'Chọn '+name)
        self.wait(lambda a:self.selected_ticket(a,key),
                  'thông tin '+name,timeout=10)
        lines = self.text(self.device.screenshot(),(300,300,1400,750),'ticket_shop')
        if not self.selected_ticket(self.device.screenshot(),key):
            raise RuntimeError('Không xác nhận đúng loại vé trong shop; chưa mua.')
        # Shop exposes spendable gold separately. The chest close button obscures it,
        # and outside some maps show a combined total, so recheck here before payment.
        wallet = self.wallet()
        ensure_funds(wallet,currency,cost)
        self.button('buy','Mua '+name)
        # The payment popup must identify both the product and exact price.
        self.wait(lambda a:self.ticket_confirmation(a,key),
                  'popup xác nhận '+name,timeout=10)
        if not self.ticket_confirmation(self.device.screenshot(),key):
            raise RuntimeError('Chưa xác minh tên/giá vé trên popup xác nhận; chưa thanh toán.')
        ensure_funds(wallet,currency,cost)
        point = self.payment_point(currency)
        self.event('TICKET_PURCHASE_PENDING',ticket=key)
        self.tap(point, 'Thanh toán '+name)
        self.wait(lambda a:self.world.match(a,'ok'),'kết quả mua vé',timeout=10)
        receipt = self.device.screenshot()
        lines = self.text(receipt,(400,250,1200,650),'ticket_receipt')
        if 'thanh cong' not in normalize(' '.join(lines)) or not self.ticket_identity(receipt,lines,key):
            raise RuntimeError('Chưa xác nhận mua vé thành công; không mua lặp.')
        observation['tickets'][key]=ticket_info(lines)
        observation['wallet']=dict(wallet)
        observation['wallet'][currency]-=cost
        observation['inventory_updated_at']=datetime.now().isoformat()
        self.event('TICKET_PURCHASE_CONFIRMED',ticket=key,
                   expires_on=observation['tickets'][key]['expires_on'],wallet=observation['wallet'])
        self.button('ok','Đóng biên nhận vé')
        self.tap((200,650),'Đóng shop sau mua vé')
        return observation

    def ticket_identity(self, screen, lines, key):
        if item_kind(lines) == ('ticket',key):
            return True
        # Exact observed lettering avoids fuzzy guesses such as OCR's "Cé M$p".
        return key == 'ca_map' and self.match(screen[250:650,400:1200],'shark_ticket_name') is not None

    def selected_ticket(self, screen, key):
        if key=='ca_noc' and self.match(screen[460:590,450:1000],'loc_shop_name') is not None:
            return True
        return item_kind(self.text(screen,(300,300,1400,750),'ticket_shop'))==('ticket',key)

    def ticket_confirmation(self, screen, key):
        if key in ('ca_noc','ca_map') and self.match(screen[450:550,600:1000],'ticket_quantity_one') is None:
            return False
        # Exact observed product + price artwork with an independent quantity
        # anchor. No OCR is needed on this verified layout.
        if (key=='ca_noc' and self.match(screen[375:435,480:1130],'loc_confirmation') is not None
                and self.match(screen[375:435,940:1120],'loc_price') is not None
                and self.match(screen[450:550,600:1000],'ticket_quantity_one') is not None):
            return True
        lines = self.text(screen,(400,250,1200,650),'ticket_confirmation')
        _,cost,currency = TICKETS[key]
        plain = normalize(' '.join(lines)).replace('.','').replace(',','')
        payment = 'xu' if currency == 'coins' else 'luong'
        if key == 'ca_map' and self.match(screen[450:550,600:1000],'ticket_quantity_one') is None:
            return False
        if item_kind(lines) == ('ticket',key) and re.search(rf'\b{cost}\s*{payment}\b',plain):
            return True
        # This complete line includes the specific product, 2-day duration and
        # exact 2-gold price. Also require the unchanged single-item selector.
        return (key == 'ca_map' and
                self.match(screen[300:450,400:1200],'shark_confirmation') is not None and
                self.match(screen[375:430,950:1120],'shark_price') is not None and
                self.match(screen[450:550,600:1000],'ticket_quantity_one') is not None)

    def payment_point(self, currency):
        if currency == 'coins':
            return self.wait(lambda a:self.world.match(a,'buy_coin'),'Mua bằng xu',timeout=8).center
        screen = self.device.screenshot()
        button = self.match(screen[400:850,400:1200],'buy_gold')
        if button:
            return button.center[0]+400,button.center[1]+400
        # Fallback for other supported layouts: OCR plus button-color evidence.
        from fishing.quest import read_ocr_boxes
        path = self.output/'payment_buttons.png'
        cv2.imwrite(str(path),screen)
        candidates = []
        for line in read_ocr_boxes(path):
            plain = normalize(line['text'])
            if 'mua' in plain and 'luong' in plain:
                x,y,w,h = [line[k] for k in ('x','y','width','height')]
                point = round(x+w/2),round(y+h/2)
                if 400 < point[0] < 1200 and 400 < point[1] < 850:
                    hsv = cv2.cvtColor(screen[max(0,point[1]-25):point[1]+25,max(0,point[0]-80):point[0]+80],cv2.COLOR_BGR2HSV)
                    if np.mean(cv2.inRange(hsv,(15,100,120),(40,255,255))>0) > .25:
                        candidates.append(point)
        if len(candidates) != 1:
            raise RuntimeError('Chưa nhận diện chắc nút Mua bằng lượng; chưa thanh toán.')
        return candidates[0]

    def open_dock_shop(self):
        from fishing.dock import DockDetector
        from fishing.detector import FishingDetector
        from fishing.states import FishingState
        phase=FishingDetector(area='dock').detect(self.device.screenshot()).state
        if phase in (FishingState.READY,FishingState.RESULT,FishingState.FAILED,FishingState.SUCCESS,FishingState.OUT_OF_BAIT):
            self.leave_chair('dock')
        elif phase in (FishingState.WAITING,FishingState.FISHING):
            raise RuntimeError('Đang có lượt câu; không rời ghế để mua mồi hoặc vé.')
        detector=DockDetector()
        sign=self.wait(lambda a:detector.detect(a).shop,'shop Bến Tàu')
        self.tap((sign.center[0],sign.center[1]+185),'Mở shop Bến Tàu')
        menu=self.wait(lambda a:detector.match(a,'shop_menu'),'menu shop Bến Tàu')
        self.tap(menu.center,'Cửa hàng Bến Tàu')

    def buy_dock_bait(self, quantity, wallet):
        if type(quantity) is not int or not 1 <= quantity <= 50:
            raise ValueError('Số mồi phải từ 1 đến 50')
        ensure_funds(wallet,'coins',quantity*50)
        from fishing.dock import DockDetector
        detector = DockDetector()
        self.open_dock_shop()
        icon = self.wait(lambda a:self.match(a,'dock_bait'),'Mồi Câu Cá Trâm',timeout=10)
        self.tap(icon.center,'Chọn Mồi Câu Cá Trâm')
        self.wait(lambda a:detector.detect(a).bait_selected,'Mồi Câu Cá Trâm giá 50 xu',timeout=8)
        self.button('buy','Mua mồi bến tàu')
        self.wait(lambda a:item_kind(self.text(a,(400,250,1200,650),'dock_bait_dialog')) == ('bait','dock'),
                  'popup số lượng mồi bến tàu',timeout=10)
        self.tap((798,500),'Nhập số lượng mồi')
        self.wait(lambda a:self.world.match(a,'input_ok'),'ô nhập Android',timeout=8)
        self.device.type_number(quantity)
        self.button('input_ok','OK số lượng')
        lines = self.text(self.device.screenshot(),(400,250,1200,650),'dock_bait_confirmation')
        plain = normalize(' '.join(lines)).replace('.','').replace(',','')
        if item_kind(lines) != ('bait','dock') or not re.search(rf'\bmua\s+{quantity}\b',plain) or not re.search(rf'\b{quantity*50}\s*xu\b',plain):
            raise RuntimeError('Chưa xác minh số lượng/giá mồi bến tàu; chưa thanh toán.')
        ensure_funds(wallet,'coins',quantity*50)
        point = self.payment_point('coins')
        self.event('PURCHASE_PENDING',quantity=quantity)
        self.tap(point,'Thanh toán mồi bến tàu')
        self.wait(lambda a:self.world.match(a,'ok'),'biên nhận mồi bến tàu',timeout=10)
        lines = self.text(self.device.screenshot(),(400,250,1200,650),'dock_bait_receipt')
        if item_kind(lines) != ('bait','dock') or 'thanh cong' not in normalize(' '.join(lines)):
            raise RuntimeError('Chưa xác nhận mua mồi bến tàu; không mua lặp.')
        self.event('DOCK_PURCHASE_CONFIRMED',quantity=quantity)
        self.button('ok','Đóng biên nhận')
        self.tap((200,650),'Đóng shop bến tàu')
        return quantity
