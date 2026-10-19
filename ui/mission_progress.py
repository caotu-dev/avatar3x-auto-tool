"""Weighted mission footer with a bounded, GUI-thread stripe animation."""
import tkinter as tk
from tkinter import ttk

from ui.theme import token


def mission_totals(targets):
    """Weight by fish quantities; surplus of one fish cannot finish another."""
    required = sum(max(0, target['required']) for target in targets)
    completed = sum(min(max(0, target['current']), max(0, target['required']))
                    for target in targets)
    return completed, required


class MissionProgress(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style='Inner.TFrame')
        self.completed = self.required = 0
        self._draw_signature = None
        self._animation_job = None
        self._phase = 0
        self._frames = []
        heading = ttk.Frame(self, style='Inner.TFrame')
        heading.pack(fill='x')
        ttk.Label(heading, text='Tiến độ tổng', foreground=token('color.text.heading'),font=('Segoe UI',13,'bold')).pack(side='left')
        self.summary = tk.StringVar(value='—  Chưa đặt mục tiêu')
        ttk.Label(heading, textvariable=self.summary, font=('Segoe UI',13),
                  foreground=token('color.brand.blue')).pack(side='right')
        self.canvas = tk.Canvas(self, height=36, width=1, highlightthickness=0,
                                background=token('color.background.surface'))
        self.canvas.pack(fill='x', pady=(8, 0))
        self.canvas.bind('<Configure>', self.draw)
        self.canvas.bind('<Map>', lambda event: self._update_animation())
        self.canvas.bind('<Unmap>', lambda event: self._stop_animation())
        self.canvas.bind('<Destroy>', lambda event: self._stop_animation())

    def _stop_animation(self):
        if self._animation_job is not None:
            self.after_cancel(self._animation_job)
            self._animation_job = None

    def _update_animation(self):
        active = bool(self._frames) and 0 < self.completed < self.required and self.canvas.winfo_ismapped()
        if not active:
            self._stop_animation()
        elif self._animation_job is None:
            self._animation_job = self.after(60, self._animate)

    def _animate(self):
        self._animation_job = None
        if not self.canvas.winfo_ismapped() or not 0 < self.completed < self.required or not self._frames:
            return
        self._phase = (self._phase + 1) % len(self._frames)
        self.canvas.itemconfigure(self._fill_item, image=self._frames[self._phase])
        self._update_animation()

    def set_targets(self, targets):
        completed, required = mission_totals(targets)
        if (completed, required) == (self.completed, self.required):
            return
        self.completed, self.required = completed, required
        if required:
            percent = 100 if completed == required else min(99.9, completed * 100 / required)
            percent_text = f'{percent:.1f}'.rstrip('0').rstrip('.').replace('.', ',')
            self.summary.set(f'{completed} / {required} cá • {percent_text}%')
        else:
            self.summary.set('—  Chưa đặt mục tiêu')
        self.draw()

    def draw(self, event=None):
        width = self.canvas.winfo_width()
        signature = (width, self.completed, self.required)
        if signature == self._draw_signature or width < 20:
            return
        self._draw_signature = signature
        self._stop_animation()
        self._frames = []
        canvas = self.canvas
        canvas.delete('all')
        colors = token('color.progress')
        import cv2
        import numpy as np
        # Cache an antialiased, opaque track by width. Native Canvas round
        # lines have visibly jagged end caps at the approved 1:1 viewport.
        if width != getattr(self,'_track_width',None):
            factor=4
            pixels=np.full((36*factor,width*factor,3),255,dtype=np.uint8)
            def pill(x,y,w,h,color):
                x,y,w,h=[round(n*factor) for n in (x,y,w,h)]
                radius=h//2
                cv2.rectangle(pixels,(x+radius,y),(x+w-radius-1,y+h-1),color,-1)
                cv2.circle(pixels,(x+radius,y+radius),radius,color,-1)
                cv2.circle(pixels,(x+w-radius-1,y+radius),radius,color,-1)
            border=tuple(int(colors['border'][i:i+2],16) for i in (5,3,1))
            track=np.array([int(colors['track'][i:i+2],16) for i in (5,3,1)])
            pill(0,1,width,34,border)
            pill(1,2,width-2,32,(255,255,255))
            mask_base=pixels.copy()
            pill(5,6,width-10,24,(0,0,0))
            mask=np.all(pixels==0,axis=2)
            blend=np.clip((np.arange(36*factor)/factor-6)/23,0,1)
            gradient=np.clip(track[None,:]+4-8*blend[:,None],0,255).astype('uint8')
            pixels=mask_base
            pixels[mask]=np.broadcast_to(gradient[:,None,:],pixels.shape)[mask]
            pixels=cv2.resize(pixels,(width,36),interpolation=cv2.INTER_AREA)
            self._track_image=tk.PhotoImage(master=canvas,data=cv2.imencode('.png',pixels)[1].tobytes())
            self._track_width=width
        canvas.create_image(0,0,anchor='nw',image=self._track_image)
        inner_left, inner_right, radius = 5, width - 5, 12
        length = max(0, inner_right - inner_left)
        ratio = min(1, max(0, self.completed / self.required)) if self.required else 0
        filled = length * ratio
        # Rasterize only this real progress widget: rounded gradient and clipped
        # diagonal highlights. Six cached phases bound memory and avoid image
        # allocations at each animation tick; totals never depend on the phase.
        if filled <= 0:
            return
        import cv2
        import numpy as np
        w, h = max(1, round(filled)), 24
        yy, xx = np.mgrid[0:h, 0:w]
        radius = min(12, w/2)
        cx = np.clip(xx+.5, radius, max(radius, w-radius))
        cy = np.clip(yy+.5, radius, h-radius)
        alpha = np.clip(radius + .5 - np.sqrt((xx+.5-cx)**2+(yy+.5-cy)**2), 0, 1)
        mix = (xx / max(1,w-1))[...,None]
        start = np.array([int(colors['start'][i:i+2],16) for i in (1,3,5)])
        end = np.array([int(colors['end'][i:i+2],16) for i in (1,3,5)])
        rgb = start*(1-mix)+end*mix
        for phase in range(6 if 0 < self.completed < self.required else 1):
            stripe = (((xx+yy-phase*3)//9)%2 == 0)[...,None]
            pixels = np.where(stripe, rgb*.70 + np.array([int(colors['stripe'][i:i+2],16) for i in (1,3,5)])*.30, rgb)
            rgba = np.dstack((pixels[...,::-1].astype('uint8'), (alpha*255).astype('uint8')))
            self._frames.append(tk.PhotoImage(master=canvas, data=cv2.imencode('.png',rgba)[1].tobytes()))
        self._phase = 0
        self._fill_image = self._frames[0]
        self._fill_item = canvas.create_image(inner_left, 6, anchor='nw', image=self._fill_image)
        self._update_animation()
