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


def espn_point_buckets(applied: dict[str, Any]) -> dict[str, float]:
    """Fantasy points already applied by ESPN, split into the four stat-line buckets.

    `appliedStats` values are points (stat count times the league weight), not
    the counting stats themselves. A missing or non-numeric id is ignored.
    """
    buckets = {"pass": 0.0, "rush": 0.0, "rec": 0.0, "misc": 0.0}
    for key, value in applied.items():
        try:
            stat_id = int(key)
            amount = float(value or 0)
        except (TypeError, ValueError):
            continue
        if amount == 0:
            continue
        buckets[_espn_point_bucket(stat_id)] += amount
    return {name: round_points(total) for name, total in buckets.items()}


def _espn_point_bucket(stat_id: int) -> str:
    # Same cuts as the scoring-sheet groups: passing, rushing, receiving.
    # Fumbles, kicking, and defense land in misc, matching Sleeper's prefixes
    # (`fum_*` / `fgm` / `sack` are not pass_, rush_, or rec_).
    if stat_id <= 22:
        return "pass"
    if stat_id <= 40:
        return "rush"
    if stat_id <= 61:
        return "rec"
    return "misc"


# Raw `stats` id -> counting column. Ids that share a column are summed.
# Counts come from `stats`, never from `appliedStats` (those are points).
# Checked against 2022-2023 dumps:
# - 83 (FG made) equals 80+77+198+201, so the total uses 83 alone.
# - 74 equals 198+201, so 50+ makes use the scoring split only.
# - 84 (FG attempts) equals 83+85, and 87 (XP attempts) equals 86+88.
# - 94 (defensive TDs) equals 103+104. 93 is a blocked-kick return TD.
# - 120 (points allowed) equals 187. 127 is yards allowed.
# Red-zone columns have no ESPN stat id through 234; they stay 0.
ESPN_COUNTING_SOURCES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("pass_cmp", (1,)),
    ("pass_att", (0,)),
    ("pass_yd", (3,)),
    ("pass_td", (4,)),
    ("pass_int", (20,)),
    ("rush_att", (23,)),
    ("rush_yd", (24,)),
    ("rush_td", (25,)),
    ("rec", (53,)),
    ("rec_yd", (42,)),
    ("rec_td", (43,)),
    ("rec_tgt", (58,)),
    ("fum_lost", (72,)),
    ("pass_2pt", (19,)),
    ("rush_2pt", (26,)),
    ("rec_2pt", (44,)),
    ("pass_fd", (211,)),
    ("rush_fd", (212,)),
    ("rec_fd", (213,)),
    ("pass_rz_att", ()),
    ("rush_rz_att", ()),
    ("rec_rz_tgt", ()),
    ("fgm", (83,)),
    ("fga", (84,)),
    ("xpm", (86,)),
    ("xpa", (87,)),
    ("fgm_50p", (198, 201)),
    ("sack", (99,)),
    ("def_int", (95,)),
    ("fum_rec", (96,)),
    ("def_td", (103, 104)),
    ("st_td", (93, 101, 102)),
    ("blk_kick", (97,)),
    ("safe", (98,)),
    ("pts_allow", (120,)),
    ("yds_allow", (127,)),
)

# appliedStats ids in the 2022-2023 dumps that have no counting column.
# Their points still count in the misc bucket. Totals that do have a column
# are read from a different raw id (FG made 83, FG attempts 84, points
# allowed 120, yards allowed 127) so these band and tier flags are not summed
# on top of those totals.
ESPN_UNMAPPED_APPLIED_IDS: tuple[int, ...] = (
    63,  # Fumble recovered for TD (offensive; no fum_td column)
    77,  # FG made 40–49, already inside fgm via 83
    80,  # FG made 0–39, already inside fgm via 83
    85,  # FG miss; fga is attempts (84), not misses
    89,  # 0 PA tier
    90,  # 1–6 PA tier
    91,  # 7–13 PA tier
    92,  # 14–17 PA tier
    123,  # 28–34 PA tier
    124,  # 35–45 PA tier
    125,  # 46+ PA tier
    128,  # 0–99 yards allowed tier
    129,  # 100–199 yards allowed tier
    130,  # 200–299 yards allowed tier
    132,  # 350–399 yards allowed tier
    133,  # 400–449 yards allowed tier
    134,  # 450–499 yards allowed tier
    135,  # 500–549 yards allowed tier
    136,  # 550+ yards allowed tier
)


def counting_stat_values_espn(stats: dict[str, Any]) -> tuple[int, ...]:
    columns = tuple(column for column, _ids in ESPN_COUNTING_SOURCES)
    expected = tuple(column for column, _key in COUNTING_STAT_FIELDS)
    if columns != expected:
        raise RuntimeError("ESPN counting sources drifted from COUNTING_STAT_FIELDS")
    values: list[int] = []
    for _column, stat_ids in ESPN_COUNTING_SOURCES:
        total = 0.0
        for stat_id in stat_ids:
            raw = stats.get(str(stat_id), stats.get(stat_id))
            try:
                total += float(raw or 0)
            except (TypeError, ValueError):
                continue
        values.append(_as_count(total))
    return tuple(values)
