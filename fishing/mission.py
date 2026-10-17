"""Điều phối theo mục tiêu, lưu tiến độ và tồn kho sau mỗi bằng chứng."""
import json
import time
from datetime import datetime
from pathlib import Path

from config.settings import ROOT, SessionSettings
from .bot import OneRoundBot, TrialResult
from .catch import CatchDetector, SPECIES
from .detector import FishingDetector
from .session import FishingSession
from .states import FishingState
from .travel import TravelController

SPECIES_AREA = {"ca_chep_vang": "ca_ro", "cua": "ca_noc", "ca_chim": "ca_map"}


class MissionLedger:
    def __init__(self, path: Path, task: dict):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
            if self.data["task"] != task:
                raise ValueError("State thuộc nhiệm vụ khác; cần đường dẫn state riêng")
        else:
            self.data = {"task": task, "status": "NEW", "counts": {}, "unsold": {},
                         "bait_remaining": None, "bait_purchased": 0, "area": None,
                         "rounds": {}, "pending_round": None, "purchase_pending": False}
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def complete(self):
        return all(self.data["counts"].get(species, 0) >= count
                   for species, count in self.data["task"]["targets"].items())

    def needed_area(self):
        for species, count in self.data["task"]["targets"].items():
            if self.data["counts"].get(species, 0) < count:
                return SPECIES_AREA[species]
        return None

    def record(self, key: str, result: TrialResult):
        if key in self.data["rounds"]:
            return False
        from dataclasses import asdict
        self.data["rounds"][key] = asdict(result)
        if result.casts and self.data["bait_remaining"] is not None:
            self.data["bait_remaining"] = max(0, self.data["bait_remaining"] - result.casts)
        if result.outcome == "SUCCESS":
            species = result.fish_species or "unknown"
            for field in ("counts", "unsold"):
                self.data[field][species] = self.data[field].get(species, 0) + 1
        if result.outcome == "OUT_OF_BAIT":
            self.data["bait_remaining"] = 0
        self.data["pending_round"] = None
        self.save()
        return True

    def event(self, name, details):
        if name == "PURCHASE_PENDING":
            self.data["purchase_pending"] = True
        elif name == "PURCHASE_CONFIRMED":
            quantity = details["quantity"]
            self.data["bait_purchased"] += quantity
            if self.data["bait_remaining"] is not None:
                self.data["bait_remaining"] += quantity
            self.data["purchase_pending"] = False
        elif name == "PURCHASE_REJECTED_CAPACITY":
            self.data["purchase_pending"] = False
        elif name == "SALE_CONFIRMED":
            self.data["unsold"] = {}
        self.save()


