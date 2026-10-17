from collections import Counter
from dataclasses import asdict

from .bot import TrialResult


def fishing_statistics(rounds: list[TrialResult]) -> dict:
    areas = {}
    for area in sorted({round_.area for round_ in rounds}):
        subset = [round_ for round_ in rounds if round_.area == area]
        fish = Counter(round_.fish_species or "unknown" for round_ in subset
                       if round_.outcome == "SUCCESS")
        areas[area] = {
            "caught": sum(fish.values()), "fish_counts": dict(fish),
            "bites": sum(round_.bite_observed for round_ in subset),
            "misses_confirmed": sum(round_.outcome == "FAILED" for round_ in subset),
            "results_without_success_evidence": sum(round_.outcome == "RESULT" for round_ in subset),
            "misses": max(0,sum(round_.casts for round_ in subset)-sum(round_.bite_observed for round_ in subset)),
            "casts": sum(round_.casts for round_ in subset),
            "outcomes": dict(Counter(round_.outcome for round_ in subset)),
        }
    return {"areas": areas, "caught": sum(area["caught"] for area in areas.values()),
            "bites": sum(area["bites"] for area in areas.values()),
            "misses": sum(area["misses"] for area in areas.values()),
            "rounds": [asdict(round_) for round_ in rounds]}
