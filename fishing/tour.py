"""Tuyến hữu hạn: shop → cá nóc → shop → cá mập, bổ sung mồi khi hết."""
import json
from datetime import datetime
from pathlib import Path

from config.settings import ROOT, SessionSettings
from .bot import OneRoundBot
from .catch import AREA_SPECIES
from .session import FishingSession
from .statistics import fishing_statistics
from .travel import TravelController


class FishingTour:
    def __init__(self, device, rounds_per_area: int = 20, max_refills: int = 2,
                 output: Path | None = None):
        if type(rounds_per_area) is not int or rounds_per_area <= 0:
            raise ValueError("Số lượt mỗi khu phải là số nguyên dương")
        if type(max_refills) is not int or max_refills < 0:
            raise ValueError("Số lần bổ sung mồi phải là số nguyên không âm")
        self.device = device
        self.rounds_per_area, self.max_refills = rounds_per_area, max_refills
        self.output = output or ROOT / "debug/tours" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        self.travel = TravelController(device, self.output / "travel")
        self.rounds = []

    def summary(self, status: str, reason: str):
        payload = fishing_statistics(self.rounds)
        payload.update(status=status, reason=reason, bait_purchased=self.travel.bait_purchased,
                       bait_coins=self.travel.bait_purchased * 20)
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if status != "RUNNING":
            OneRoundBot._log(f"[TUYẾN] {status}: {reason}\n[TUYẾN] Cá: {payload['caught']}, "
                             f"cắn câu: {payload['bites']}, lượt không nhận cá: {payload['misses']}, "
                             f"mồi đã mua: {payload['bait_purchased']}\n[TUYẾN] Báo cáo: {self.output}")
        return payload

    def run(self):
        try:
            self.travel.center()
            for area in ("ca_noc", "ca_map"):
                bought = self.travel.sell_and_buy()
                self.summary("RUNNING", f"Mua thêm {bought} mồi trước khu {area}" if bought
                             else f"Dùng mồi đang có trước khu {area}")
                self.travel.enter(area)
                completed = refills = 0
                found = set()
                # Khu cá mập còn đang thu mẫu, không coi danh mục đã gặp là đầy đủ.
                expected = AREA_SPECIES.get(area, set()) if area == "ca_noc" else set()
                while completed < self.rounds_per_area:
                    session = FishingSession(self.device, SessionSettings(rounds=1), area=area,
                                             output=self.output / area / f"attempt_{completed + 1:03d}_refill_{refills}")
                    result = session.run()
                    self.rounds.extend(result.rounds)
                    self.summary("RUNNING", f"Đã lưu lượt ở {area}")
                    if result.status == "OUT_OF_BAIT":
                        if refills >= self.max_refills:
                            return self.summary("STOPPED", f"Đã hết giới hạn bổ sung mồi ở {area}")
                        self.travel.center(area)
                        bought = self.travel.sell_and_buy()
                        if not bought:
                            return self.summary("STOPPED", "Hết mồi nhưng shop từ chối bổ sung do giới hạn rương")
                        self.summary("RUNNING", "Đã bổ sung 20 mồi")
                        self.travel.enter(area)
                        refills += 1
                        continue
                    if result.status != "COMPLETE":
                        return self.summary("STOPPED", result.reason)
                    completed += 1
                    found.update(round_.fish_species for round_ in result.rounds if round_.fish_species)
                    if expected and expected <= found:
                        OneRoundBot._log(f"[TUYẾN] Đã gặp đủ các loại cá của {area}")
                        break
                self.travel.center(area)
            # Về trung tâm; không mua thêm một lô chưa dùng sau khu cuối.
            return self.summary("COMPLETE", "Đã kết thúc hai khu và về trung tâm")
        except KeyboardInterrupt:
            return self.summary("STOPPED", "Đã dừng bằng Ctrl+C")
        except (RuntimeError, OSError, ValueError) as exc:
            return self.summary("STOPPED", str(exc))
