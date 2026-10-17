import tempfile
import unittest
import json
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
from pathlib import Path

from fishing.bot import TrialResult
from fishing.mission import MissionLedger, FishingMission


class MissionTests(unittest.TestCase):
    def test_completed_mission_sends_no_device_action_on_restart(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            task = {"id": "completed_test", "targets": {"cua": 3}}
            task_path, state_path = root / "task.json", root / "state.json"
            task_path.write_text(json.dumps(task), encoding="utf-8")
            ledger = MissionLedger(state_path, task)
            ledger.data["counts"] = {"cua": 3}
            ledger.save()
            with patch("fishing.mission.TravelController"), redirect_stdout(StringIO()):
                mission = FishingMission(object(), task_path, state_path)
                mission.output = root / "output"
                self.assertEqual(mission.run()["status"], "COMPLETE")

    def test_progress_survives_restart_and_sale_without_double_count(self):
        task = {"id": "test", "targets": {"ca_chep_vang": 2, "cua": 3, "ca_chim": 2}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / "state.json"
            ledger = MissionLedger(path, task)
            fish = TrialResult("SUCCESS", "ok", 1, 4, 4, "ca_chep_vang", "Cá chép vàng", 1., "ca_ro", True)
            ledger.record("a", fish)
            ledger = MissionLedger(path, task)
            self.assertFalse(ledger.record("a", fish))
            self.assertEqual(ledger.data["counts"]["ca_chep_vang"], 1)
            ledger.event("SALE_CONFIRMED", {})
            self.assertEqual(ledger.data["unsold"], {})
            self.assertEqual(ledger.data["counts"]["ca_chep_vang"], 1)
            ledger.record("b", fish)
            self.assertEqual(ledger.needed_area(), "ca_noc")

    def test_bait_unknown_then_empty_receipt_and_consumption(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            ledger = MissionLedger(Path(folder) / "state.json", {"targets": {"cua": 1}})
            self.assertIsNone(ledger.data["bait_remaining"])
            ledger.record("empty", TrialResult("OUT_OF_BAIT", "empty", 0, 0, 0))
            ledger.event("PURCHASE_PENDING", {})
            self.assertTrue(ledger.data["purchase_pending"])
            ledger.event("PURCHASE_CONFIRMED", {"quantity": 20})
            ledger.record("cast", TrialResult("RESULT", "finish", 1, 0, 0))
            self.assertEqual(ledger.data["bait_remaining"], 19)
            self.assertEqual(ledger.data["bait_purchased"], 20)

    def test_complete_requires_every_target(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            ledger = MissionLedger(Path(folder) / "state.json", {"targets": {"cua": 3}})
            for index in range(3):
                ledger.record(str(index), TrialResult("SUCCESS", "ok", 1, 0, 0, "cua"))
                self.assertEqual(ledger.complete(), index == 2)
            self.assertIsNone(ledger.needed_area())
