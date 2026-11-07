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


# Fan box score kept from Sleeper stats.json. Column name, then source key.
# def_int is Sleeper's `int` (defense), not pass_int and not idp_int.
# sack is Sleeper's `sack` (team defense), not pass_sack and not idp_sack.
# Rates, ranks, snaps, bonuses, yardage bands, and the IDP tree are left out.
COUNTING_STAT_FIELDS: tuple[tuple[str, str], ...] = (
    ("pass_cmp", "pass_cmp"),
    ("pass_att", "pass_att"),
    ("pass_yd", "pass_yd"),
    ("pass_td", "pass_td"),
    ("pass_int", "pass_int"),
    ("rush_att", "rush_att"),
    ("rush_yd", "rush_yd"),
    ("rush_td", "rush_td"),
    ("rec", "rec"),
    ("rec_yd", "rec_yd"),
    ("rec_td", "rec_td"),
    ("rec_tgt", "rec_tgt"),
    ("fum_lost", "fum_lost"),
    ("pass_2pt", "pass_2pt"),
    ("rush_2pt", "rush_2pt"),
    ("rec_2pt", "rec_2pt"),
    ("pass_fd", "pass_fd"),
    ("rush_fd", "rush_fd"),
    ("rec_fd", "rec_fd"),
    ("pass_rz_att", "pass_rz_att"),
    ("rush_rz_att", "rush_rz_att"),
    ("rec_rz_tgt", "rec_rz_tgt"),
    ("fgm", "fgm"),
    ("fga", "fga"),
    ("xpm", "xpm"),
    ("xpa", "xpa"),
    ("fgm_50p", "fgm_50p"),
    ("sack", "sack"),
    ("def_int", "int"),
    ("fum_rec", "fum_rec"),
    ("def_td", "def_td"),
    ("st_td", "st_td"),
    ("blk_kick", "blk_kick"),
    ("safe", "safe"),
    ("pts_allow", "pts_allow"),
    ("yds_allow", "yds_allow"),
)


def counting_stat_values(stats: dict[str, Any]) -> tuple[int, ...]:
    return tuple(_as_count(stats.get(key)) for _column, key in COUNTING_STAT_FIELDS)


def _as_count(value: Any) -> int:
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0
