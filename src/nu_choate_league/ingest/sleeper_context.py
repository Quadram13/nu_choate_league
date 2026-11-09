"""Sleeper weekly context from stats.json: snaps, snap opportunity, gp/gs, ranks.

ESPN seasons have no equivalent dump. Callers skip them. Nothing here invents
2022–2023 rows from boxscores.
"""

from __future__ import annotations

from typing import Any

from ..dumps import load_json, season_dir
from ..models import PlayerWeekSleeperContext, Season
from ..players import PlayerIndex
from .score import score_sleeper_buckets

# Column order is the insert order. Source key matches the column name.
SLEEPER_CONTEXT_COLUMNS: tuple[str, ...] = (
    "gp",
    "gs",
    "off_snp",
    "def_snp",
    "st_snp",
    "tm_off_snp",
    "tm_def_snp",
    "tm_st_snp",
    "pos_rank_ppr",
    "pos_rank_half_ppr",
    "pos_rank_std",
)

# A game or a snap opens a row. Rank and team-snap totals do not: Sleeper
# writes those on players who never played.
_PLAYED_KEYS = ("gp", "gs", "off_snp", "def_snp", "st_snp")
_RANK_KEYS = ("pos_rank_ppr", "pos_rank_half_ppr", "pos_rank_std")

# Real positional ranks in the 2024–2026 dumps stay under 200. 999 is the
# unranked filler on defenses, kickers, and players Sleeper did not rank.
_UNRANKED_RANK = 999


def sleeper_context_rows(
    season: Season,
    *,
    through_week: int | None,
    players: PlayerIndex,
) -> list[PlayerWeekSleeperContext]:
    """One row per played or fantasy-scoring player-week.

    The counting-stats gate is a non-zero fantasy bucket under this league's
    scoring settings. That set is a subset of the rows returned here. Extra
    rows are weeks with gp, gs, or a snap count above zero and all-zero
    fantasy buckets. Stat objects that only carry a positional rank or a team
    snap total are left out.

    Player ids use the same path as counting stats: `PlayerIndex.from_sleeper`,
    and the raw stats.json key when the catalog has no record. `TEAM_*`
    aggregates miss; fantasy D/ST ids such as `PHI` resolve.
    """
    folder = season_dir(season)
    league_path = folder / "league.json"
    try:
        league = load_json(league_path)
    except Exception:
        return []
    settings = league.get("scoring_settings") if isinstance(league, dict) else None
    if not isinstance(settings, dict):
        return []
    weeks = folder / "weeks"
    if not weeks.is_dir():
        return []
    chosen: dict[tuple[int, str], PlayerWeekSleeperContext] = {}
    for week_dir in sorted(weeks.iterdir()):
        if not week_dir.is_dir():
            continue
        week = int(week_dir.name)
        if through_week is not None and week > through_week:
            continue
        path = week_dir / "stats.json"
        if not path.is_file():
            continue
        try:
            stats = load_json(path)
        except Exception:
            continue
        if not isinstance(stats, dict):
            continue
        for player_id, raw in stats.items():
            if not isinstance(raw, dict):
                continue
            if not _keep_stat_object(raw, settings):
                continue
            meta = players.from_sleeper(str(player_id))
            canonical = meta.id if meta is not None else str(player_id)
            chosen[(week, canonical)] = _context_row(season.year, week, canonical, raw)
    return [chosen[key] for key in sorted(chosen)]


def context_insert_tuple(row: PlayerWeekSleeperContext) -> tuple:
    return (row.year, row.week, row.player_id, *(getattr(row, name) for name in SLEEPER_CONTEXT_COLUMNS))


def _keep_stat_object(stats: dict[str, Any], settings: dict[str, Any]) -> bool:
    if any(score_sleeper_buckets(stats, settings).values()):
        return True
    return any((value or 0) > 0 for value in (_optional_int(stats, key) for key in _PLAYED_KEYS))


def _context_row(year: int, week: int, player_id: str, stats: dict[str, Any]) -> PlayerWeekSleeperContext:
    values = {name: _optional_int(stats, name) for name in SLEEPER_CONTEXT_COLUMNS}
    for name in _RANK_KEYS:
        rank = values[name]
        if rank is not None and rank >= _UNRANKED_RANK:
            values[name] = None
    return PlayerWeekSleeperContext(year=year, week=week, player_id=player_id, **values)


def _optional_int(stats: dict[str, Any], key: str) -> int | None:
    if key not in stats:
        return None
    value = stats[key]
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None
