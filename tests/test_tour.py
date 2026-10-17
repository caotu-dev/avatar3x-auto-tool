import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from fishing.bot import TrialResult
from fishing.session import SessionResult
from fishing.tour import FishingTour


class FakeTravel:
    def __init__(self, device, output):
        self.bait_purchased = 0
        self.actions = []

    def center(self, area=None):
        self.actions.append(("center", area))

    def enter(self, area):
        self.actions.append(("enter", area))

    def sell_and_buy(self):
        self.bait_purchased += 20
        self.actions.append(("buy", 20))
        return 20


class TourTests(unittest.TestCase):
    def run_tour(self, results, refills=2):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, redirect_stdout(StringIO()), \
                patch("fishing.tour.TravelController", FakeTravel), \
                patch("fishing.tour.FishingSession") as session:
            session.return_value.run.side_effect = results
            tour = FishingTour(object(), rounds_per_area=1, max_refills=refills, output=Path(folder))
            report = tour.run()
            return report, tour.travel.actions

    def test_out_of_bait_refills_then_continues_both_areas(self):
        empty = SessionResult("OUT_OF_BAIT", "empty", ())
        puffer = TrialResult("SUCCESS", "ok", 1, 4, 4,
                             fish_species="cua", area="ca_noc", bite_observed=True)
        shark = TrialResult("RESULT", "finish", 1, 0, 0, area="ca_map")
        report, actions = self.run_tour([
            empty, SessionResult("COMPLETE", "ok", (puffer,)),
            SessionResult("COMPLETE", "ok", (shark,))])
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["bait_purchased"], 60)
        self.assertEqual((report["caught"], report["misses"]), (1, 1))
        self.assertEqual(actions.count(("enter", "ca_noc")), 2)
        self.assertEqual(actions[-1], ("center", "ca_map"))

    def test_refill_limit_stops_without_another_purchase(self):
        report, actions = self.run_tour([SessionResult("OUT_OF_BAIT", "empty", ())], refills=0)
        self.assertEqual(report["status"], "STOPPED")
        self.assertEqual(actions.count(("buy", 20)), 1)

    def test_unresolved_state_does_not_navigate_or_buy_again(self):
        report, actions = self.run_tour([SessionResult("STOPPED", "unknown", ())])
        self.assertEqual(report["status"], "STOPPED")
        self.assertEqual(actions[-1], ("enter", "ca_noc"))
