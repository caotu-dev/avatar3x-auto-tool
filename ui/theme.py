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
 'typography': {'fontFamily': 'Segoe UI',
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
        cache[name] = tk.PhotoImage(master=root, file=str(ASSET_DIR / (name + '.png')))
        image=cache[name]
        icon=(name.startswith(('fish_','section_','metric_','overview_','ticket_','currency_','tab_','panel_'))
              or name in ('clock','button_play','button_pause','button_stop','button_folder'))
        if icon:
            import math
            size=36 if name.startswith('fish_') else 32 if name=='clock' else 24
            if max(image.width(),image.height())>size:
                cache[name]=image.subsample(math.ceil(max(image.width(),image.height())/size))
    return cache[name]


def apply_theme(root):
    style = ttk.Style(root)
    style.theme_use('clam')
    c = token
    surface, ink = c('color.background.surface'), c('color.text.primary')
    style.configure('.', font=font(), foreground=ink)
    style.configure('TFrame', background=c('color.background.app'))
    style.element_create('Rounded.Card', 'image', asset(root, 'card'), border=12, sticky='nswe')
    style.layout('Card.TFrame', [('Rounded.Card', {'sticky': 'nswe'})])
    style.configure('Card.TFrame', background=c('color.background.app'), borderwidth=0)
    for name in ('TLabel', 'Card.TLabel', 'Section.TLabel'):
        style.configure(name, background=surface, foreground=ink,
                        font=font('sectionTitle', True) if name == 'Section.TLabel' else font('bodyLarge'))
    style.configure('Status.TLabel', background=c('color.background.surfaceMuted'),
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
        style.element_create(element, 'image', asset(root, normal),
                             ('disabled', asset(root, 'button_disabled')),
                             ('active', asset(root, hover)), ('focus', asset(root, 'button_hover')),
                             border=8, sticky='nswe')
        style.layout(name, [(element, {'sticky': 'nswe', 'children': [
            ('Button.focus', {'sticky': 'nswe', 'children': [
                ('Button.padding', {'sticky': 'nswe', 'children': [
                    ('Button.label', {'sticky': 'nswe'})]})]})]})])
        style.configure(name, padding=(12, 4), foreground=c(foreground),
                        font=font('bodyLarge', name == 'Accent.TButton'), focuscolor=c('color.border.focus'))
        style.map(name, foreground=[('disabled', c('color.text.disabled'))])
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
    for key in ('castBg','biteBg','missBg','baitBg','stock'):
        element = 'Tile.' + key
        style.element_create(element, 'image', asset(root, 'tile_' + key), border=10, sticky='nswe')
        style.layout(key + '.TFrame', [(element, {'sticky': 'nswe'})])
    style.configure('Treeview', font=font('bodyLarge'), rowheight=c('sizingPx.tableRowHeight'), background=surface, fieldbackground=surface, borderwidth=0)
    style.configure('Treeview.Heading', background=c('color.background.surfaceMuted'), foreground=c('color.text.secondary'), padding=(8, 10), font=font('body'), relief='flat')
    style.map('Treeview', background=[('selected', c('color.brand.blueSubtle'))], foreground=[('selected', ink)])
    style.configure('SelectedFish.TLabel', background='#DDEBFF', foreground=c('color.text.primary'), font=font('bodyLarge'))
    root.configure(background=c('color.background.app'))


@lru_cache(maxsize=2)
def _header_source(variant):
    import cv2
    return cv2.imread(str(ASSET_DIR/f'header_{variant}_168.png'))


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
    canvas=tk.Canvas(parent,height=144,highlightthickness=0)
    def draw():
        canvas._banner_job=None
        width,height=canvas._banner_pending
        if (width,height)==getattr(canvas,'_banner_size',None):return
        canvas._banner_size=(width,height)
        canvas.delete('all')
        canvas_bitmap(canvas,banner_pixels(width,height))
        x=round(width*.198)
        canvas.create_text(x,32,anchor='w',text='AVATAR • FISHING BOT',fill=token('color.text.onDark'),font=font('pageTitle',True))
        canvas.create_text(x,66,anchor='w',text='Săn cá tự động • Dễ dùng • Hiệu quả',fill=token('color.text.onDark'),font=font('bodyLarge'))
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
