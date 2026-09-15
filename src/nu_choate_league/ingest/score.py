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


def score_sleeper_buckets(stats: dict[str, Any], settings: dict[str, Any]) -> dict[str, float]:
    buckets = {"pass": 0.0, "rush": 0.0, "rec": 0.0, "misc": 0.0}
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
        if value == 0:
            continue
        buckets[_stat_bucket(key)] += value * w
    return {name: round_points(total) for name, total in buckets.items()}


def _stat_bucket(key: str) -> str:
    if key == "rec" or key.startswith("rec_"):
        return "rec"
    if key.startswith("pass_"):
        return "pass"
    if key.startswith("rush_"):
        return "rush"
    return "misc"
