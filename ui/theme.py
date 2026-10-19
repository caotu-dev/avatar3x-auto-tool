"""Offline ttk theme for the current Avatar Fishing Bot dashboard."""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from functools import lru_cache
TOKENS = {'color': {'brand': {'blue': '#1459E8', 'blueSubtle': '#E6F0FF'},
           'background': {'app': '#F1F7FF',
                          'surface': '#FFFFFF',
                          'surfaceAlt': '#F7FAFF',
                          'surfaceMuted': '#EEF4FD'},
           'text': {'primary': '#182F63',
                    'secondary': '#48618E',
                    'muted': '#526B95',
                    'onDark': '#FFFFFF',
                    'onBrand': '#FFFFFF',
                    'disabled': '#586D8C'},
           'border': {'focus': '#125CDE', 'strong': '#ADC4E5'},
           'semantic': {'success': '#277D24', 'danger': '#BD2C3E'},
           'metric': {'castBg': '#EAF8F4',
                      'biteBg': '#FFF5E5',
                      'missBg': '#EAF4FF',
                      'baitBg': '#FFF0EC'}},
 'typography': {'fontFamily': 'Bahnschrift',
                'fontFamilyNumeric': 'Consolas',
                'sizePx': {'body': 14,
                           'bodyLarge': 15,
                           'caption': 13,
                           'sectionTitle': 18,
                           'pageTitle': 34,
                           'timer': 36,
                           'metric': 23}},
 'sizingPx': {'headerHeight': 168, 'tableRowHeight': 38, 'rowGap': 14}}

# V2 tokens are bundled locally and adapted to the existing theme contract.
import json
V2 = json.loads((Path(__file__).resolve().parent / 'assets/design_tokens_v2.json').read_text(encoding='utf-8'))
TOKENS['color']['background'].update(app=V2['colors']['background'], surfaceMuted=V2['colors']['surfaceBlue'])
TOKENS['color']['text'].update(primary=V2['colors']['textPrimary'], secondary=V2['colors']['textSecondary'])
TOKENS['color']['brand']['blue'] = V2['colors']['primary']
TOKENS['sizingPx'].update(headerHeight=177, tableRowHeight=42)

# Measured approved 1534 x 1025 reference, in 96-DPI layout pixels.
TOKENS['color']['background'].update(app='#E8F3FE', surfaceAlt='#F3F9FE', surfaceMuted='#E7F1FD')
TOKENS['color']['text'].update(primary='#102D72', secondary='#5272A9', muted='#5272A9')
TOKENS['color']['text']['heading'] = '#001772'
TOKENS['color']['background']['status'] = '#E7F3FE'
TOKENS['color']['background']['timer'] = '#DAEBFD'
TOKENS['color']['brand'].update(blue='#1267F5', blueSubtle='#EAF3FF')
TOKENS['color']['border'].update(strong='#C9DFF9')
TOKENS['color']['metric'].update(castBg='#E5F5FE', biteBg='#FEF3E1', missBg='#FEEAEE', baitBg='#FEEFE9')
TOKENS['color']['progress'] = dict(border='#C9DFF9', track='#CAD9E9', start='#009AF0', end='#00C8EC', stripe='#22D4F1')
TOKENS['typography']['sizePx'].update(body=17, bodyLarge=18, caption=15, sectionTitle=23, pageTitle=48, metric=23)
TOKENS['sizingPx'].update(headerHeight=148, tableRowHeight=60)
TILE_COLORS = dict(ecological='#EFEEFE', dock='#E7F8FD', ticket_ro='#E8F6FE', ticket_map='#FEEEEE', ticket_loc='#E9F9F6', ticket_dock='#EAF3FE')

def token(path):
    value = TOKENS
    for key in path.split('.'):
        value = value[key]
    return value

def font(name='body', bold=False, numeric=False):
    family = token('typography.fontFamilyNumeric' if numeric else 'typography.fontFamily')
    # Convert reference 96-DPI pixels to points, so Tk/Windows text scaling applies.
    return (family, round(token('typography.sizePx.' + name) * 72 / 96),
            'bold' if bold else 'normal')


ASSET_DIR = Path(__file__).resolve().parent / 'assets'

