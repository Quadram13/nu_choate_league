from __future__ import annotations

from typing import Any

from ..records import round_points


def score_sleeper(stats: dict[str, Any], settings: dict[str, Any]) -> float:
    total = 0.0
    for key, weight in settings.items():
        try:
            w = float(weight or 0)
        except (TypeError, ValueError):
            continue
        if w == 0:
            continue
        try:
            value = float(stats.get(key) or 0)
        except (TypeError, ValueError):
            continue
        total += value * w
    return round_points(total)