class FishingMission:
    def __init__(self, device, task_path: Path = ROOT / "config/mission.json",
                 state_path: Path = ROOT / "runtime/mission.json"):
        task = json.loads(task_path.read_text(encoding="utf-8"))
        if not task.get("targets") or any(species not in SPECIES_AREA or type(count) is not int or count <= 0
                                          for species, count in task["targets"].items()):
            raise ValueError("Mục tiêu nhiệm vụ không hợp lệ")
        self.device = device
        self.ledger = MissionLedger(state_path, task)
        self.output = ROOT / "debug/missions" / task["id"]
        run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        self.travel = TravelController(device, self.output / run_id / "travel", on_event=self.ledger.event)

    def finish(self, status, reason):
        self.ledger.data.update(status=status, reason=reason)
        self.ledger.save()
        progress = {SPECIES[key]: f"{self.ledger.data['counts'].get(key, 0)}/{count}"
                    for key, count in self.ledger.data["task"]["targets"].items()}
        OneRoundBot._log(f"[NHIỆM VỤ] {status}: {reason}\n[NHIỆM VỤ] {progress}")
        if status == "COMPLETE":
            self.output.mkdir(parents=True, exist_ok=True)
            (self.output / "notification.json").write_text(json.dumps(
                {"message": "Đã hoàn thành nhiệm vụ câu cá", "progress": progress},
                ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK)
            except (ImportError, RuntimeError):
                pass
        return self.ledger.data

    def recover_pending(self):
        pending = self.ledger.data["pending_round"]
        if not pending:
            return
        path = Path(pending["path"]) / "round_001/result.json"
        if path.exists():
            self.ledger.record(pending["path"], TrialResult(**json.loads(path.read_text(encoding="utf-8"))))
        else:
            # Không tự quăng lại nếu lần trước bị ngắt trước khi ghi kết quả.
            detector = FishingDetector(area=pending["area"])
            image = self.device.screenshot()
            if detector.detect(image).state is FishingState.SUCCESS:
                catch = CatchDetector(area=pending["area"]).detect(image)
                self.ledger.record(pending["path"], TrialResult("SUCCESS", "Popup từ lượt bị ngắt",
                    1, 0, 0, catch.species, catch.name, catch.confidence, pending["area"], True))
            else:
                raise RuntimeError("Lượt trước bị ngắt chưa có kết quả; giữ state để đối chiếu")

    def refill(self, area):
        self.ledger.data["bait_remaining"] = 0
        self.ledger.save()
        self.travel.center(area)
        self.ledger.data["area"] = "center"
        self.ledger.save()
        bought = self.travel.sell_and_buy(sell=bool(self.ledger.data["unsold"]), buy=True)
        if not bought:
            raise RuntimeError("Đã hết mồi nhưng shop chưa xác nhận mua được mồi")
        self.travel.enter(area)
        self.ledger.data["area"] = area
        self.ledger.save()

    def run(self):
        try:
            if self.ledger.complete():
                return self.finish("COMPLETE", "Mục tiêu đã đủ; không quăng thêm")
            if self.ledger.data["purchase_pending"]:
                raise RuntimeError("Giao dịch lần trước chưa xác nhận; không mua lặp")
            self.recover_pending()
            self.ledger.data["status"] = "RUNNING"
            self.ledger.save()
            while not self.ledger.complete():
                area = self.ledger.needed_area()
                image = self.device.screenshot()
                observed = self.travel.world.map_name(image, require_menu=False)
                current = observed or self.ledger.data["area"]
                if current != area:
                    self.travel.center(current if current in SPECIES_AREA.values() else None)
                    if self.ledger.data["unsold"]:
                        self.travel.sell_and_buy(sell=True, buy=False)
                    self.travel.enter(area)
                self.ledger.data["area"] = area
                self.ledger.save()
                path = self.output / "rounds" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
                self.ledger.data["pending_round"] = {"path": str(path), "area": area}
                self.ledger.save()
                session = FishingSession(self.device, SessionSettings(rounds=1), area=area, output=path)
                result = session.run()
                if not result.rounds:
                    self.ledger.data["pending_round"] = None
                    self.ledger.save()
                for round_ in result.rounds:
                    self.ledger.record(str(path), round_)
                if self.ledger.complete():
                    return self.finish("COMPLETE", "Đã câu đủ 2 cá chép vàng, 3 cua, 2 cá chim")
                if result.status == "OUT_OF_BAIT":
                    self.refill(area)
                    continue
                if result.status != "COMPLETE":
                    # Chờ bằng chứng kết quả muộn, không gửi input ở màn hình lạ.
                    deadline = time.monotonic() + 30
                    detector = FishingDetector(area=area)
                    recovered = False
                    while time.monotonic() < deadline:
                        image = self.device.screenshot()
                        detection = detector.detect(image)
                        if detection.state in (FishingState.SUCCESS, FishingState.RESULT, FishingState.FAILED,
                                                FishingState.READY):
                            if detection.state is FishingState.SUCCESS and result.rounds:
                                from dataclasses import replace
                                old = result.rounds[-1]
                                if old.outcome != "SUCCESS":
                                    catch = CatchDetector(area=area).detect(image)
                                    # Thay kết quả cùng lượt; không trừ mồi lần hai.
                                    self.ledger.data["rounds"].pop(str(path))
                                    updated = replace(old, outcome="SUCCESS", fish_species=catch.species,
                                                      fish_name=catch.name, fish_confidence=catch.confidence, casts=0)
                                    self.ledger.record(str(path), updated)
                                    self.ledger.data["rounds"][str(path)]["casts"] = old.casts
                                    self.ledger.save()
                            recovered = True
                            break
                        time.sleep(.2)
                    if not recovered:
                        return self.finish("STOPPED", result.reason)
            return self.finish("COMPLETE", "Đã đủ toàn bộ mục tiêu")
        except KeyboardInterrupt:
            return self.finish("PAUSED", "Đã dừng theo yêu cầu; tiến độ được giữ")
        except (RuntimeError, OSError, ValueError) as exc:
            return self.finish("STOPPED", str(exc))
