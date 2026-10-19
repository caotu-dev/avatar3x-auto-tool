import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

import numpy as np
from numpy.typing import NDArray

from adb.screenshot import save_event_screenshot
from config.settings import ROOT, TrialSettings
from .detector import Detection, FishingDetector
from .solver import DragMatch, FishingSolver, SolvePlan
from .states import FishingState
from .catch import CatchDetector


class Device(Protocol):
    def screenshot(self) -> NDArray[np.uint8]: ...
    def tap(self, x: int, y: int) -> None: ...
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 250) -> None: ...


class Detector(Protocol):
    def detect(self, screen: NDArray[np.uint8]) -> Detection: ...


class Solver(Protocol):
    def plan(self, screen: NDArray[np.uint8]) -> SolvePlan: ...
    def completed(self, screen: NDArray[np.uint8], target: tuple[int, int]) -> bool: ...


@dataclass(frozen=True)
class TrialResult:
    outcome: str
    reason: str
    casts: int
    drags: int
    confirmed: int
    fish_species: str | None = None
    fish_name: str | None = None
    fish_confidence: float | None = None
    area: str = "ca_ro"
    bite_observed: bool = False


class OneRoundBot:
    """Một lần Quăng câu, xác nhận từng kéo rồi dừng ở kết quả; không tự lặp lượt."""

    def __init__(self, device: Device, settings: TrialSettings = TrialSettings(),
                 detector: Detector | None = None, solver: Solver | None = None,
                 output: Path | None = None, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, area: str = "ca_ro",
                 recover_uncertain: bool = False):
        self.device = device
        self.settings = settings
        self.area = area
        self.recover_uncertain = recover_uncertain
        self.bite_observed = False
        self.detector = detector or FishingDetector(area=area)
        self.solver = solver or FishingSolver(FishingDetector(area=area))
        self.output = output or ROOT / "debug" / "trials" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        self.clock = clock
        self.sleep = sleep
        self.casts = self.drags = self.confirmed = 0
        self.event_index = 0
        self.last_screen: NDArray[np.uint8] | None = None
        self.started = 0.0

    def _event(self, name: str, **details: object) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        filename = f"{self.event_index:03d}_{name}.png"
        if self.last_screen is not None:
            captured=save_event_screenshot(self.last_screen, self.output / filename, name, details)
            filename=captured.name if captured is not None else None
        event = {"event": name, "elapsed": round(self.clock() - self.started, 3),
                 "image": filename, **details}
        with (self.output / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.event_index += 1

    @staticmethod
    def _log(message: str) -> None:
        try:
            print(message, flush=True)
        except UnicodeEncodeError:
            # Người dùng import bot trực tiếp có thể chưa đặt UTF-8 cho console.
            print(message.encode("ascii", errors="backslashreplace").decode(), flush=True)

    def _finish(self, outcome: str, reason: str, *, allow_recovery: bool = True) -> TrialResult:
        if allow_recovery and self.recover_uncertain and self.casts and outcome in ('STOPPED','TIMEOUT') and reason!='Đã dừng bằng Ctrl+C':
            return self.wait_for_result(reason)
        catch = CatchDetector(area=self.area).detect(self.last_screen) if outcome == "SUCCESS" and self.last_screen is not None else None
        result = TrialResult(outcome, reason, self.casts, self.drags, self.confirmed,
                             catch.species if catch else None, catch.name if catch else None,
                             catch.confidence if catch else None, self.area, self.bite_observed)
        if catch:
            self._log(f"[CÁ] {catch.name} ({catch.confidence:.2f})")
        self._event("STOP", **asdict(result))
        (self.output / "result.json").write_text(
            json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
        self._log(f"[BOT] {outcome}: {reason}\n[BOT] Báo cáo: {self.output}")
        return result

    def wait_for_result(self, reason):
        """Keep the auto session alive without using an uncertain drag plan."""
        self._event('RECOVER_RESULT',reason=reason)
        self._log('[BOT] Chưa đọc chắc lượt câu; ngừng kéo và chờ kết quả để câu tiếp.')
        previous=None;stable=0;exit_tapped=False;last_notice=self.clock()
        deadline=self.clock()+self.settings.recovery_timeout
        loading_since=None
        while True:
            self.last_screen=self.device.screenshot()
            detection=self.detector.detect(self.last_screen)
            state=detection.state
            stable=stable+1 if state is previous else 1
            previous=state
            if state is FishingState.LOADING:
                if loading_since is None:loading_since=self.clock()
                self.sleep(max(.1,self.settings.poll_interval))
                continue
            if loading_since is not None:
                deadline+=self.clock()-loading_since
                loading_since=None
            if state is FishingState.SUCCESS:
                return self._finish('SUCCESS','Đã nhận cá sau khi chờ khôi phục')
            if state is FishingState.OUT_OF_BAIT:
                return self._finish('OUT_OF_BAIT','Hết mồi sau khi chờ kết quả')
            if stable>=2 and detection.scene_confirmed:
                if state in (FishingState.RESULT,FishingState.FAILED):
                    return self._finish('FAILED' if state is FishingState.FAILED else 'RESULT','Đã thấy kết quả sau khi ngừng kéo')
                if state is FishingState.READY:
                    return self._finish('ABORTED','Lượt đã trở về Quăng câu; tiếp tục lượt sau')
            if state is FishingState.EXIT_CONFIRM and stable>=2 and not exit_tapped:
                button=detection.matches.get('exit_no')
                if button is not None:
                    self._event('CANCEL_EXIT_RECOVERY',point=button.center)
                    self.device.tap(*button.center);exit_tapped=True
            if state is not FishingState.EXIT_CONFIRM:
                exit_tapped=False
            if self.clock()>=deadline:
                return self._finish('TIMEOUT',
                    'Không có tiến triển sau khi chờ kết quả; chuyển về luồng khôi phục phiên.',
                    allow_recovery=False)
            if self.clock()-last_notice>=30:
                self._log('[BOT] Đang chờ màn hình kết quả hoặc Quăng câu; có thể bấm Dừng bất kỳ lúc nào.')
                last_notice=self.clock()
            self.sleep(max(.25,self.settings.poll_interval))

    def run(self) -> TrialResult:
        self.started = self.clock()
        try:
            return self._run()
        except KeyboardInterrupt:
            return self._finish("STOPPED", "Đã dừng bằng Ctrl+C")
        except (RuntimeError, OSError, ValueError) as exc:
            return self._finish("ERROR", str(exc))

    def _run(self) -> TrialResult:
        verified=getattr(self,'verified_ready',None)
        if (verified is not None and 0<=self.clock()-verified[2]<=.25
                and verified[1].state is FishingState.READY and verified[1].scene_confirmed):
            self.last_screen,initial,_=verified
        else:
            self.last_screen = self.device.screenshot()
            initial = self.detector.detect(self.last_screen)
        ready_deadline = self.clock() + self.settings.unknown_timeout
        while initial.state is FishingState.UNKNOWN and self.clock() < ready_deadline:
            # Session readiness and this fresh frame can differ during a
            # player animation. Observe again without sending any input.
            self.sleep(self.settings.poll_interval)
            self.last_screen = self.device.screenshot()
            initial = self.detector.detect(self.last_screen)
        if initial.state is FishingState.OUT_OF_BAIT:
            return self._finish("OUT_OF_BAIT", "Hết mồi câu; hãy mua thêm mồi")
        if initial.state is not FishingState.READY or not initial.scene_confirmed:
            return self._finish("STOPPED", "Hãy mở màn hình có Quăng câu trước khi chạy thử")
        self._event("CAST", state=initial.state.name)
        self._log("[ACTION] Quăng câu: quăng một lượt")
        self.device.tap(*initial.matches["toss"].center)
        self.casts = 1
        deadline = self.clock() + self.settings.round_timeout
        cast_time = self.clock()
        previous = None
        unknown_since = None
        unsafe_since = None
        pending: DragMatch | None = None
        pending_until = 0.0
        confirmations = 0
        board_signature = None
        observed_plan = None
        first_drag = True
        result_until = None
        recovery_until = None
        pending_before = None
        retried = False
        exit_observations = 0
        exit_tapped = False
        exit_since = None
        ready_after_exit = 0
        recast_after_exit = False
        loading_since = None

        while self.clock() < deadline or loading_since is not None:
            self.last_screen = self.device.screenshot()
            detection = self.detector.detect(self.last_screen)
            state = detection.state
            if state is FishingState.FISHING:
                self.bite_observed = True
            now = self.clock()
            if state is not previous:
                self._log(f"[FISHING] {state.name}")
                self._event(state.name)
                previous = state
            if state is FishingState.LOADING:
                loading_since = now if loading_since is None else loading_since
                unknown_since = None
                exit_observations = 0
                observed_plan = None
                self.sleep(self.settings.poll_interval)
                continue
            if loading_since is not None:
                paused=now-loading_since
                deadline+=paused
                if cast_time is not None:cast_time+=paused
                if result_until is not None:result_until+=paused
                if recovery_until is not None:recovery_until+=paused
                pending_until+=paused
                loading_since=None
            if state is FishingState.SUCCESS:
                return self._finish("SUCCESS", "Đã thấy popup nhận cá")
            if state is FishingState.OUT_OF_BAIT:
                return self._finish("OUT_OF_BAIT", "Hết mồi câu; hãy mua thêm mồi")
            if state is FishingState.FAILED:
                return self._finish("FAILED", "Đã thấy thông báo trật; không kéo thêm")
            if state is FishingState.RESULT:
                return self._finish("RESULT", "Đã thấy Xong, chưa đủ bằng chứng thành công hay trật")

            if state is FishingState.EXIT_CONFIRM:
                exit_since = now if exit_since is None else exit_since
                exit_observations += 1
                close = detection.matches.get("exit_no")
                if exit_observations >= 2 and not exit_tapped and close is not None:
                    self._event("CANCEL_EXIT", point=close.center)
                    self._log("[ACTION] Không: đóng xác nhận thoát trong lượt")
                    self.device.tap(*close.center)
                    exit_tapped = True
                    exit_since = self.clock()
                    pending_until = self.clock() + self.settings.confirmation_timeout
                elif now - exit_since >= max(12.0,self.settings.unknown_timeout):
                    return self._finish("STOPPED", "Popup xác nhận thoát chưa đóng; không bấm lặp")
                observed_plan = None
                self.sleep(self.settings.poll_interval)
                continue
            exit_observations = 0
            exit_since = None

            if exit_tapped and not recast_after_exit and state is FishingState.READY and detection.scene_confirmed and not self.drags:
                ready_after_exit += 1
                if ready_after_exit >= 2:
                    self._event('RECAST_AFTER_CANCEL_EXIT')
                    self._log('[ACTION] Quăng câu lại sau khi đóng popup thoát')
                    self.device.tap(*detection.matches['toss'].center)
                    self.casts += 1
                    recast_after_exit = True
                    self.bite_observed = False
                    cast_time = self.clock()
                    unknown_since = None
                    ready_after_exit = 0
                    # Keep exit_tapped: a second popup in this round is bounded
                    # by the existing timeout, rather than an endless retry.
                self.sleep(self.settings.poll_interval)
                continue
            ready_after_exit = 0

            if recovery_until is not None:
                # Không kéo hoặc quăng lại; chỉ chờ kết quả để session xử lý Xong.
                if now >= recovery_until:
                    return self._finish("STOPPED", "Chờ kết quả sau khi ngừng kéo đã hết hạn")
                self.sleep(self.settings.poll_interval)
                continue

            if state in (FishingState.UNKNOWN, FishingState.READY) or not detection.scene_confirmed:
                observed_plan = None
                unknown_since = now if unknown_since is None else unknown_since
                # The server can show Xin chờ before the exit prompt. Wait
                # without input before a bite; the round deadline still bounds it.
                unknown_limit = (max(self.settings.unknown_timeout, min(30.0, self.settings.bite_timeout))
                                 if state is FishingState.UNKNOWN and not self.bite_observed and not self.drags
                                 else self.settings.unknown_timeout)
                if now - unknown_since >= unknown_limit:
                    return self._finish("STOPPED", "Màn hình chưa xác định; đã ngừng thao tác")
            else:
                unknown_since = None
                if state is FishingState.WAITING:
                    if self.drags or board_signature is not None:
                        return self._finish("STOPPED", "Màn hình kéo hình biến mất nhưng chưa thấy kết quả")
                    if now - cast_time >= self.settings.bite_timeout:
                        return self._finish("TIMEOUT", "Hết thời gian chờ cá; không quăng lại tự động")
                elif state is FishingState.FISHING:
                    if pending is not None:
                        # Không gửi lại swipe trong thời gian chờ xác nhận.
                        if self.solver.completed(self.last_screen, pending.target):
                            confirmations += 1
                        else:
                            confirmations = 0
                        if confirmations >= 2:
                            self.confirmed += 1
                            self._event("CONFIRMED", target=pending.target_index + 1)
                            pending = None
                            unsafe_since = None
                        elif now >= pending_until:
                            retry_check = getattr(self.solver, "retry_match", None)
                            if (not retried and pending_before is not None and retry_check
                                    and retry_check(pending_before, self.last_screen, pending)):
                                self.last_screen = self.device.screenshot()
                                guard = self.detector.detect(self.last_screen)
                                if (guard.state is FishingState.FISHING and guard.scene_confirmed
                                        and self.clock() < deadline
                                        and retry_check(pending_before, self.last_screen, pending)):
                                    self._event("RETRY_DRAG", target=pending.target_index + 1)
                                    self._log(f"[ACTION] Thử kéo lại T{pending.target_index + 1}: ô chưa đổi")
                                    self.device.swipe(*pending.source, *pending.target,
                                                      duration_ms=max(900, self.settings.swipe_duration_ms))
                                    self.drags += 1
                                    retried = True
                                    confirmations = 0
                                    pending_until = self.clock() + self.settings.confirmation_timeout
                                    continue
                                # Kết quả/chuyển cảnh mới được xử lý ở vòng kế, không kéo.
                                if guard.state is not FishingState.FISHING:
                                    continue
                            recovery_until = min(deadline, now + self.settings.recovery_timeout)
                            self._event("WAIT_RESULT", reason="Chưa xác nhận được ô đã điền")
                            self._log("[BOT] Chưa xác nhận ô; ngừng kéo và chờ kết quả lượt")
                    if pending is None:
                        plan_started = self.clock()
                        plan_from_frame = getattr(self.solver, 'plan_after_detection', None)
                        plan = (plan_from_frame(self.last_screen, detection) if plan_from_frame
                                else self.solver.plan(self.last_screen))
                        plan_elapsed = self.clock() - plan_started
                        signature = tuple((m.target_index, m.source_index) for m in plan.matches)
                        if board_signature is not None and signature != board_signature and plan.safe:
                            return self._finish("STOPPED", "Bảng hình thay đổi trong lượt; không dùng kế hoạch cũ")
                        if not plan.safe:
                            observed_plan = None
                            unsafe_since = now if unsafe_since is None else unsafe_since
                            if self.clock() - unsafe_since >= self.settings.plan_timeout:
                                recovery_until = min(deadline, self.clock() + self.settings.recovery_timeout)
                                self._event("WAIT_RESULT", reason=plan.reason)
                                self._log(f"[BOT] {plan.reason}; ngừng kéo và chờ kết quả lượt")
                        elif first_drag and observed_plan != signature:
                            # Bảng chớp một frame rồi Miss sẽ không nhận thao tác kéo.
                            observed_plan = signature
                        else:
                            unsafe_since = None
                            todo = [m for m in plan.matches if not m.completed]
                            if todo:
                                chosen = todo[0]
                                # Sau xác nhận, dùng ngay ảnh hiện tại nếu ghép đủ nhanh.
                                if first_drag or plan_elapsed > .12:
                                    self.last_screen = self.device.screenshot()
                                    guard = self.detector.detect(self.last_screen)
                                    if guard.state is FishingState.SUCCESS:
                                        return self._finish("SUCCESS", "Đã thấy popup nhận cá")
                                    if guard.state is FishingState.FAILED:
                                        return self._finish("FAILED", "Đã thấy thông báo trật trước thao tác; không kéo")
                                    if guard.state is FishingState.RESULT:
                                        return self._finish("RESULT", "Đã thấy Xong trước thao tác; không kéo")
                                    if guard.state is not FishingState.FISHING or not guard.scene_confirmed:
                                        observed_plan = None
                                        continue
                                    validate = getattr(self.solver, 'validate_match', None)
                                    if validate is not None and not validate(self.last_screen, guard, chosen):
                                        observed_plan = None
                                        continue
                                if self.solver.completed(self.last_screen, chosen.target):
                                    continue
                                if self.clock() >= deadline:
                                    break
                                self._event("DRAG", source=chosen.source_index + 1,
                                            target=chosen.target_index + 1,
                                            confidence=round(chosen.confidence, 3))
                                self._log(f"[ACTION] Kéo S{chosen.source_index + 1} → "
                                          f"T{chosen.target_index + 1} ({chosen.confidence:.2f})")
                                self.device.swipe(*chosen.source, *chosen.target,
                                                  duration_ms=self.settings.swipe_duration_ms)
                                self.drags += 1
                                board_signature = signature
                                first_drag = False
                                pending = chosen
                                pending_before = self.last_screen.copy()
                                retried = False
                                confirmations = 0
                                pending_until = self.clock() + self.settings.confirmation_timeout
                            else:
                                result_until = (self.clock() + self.settings.unknown_timeout
                                                if result_until is None else result_until)
                                if self.clock() >= result_until:
                                    return self._finish("STOPPED", "Các ô có vẻ đã điền nhưng chưa thấy kết quả")
            self.sleep(self.settings.poll_interval)
        if previous is FishingState.EXIT_CONFIRM:
            return self._finish('STOPPED','Popup xác nhận thoát chưa đóng; không bấm lặp')
        return self._finish("TIMEOUT", "Hết thời hạn lượt thử")
