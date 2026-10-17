import json
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from adb.screenshot import save_debug_screenshot
from debug.notifications import notify_out_of_bait
from config.settings import ROOT, SessionSettings, TrialSettings
from .bot import Detector, Device, OneRoundBot, Solver, TrialResult
from .detector import FishingDetector
from .solver import FishingSolver
from .states import FishingState
from .catch import SPECIES


def popup_outside_point(screen: np.ndarray) -> tuple[int, int] | None:
    """Điểm trên nước bên trái popup đã quan sát, kiểm tra lại màu trước khi bấm."""
    if screen.shape != (900, 1600, 3):
        return None
    for x,y in [(x,y) for y in (650,180) for x in (160,350,1250,1350)]:
        patch = cv2.cvtColor(screen[y-20:y+20, x - 20:x + 20], cv2.COLOR_BGR2HSV)
        water = cv2.inRange(patch, (80, 60, 35), (115, 255, 255))
        if np.count_nonzero(water) / water.size > .80:
            return x, y
    return None


@dataclass(frozen=True)
class SessionResult:
    status: str
    reason: str
    rounds: tuple[TrialResult, ...]


class FishingSession:
    """Ghép các lượt đã kiểm tra với bước đóng popup và Xong có xác nhận."""

    def __init__(self, device: Device, settings: SessionSettings = SessionSettings(),
                 trial_settings: TrialSettings = TrialSettings(),
                 detector: Detector | None = None, solver: Solver | None = None,
                 output: Path | None = None, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, area: str = "ca_ro",
                 recover_uncertain: bool = False, reuse_ready: bool = False,
                 ready_handoff=None):
        if type(settings.rounds) is not int or settings.rounds <= 0:
            raise ValueError("Số lượt phải là số nguyên dương")
        self.device = device
        self.settings = settings
        self.trial_settings = trial_settings
        self.area = area
        self.recover_uncertain = recover_uncertain
        self.reuse_ready=reuse_ready
        self.verified_ready=None
        self.ready_handoff=ready_handoff
        self.detector = detector or FishingDetector(area=area)
        self.solver = solver or FishingSolver(self.detector)
        self.output = output or ROOT / "debug" / "runs" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        self.clock, self.sleep = clock, sleep
        self.results: list[TrialResult] = []
        self.event_index = 0
        self.started = 0.0
        self.last_screen = None
        self.prepare_status = "STOPPED"

    def _event(self, name: str, **details: object) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        filename = f"{self.event_index:03d}_{name}.png"
        if self.last_screen is not None:
            filename=save_debug_screenshot(self.last_screen, self.output / filename).name
        with (self.output / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps({"event": name, "elapsed": round(self.clock() - self.started, 3),
                                   "after_round": len(self.results), "image": filename,
                                   **details}, ensure_ascii=False) + "\n")
        self.event_index += 1

    def _summary(self, status: str, reason: str) -> SessionResult:
        result = SessionResult(status, reason, tuple(self.results))
        payload = asdict(result)
        payload["counts"] = dict(Counter(round_.outcome for round_ in self.results))
        payload["casts"] = sum(round_.casts for round_ in self.results)
        payload["area"] = self.area
        payload["bites"] = sum(round_.bite_observed for round_ in self.results)
        payload["misses"] = max(0,payload["casts"]-payload["bites"])
        payload["misses_confirmed"] = sum(round_.outcome == "FAILED" for round_ in self.results)
        payload["fish_counts"] = dict(Counter(round_.fish_species or "unknown"
                                              for round_ in self.results if round_.outcome == "SUCCESS"))
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if status != "RUNNING":
            self._event("STOP", status=status, reason=reason)
            OneRoundBot._log(f"[SESSION] {status}: {reason}\n[SESSION] Báo cáo: {self.output}")
            OneRoundBot._log(f"[SESSION] Kết quả: {payload['counts']}")
            names = {SPECIES.get(species, "Chưa xác định"): count
                     for species, count in payload["fish_counts"].items()}
            OneRoundBot._log(f"[SESSION] Cá đã nhận: {names}")
            if status == "OUT_OF_BAIT":
                notify_out_of_bait(self.output)
        return result

    def _prepare_ready(self, after_round: bool = False) -> tuple[bool, str]:
        # A completed GUI round has already observed two READY frames. Reuse
        # that proof only immediately, once, before any intervening navigation.
        handoff, self.ready_handoff = self.ready_handoff, None
        if (not after_round and self.reuse_ready and handoff is not None
                and 0 <= self.clock()-handoff[2] <= .25
                and handoff[1].state is FishingState.READY and handoff[1].scene_confirmed):
            self.verified_ready=handoff
            self.last_screen=handoff[0]
            return True, 'Đã xác nhận Quăng câu từ lượt trước'
        # ADB capture + recognition can take several seconds per observation.
        # Post-catch animation still needs two verified frames before each tap.
        transition_timeout = max(self.settings.transition_timeout,12.0) if after_round else self.settings.transition_timeout
        deadline = self.clock() + transition_timeout
        total_deadline = self.clock() + 4 * transition_timeout
        popup_tapped = finish_tapped = False
        finish_attempts = 0
        finish_sent_at = None
        finish_point = None
        exit_tapped = False
        chair_tapped = False
        previous_chair = None
        self.prepare_status = "STOPPED"
        previous = None
        waiting_for_chair = False
        stable = 0
        loading_since = None
        while self.clock() < deadline or loading_since is not None:
            self.last_screen = self.device.screenshot()
            detection = self.detector.detect(self.last_screen)
            state = detection.state
            if state is FishingState.LOADING:
                if loading_since is None:
                    exit_tapped=False
                    self._event('WAIT_LOADING')
                    OneRoundBot._log('[SESSION] Game đang Xin chờ; đợi popup kết thúc, có thể bấm Dừng.')
                loading_since = self.clock()
                previous=None;stable=0
                self.sleep(self.settings.poll_interval)
                continue
            if loading_since is not None:
                total_deadline=self.clock()+4*transition_timeout
                deadline=self.clock()+max(transition_timeout,self.settings.chair_entry_timeout)
                loading_since=None
            if self.clock() >= deadline:
                break
            if state is not FishingState.EXIT_CONFIRM:
                exit_tapped=False
            if (not after_round and state is FishingState.UNKNOWN
                    and 'idle_menu' in detection.matches and not waiting_for_chair):
                waiting_for_chair = True
                deadline = min(total_deadline, self.clock() + self.settings.chair_entry_timeout)
            # Miss có thể biến mất thành RESULT, nhưng nút Xong vẫn là cùng một bước.
            phase = "FINISH" if state in (FishingState.FAILED, FishingState.RESULT) else state.name
            stable = stable + 1 if phase == previous else 1
            if phase != previous:
                self._event(f"PREPARE_{phase}")
            previous = phase
            if state is FishingState.OUT_OF_BAIT:
                self.prepare_status = "OUT_OF_BAIT"
                return False, "Hết mồi câu; đã dừng, không bấm OK hoặc vào ghế lại"
            if state is FishingState.READY and detection.scene_confirmed and stable >= 2:
                self.verified_ready=(self.last_screen,detection,self.clock())
                return True, "Đã thấy Quăng câu"
            if state is FishingState.IDLE and detection.scene_confirmed:
                chairs = sorted((name, match) for name, match in detection.matches.items()
                                if name.startswith("chair_"))
                if chairs:
                    # Chọn ghế nhìn thấy ở dưới, lấy vị trí từ mặt ghế đã nhận diện.
                    chair = chairs[-1][1]
                    point = (chair.center[0], chair.center[1] + 15)
                    if (stable >= 2 and point == previous_chair and not chair_tapped):
                        self._event("ENTER_CHAIR", point=point)
                        OneRoundBot._log(f"[ACTION] Vào ghế: {point[0]}, {point[1]}")
                        self.device.tap(*point)
                        chair_tapped = True
                        deadline = min(total_deadline, self.clock() + self.settings.chair_entry_timeout)
                    previous_chair = point
                self.sleep(self.settings.poll_interval)
                continue
            previous_chair = None
            if state is FishingState.EXIT_CONFIRM and stable >= 2:
                if not exit_tapped:
                    close = detection.matches.get("exit_no")
                    if close is None:
                        return False, "Chưa xác nhận được nút Không của popup thoát"
                    self._event("CANCEL_EXIT", point=close.center)
                    OneRoundBot._log("[ACTION] Không: đóng xác nhận thoát")
                    self.device.tap(*close.center)
                    exit_tapped = True
                    chair_tapped=False
                    previous_chair=None
                    deadline = min(total_deadline, self.clock() + max(transition_timeout,self.settings.chair_entry_timeout))
            if state in (FishingState.WAITING, FishingState.FISHING):
                if not after_round:
                    return False, "Game đang ở giữa lượt; không tự kết thúc hay quăng thêm"
                # Kết quả có thể xen với frame cuối của bảng; chỉ chờ, không gửi input.
                self.sleep(self.settings.poll_interval)
                continue
            if state is FishingState.SUCCESS and stable >= 2:
                if finish_tapped:
                    return False, "Popup xuất hiện lại sau Xong; đã dừng"
                if not popup_tapped:
                    point = popup_outside_point(self.last_screen)
                    if point is None:
                        return False, "Không xác nhận được điểm ngoài popup trên vùng nước"
                    self._event("DISMISS_POPUP", point=point)
                    OneRoundBot._log("[ACTION] Đóng popup nhận cá")
                    self.device.tap(*point)
                    popup_tapped = True
                    deadline = min(total_deadline, self.clock() + transition_timeout)
            elif phase == "FINISH" and stable >= 2 and detection.scene_confirmed:
                retry_finish = (after_round and self.recover_uncertain and finish_tapped
                                and finish_attempts < 3
                                and self.clock() - finish_sent_at >= 3)
                if not finish_tapped or retry_finish:
                    finish = detection.matches.get("finish")
                    if finish is None:
                        return False, "Chưa tìm được nút Xong; không bấm theo tọa độ đoán"
                    if retry_finish and finish.center != finish_point:
                        self.sleep(self.settings.poll_interval)
                        continue
                    self._event("FINISH_RETRY" if retry_finish else "FINISH",
                                point=finish.center, attempt=finish_attempts+1)
                    OneRoundBot._log("[ACTION] Xong")
                    self.device.tap(*finish.center)
                    finish_tapped = True
                    finish_attempts += 1
                    finish_sent_at = self.clock()
                    finish_point = finish.center
                    # Each retry needs two fresh confirmed result observations.
                    previous = None
                    stable = 0
                    deadline = min(total_deadline, self.clock() + transition_timeout)
            self.sleep(self.settings.poll_interval)
        if waiting_for_chair and not chair_tapped:
            return False, "Chưa thấy ghế trống đủ tin cậy (có thể bị người chơi che); không bấm ghế mù"
        return False, "Hết thời gian xác nhận đóng popup / Xong / Quăng câu; không bấm lại"

    def run(self) -> SessionResult:
        self.started = self.clock()
        try:
            ready, reason = self._prepare_ready()
            if not ready:
                return self._summary(self.prepare_status, reason)
            for index in range(self.settings.rounds):
                OneRoundBot._log(f"[SESSION] Lượt {index + 1}/{self.settings.rounds}")
                bot = OneRoundBot(self.device, self.trial_settings, self.detector, self.solver,
                                  self.output / f"round_{index + 1:03d}", self.clock, self.sleep, area=self.area,
                                  recover_uncertain=self.recover_uncertain)
                if self.reuse_ready:bot.verified_ready=self.verified_ready
                result = bot.run()
                self.results.append(result)
                self._summary("RUNNING", "Đã lưu kết quả lượt")
                if result.outcome == "OUT_OF_BAIT":
                    return self._summary("OUT_OF_BAIT", result.reason)
                if result.outcome not in ("SUCCESS", "FAILED", "RESULT", "ABORTED"):
                    return self._summary("STOPPED", result.reason)
                ready, reason = self._prepare_ready(after_round=True)
                if not ready:
                    return self._summary(self.prepare_status, reason)
            return self._summary("COMPLETE", f"Đã kết thúc {self.settings.rounds} lượt; màn hình sẵn sàng Quăng câu")
        except KeyboardInterrupt:
            return self._summary("STOPPED", "Đã dừng bằng Ctrl+C")
        except (RuntimeError, OSError, ValueError) as exc:
            return self._summary("ERROR", str(exc))
