"""Recognize the saved-account continue screen; never enter credentials."""
import cv2
from .travel import TravelController

from config.settings import ROOT
from vision.matcher import ROI, find_template


class SessionLost(Exception):
    pass


class ContinueScreen:
    # Both supported login layouts use these same positions after viewport
    # normalization. The guard runs on every game frame, so avoid scanning
    # map scenery for login-only labels and buttons.
    LOGO_REGION = ROI(.2, .15, .6, .45)
    BUTTON_REGION = ROI(.3, .55, .25, .18)
    COOLDOWN_REGION = ROI(.25, .35, .5, .25)

    def __init__(self):
        folder = ROOT / 'vision/templates/reconnect'
        self.logo = cv2.imread(str(folder / 'logo.png'))
        self.button = cv2.imread(str(folder / 'continue.png'))
        self.cooldown = cv2.imread(str(folder / 'cooldown.png'))
        self.dark_logo = cv2.imread(str(folder / 'logo_hearts.png'))
        self.dark_button = cv2.imread(str(folder / 'continue_dark.png'))

    def blocked(self, image):
        """The static cooldown label excludes its changing seconds counter."""
        return self._blocked(cv2.resize(image, (825, 466)))

    def _blocked(self, normalized):
        return self.cooldown is not None and find_template(
            normalized, self.cooldown, threshold=.94,
            roi=self.COOLDOWN_REGION) is not None

    def detect(self, image):
        normalized = cv2.resize(image, (825, 466))
        if self._blocked(normalized):
            # Keep the session-loss guard active while the modal obscures login.
            # Recovery checks blocked() before considering this login position.
            return round(340 * image.shape[1] / 825), round(291 * image.shape[0] / 466)
        if self.logo is None or self.button is None:
            return None
        # The reference is 825×466; normalize the complete viewport, not click
        # coordinates. Both logo and labelled button must match.
        if self.dark_logo is not None and self.dark_button is not None:
            logo=find_template(normalized,self.dark_logo,threshold=.94,roi=self.LOGO_REGION)
            button=find_template(normalized,self.dark_button,threshold=.94,roi=self.BUTTON_REGION) if logo is not None else None
            if logo is not None and button is not None and 250 < button.x < 400 and 250 < button.y < 340:
                x,y=button.center
                return round(x*image.shape[1]/825),round(y*image.shape[0]/466)
        if not find_template(normalized, self.logo, threshold=.94,roi=self.LOGO_REGION):
            return None
        button = find_template(normalized, self.button, threshold=.94,roi=self.BUTTON_REGION)
        if button is None:
            return None
        x, y = button.center
        return round(x * image.shape[1] / 825), round(y * image.shape[0] / 466)


class ReconnectController(TravelController):
    def recover(self, screen_detector, ready, checkpoint=lambda: None,
                timeout=45, max_attempts=3, retry_delay=3):
        """Retry only on a fresh, stable Continue screen; never click loading frames."""
        deadline=self.clock()+timeout
        attempts=0;last_tap=None;previous=None;stable=0;ready_frames=0;waiting=False
        cooldown_started=None
        while self.clock()<deadline or cooldown_started is not None:
            checkpoint()
            self.screen=self.device.screenshot()
            if screen_detector.blocked(self.screen):
                previous=None;stable=0;ready_frames=0
                if not waiting:
                    self.event('RECONNECT_COOLDOWN', attempts=attempts)
                    cooldown_started=self.clock()
                waiting=True
                self.sleep(.2)
                continue
            if cooldown_started is not None:
                # The server controls this countdown; waiting on its verified
                # label must not exhaust the budget for actually logging in.
                deadline+=self.clock()-cooldown_started
                cooldown_started=None
            waiting=False
            point=screen_detector.detect(self.screen)
            if point:
                ready_frames=0
                stable=stable+1 if point==previous else 1
                previous=point
                if stable>=2 and attempts<max_attempts and (last_tap is None or self.clock()-last_tap>=retry_delay):
                    self.tap(point,'Chơi tiếp sau mất phiên')
                    attempts+=1;last_tap=self.clock();stable=0
            else:
                previous=None;stable=0
                ready_frames=ready_frames+1 if ready(self.screen) else 0
                if ready_frames>=2:
                    self.event('RECONNECTED',attempts=attempts)
                    return {'status':'READY','attempts':attempts}
            self.sleep(.2)
        self.event('RECONNECT_TIMEOUT',attempts=attempts)
        raise RuntimeError(f'Không khôi phục được phiên sau {attempts} lần Chơi tiếp; đã dừng.')