def asset(root, name):
    """Keep PhotoImage ownership on the Tk root, including frozen builds."""
    cache = getattr(root, '_ui_assets', None)
    if cache is None:
        cache = root._ui_assets = {}
    if name not in cache:
        import cv2
        approved = ASSET_DIR / 'approved' / (name + '.png')
        source = cv2.imread(str(approved if approved.exists() else ASSET_DIR / (name + '.png')), cv2.IMREAD_UNCHANGED)
        icon = (name.startswith(('fish_', 'section_', 'metric_', 'overview_', 'ticket_', 'currency_', 'tab_', 'panel_'))
                or name in ('clock', 'button_play', 'button_pause', 'button_stop', 'button_folder'))
        if icon and not approved.exists():
            size = 36 if name.startswith(('fish_', 'metric_', 'overview_')) else 46 if name.startswith('ticket_') else 32
            scale = size / max(source.shape[:2])
            source = cv2.resize(source, (max(1, round(source.shape[1]*scale)), max(1, round(source.shape[0]*scale))), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        if name.startswith('fish_') and approved.exists():
            source=cv2.copyMakeBorder(source,0,0,0,7,cv2.BORDER_CONSTANT,value=(0,0,0,0))
        cache[name] = tk.PhotoImage(master=root, data=cv2.imencode('.png', source)[1].tobytes())
    return cache[name]


def rounded_surface(root, name, fill, border=None, radius=8):
    """Small antialiased nine-slice surfaces; controls remain native ttk widgets."""
    import cv2
    import numpy as np
    cache = getattr(root, '_surface_assets', None)
    if cache is None:
        cache = root._surface_assets = {}
    if name not in cache:
        size, factor = 48, 4
        backdrop = token('color.background.app') if name=='card' else '#FFFFFF'
        rgba = np.full((size*factor, size*factor,4),255,dtype=np.uint8)
        rgba[:,:,:3] = tuple(int(backdrop[i:i+2],16) for i in (5,3,1))
        def rounded(color, inset):
            rgb = tuple(int(color[i:i+2],16) for i in (5,3,1)) + (255,)
            lo, hi, r = inset*factor, (size-inset)*factor-1, (radius-inset)*factor
            cv2.rectangle(rgba,(lo+r,lo),(hi-r,hi),rgb,-1)
            cv2.rectangle(rgba,(lo,lo+r),(hi,hi-r),rgb,-1)
            for x in (lo+r,hi-r):
                for y in (lo+r,hi-r): cv2.circle(rgba,(x,y),r,rgb,-1)
        rounded(border or fill,0)
        if border: rounded(fill,1)
        rgba = cv2.resize(rgba,(size,size),interpolation=cv2.INTER_AREA)
        rgba = rgba[:,:,:3]
        cache[name] = tk.PhotoImage(master=root,data=cv2.imencode('.png',rgba)[1].tobytes())
    return cache[name]


def apply_theme(root):
    import tkinter.font as tkfont
    if 'Bahnschrift' not in tkfont.families(root):
        TOKENS['typography']['fontFamily'] = 'Segoe UI'
    style = ttk.Style(root)
    style.theme_use('clam')
    c = token
    surface, ink = c('color.background.surface'), c('color.text.primary')
    style.configure('.', font=font(), foreground=ink)
    style.configure('TFrame', background=c('color.background.app'))
    style.element_create('Rounded.Card', 'image', rounded_surface(root, 'card', '#FFFFFF', '#D9EAFE', 14), border=14, sticky='nswe')
    style.layout('Card.TFrame', [('Rounded.Card', {'sticky': 'nswe'})])
    style.configure('Card.TFrame', background=c('color.background.app'), borderwidth=0)
    for name in ('TLabel', 'Card.TLabel', 'Section.TLabel'):
        style.configure(name, background=surface, foreground=c('color.text.heading') if name=='Section.TLabel' else ink,
                        font=font('sectionTitle', True) if name == 'Section.TLabel' else font('bodyLarge'))
    style.configure('Status.TLabel', background=c('color.background.status'),
                    foreground=c('color.text.secondary'), font=font('caption'))
    style.configure('Inner.TFrame', background=surface, borderwidth=0)
    style.configure('TCheckbutton', font=font('bodyLarge'), background=surface, padding=(0, 10),
                    indicatorsize=20, indicatorbackground=surface, indicatorforeground=ink)
    style.map('TCheckbutton', background=[('active', surface)], foreground=[('disabled', c('color.text.disabled'))])
    style.element_create('Rounded.Check', 'image', asset(root, 'check'),
                         ('disabled', 'selected', asset(root, 'check_selected_disabled')),
                         ('disabled', asset(root, 'check_disabled')),
                         ('selected', asset(root, 'check_selected')))
    style.layout('TCheckbutton', [('Checkbutton.padding', {'sticky': 'nswe', 'children': [
        ('Rounded.Check', {'side': 'left', 'sticky': 'w'}),
        ('Checkbutton.focus', {'side': 'left', 'sticky': 'w', 'children': [
            ('Checkbutton.label', {'sticky': 'nswe'})]})]})])

    for name, normal, hover, foreground in [('TButton', 'button', 'button_hover', 'color.text.primary'),
                                            ('Accent.TButton', 'primary', 'primary_hover', 'color.text.onBrand'),
                                            ('Blue.TButton', 'blue', 'blue_hover', 'color.text.onBrand'),
                                            ('Danger.TButton', 'danger', 'danger', 'color.semantic.danger'),
                                            ('ModeSelected.TButton', 'tab_selected', 'tab_selected', 'color.brand.blue')]:
        element = name + '.surface'
        style.element_create(element, 'image', rounded_surface(root, normal, {'primary':'#49CB91','blue':'#1267F5','danger':'#FFD4DD','tab_selected':'#E5F2FF'}.get(normal,'#F7FBFF'), {'primary':'#06A55E','danger':'#FF3559'}.get(normal,'#A8CEFF')),
                             ('disabled', rounded_surface(root, normal+'_disabled', {'primary':'#D7F1E3','danger':'#FCE0E6'}.get(normal,'#EDF3FA'), '#CDDEF2')),
                             ('active', rounded_surface(root, hover, {'primary_hover':'#32BC7D','blue_hover':'#0757DE','danger':'#FFC3CF'}.get(hover,'#E6F2FF'), '#75AEF9')), ('focus', asset(root, 'button_hover')),
                             border=8, sticky='nswe')
        style.layout(name, [(element, {'sticky': 'nswe', 'children': [
            ('Button.focus', {'sticky': 'nswe', 'children': [
                ('Button.padding', {'sticky': 'nswe', 'children': [
                    ('Button.label', {'sticky': 'nswe'})]})]})]})])
        style.configure(name, background=c('color.background.app'), borderwidth=0, relief='flat', padding=(12, 2), foreground=c(foreground),
                        font=font('bodyLarge', name == 'Accent.TButton'), focuscolor=c('color.border.focus'))
        style.map(name, foreground=[('disabled', c('color.text.disabled'))])
    style.layout('Nav.Card.TFrame',[('TButton.surface',{'sticky':'nswe'})])
    style.configure('Nav.Card.TFrame',background=c('color.background.app'),borderwidth=0)
    style.configure('Nav.TButton', padding=(7,0,17,0), font=font('body',True))
    style.configure('Folder.Nav.TButton',padding=(2,0,22,0))
    style.configure('Vertical.TScrollbar', background='#D6E4F2', troughcolor='#F0F6FC', bordercolor='#F0F6FC', arrowcolor='#5272A9', arrowsize=14, relief='flat')
    style.configure('Compact.TButton', padding=(8, 4), font=font())
    for name,base in [('Small.TButton','TButton'),('SmallAccent.TButton','Accent.TButton'),('SmallDanger.TButton','Danger.TButton')]:
        style.layout(name,style.layout(base))
        style.configure(name,padding=(3,5),font=('Segoe UI',9))
    style.configure('SmallAccent.TButton',foreground=c('color.text.onBrand'))
    style.configure('SmallDanger.TButton',foreground=c('color.semantic.danger'))
    style.configure('TNotebook', background=c('color.background.app'), borderwidth=0, bordercolor=c('color.background.app'), lightcolor=c('color.background.app'), darkcolor=c('color.background.app'), tabmargins=(0,0,0,12), padding=0)
    style.layout('Workspace.TNotebook.Tab', [])
    style.configure('Workspace.TNotebook', tabmargins=0)
    for name in ('TSpinbox', 'TCombobox'):
        style.configure(name, padding=8, fieldbackground=surface, bordercolor=c('color.border.strong'), arrowcolor=ink)
    for key in ('castBg','biteBg','missBg','baitBg','stock', *TILE_COLORS):
        element = 'Tile.' + key
        style.element_create(element, 'image', rounded_surface(root, key, TILE_COLORS.get(key, TOKENS['color']['metric'].get(key, token('color.background.timer'))), radius=8), border=8, sticky='nswe')
        style.layout(key + '.TFrame', [(element, {'sticky': 'nswe'})])
        style.configure(key+'.TFrame', background=surface, borderwidth=0)
    style.configure('Treeview.Item',indicatorsize=0,indicatormargins=(0,0,13,0))
    style.configure('Treeview', indent=15, font=(token('typography.fontFamily'),13), rowheight=c('sizingPx.tableRowHeight'), background=surface, fieldbackground=surface, borderwidth=1, bordercolor='#C9DFF9', lightcolor='#C9DFF9', darkcolor='#C9DFF9', relief='solid')
    style.configure('Treeview.Heading', background=c('color.background.surfaceMuted'), foreground=c('color.text.secondary'), padding=(5, 12), font=font('body'), relief='flat')
    style.map('Treeview', background=[('selected', c('color.brand.blueSubtle'))], foreground=[('selected', ink)])
    style.configure('SelectedFish.TLabel', background='#DDEBFF', foreground=c('color.text.primary'), font=font('bodyLarge'))
    root.configure(background=c('color.background.app'))


@lru_cache(maxsize=2)
def _header_source(variant):
    import cv2
    approved=ASSET_DIR/'approved'/'banner.png'
    return cv2.imread(str(approved if approved.exists() else ASSET_DIR/f'header_{variant}_168.png'))


def banner_pixels(width,height):
    import cv2
    variant=min((1024,1280,1440,1536,1920),key=lambda size:abs(size-width))
    source=_header_source(variant)
    width,height=max(1,width),max(1,height)
    scale=max(width/source.shape[1],height/source.shape[0])
    resized=cv2.resize(source,(max(width,round(source.shape[1]*scale)),max(height,round(source.shape[0]*scale))),interpolation=cv2.INTER_AREA)
    x=(resized.shape[1]-width)//2;y=(resized.shape[0]-height)//2
    return resized[y:y+height,x:x+width]


def canvas_bitmap(canvas,pixels):
    import cv2
    height,width=pixels.shape[:2]
    payload=f'P6\n{width} {height}\n255\n'.encode('ascii')+cv2.cvtColor(pixels,cv2.COLOR_BGR2RGB).tobytes()
    canvas.background_image=tk.PhotoImage(master=canvas,data=payload,format='PPM')
    canvas.create_image(0,0,anchor='nw',image=canvas.background_image,tags='background')
    canvas.tag_lower('background')


def banner(parent):
    canvas=tk.Canvas(parent,height=148,highlightthickness=0)
    def draw():
        canvas._banner_job=None
        width,height=canvas._banner_pending
        if (width,height)==getattr(canvas,'_banner_size',None):return
        canvas._banner_size=(width,height)
        canvas.delete('all')
        canvas_bitmap(canvas,banner_pixels(width,height))
        if not (ASSET_DIR/'approved'/'banner.png').exists():
            x=round(width*.192)
            canvas.create_text(x,39,anchor='w',text='Avatools 3x',fill=token('color.text.onDark'),font=('Segoe UI',-token('typography.sizePx.pageTitle'),'bold'))
            canvas.create_text(x,77,anchor='w',text='Săn cá tự động • Dễ dùng • Hiệu quả',fill=token('color.text.onDark'),font=('Segoe UI',-20))
        if hasattr(canvas,'refresh_nav'):canvas.refresh_nav()
    def resize(event):
        canvas._banner_pending=(max(1,event.width),max(1,event.height))
        previous=getattr(canvas,'_banner_job',None)
        if previous is not None:canvas.after_cancel(previous)
        if not hasattr(canvas,'_banner_size'):
            draw()
        else:
            canvas._banner_job=canvas.after(30,draw)
    def dispose(event):
        if event.widget is canvas and getattr(canvas,'_banner_job',None) is not None:
            canvas.after_cancel(canvas._banner_job)
    canvas.bind('<Configure>',resize)
    canvas.bind('<Destroy>',dispose)
    return canvas
