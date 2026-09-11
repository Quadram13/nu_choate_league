from __future__ import annotations

from typing import Any

from ..dumps import ESPN_POSITIONS, SKIP_SLEEPER_IDS, load_json, season_dir
from ..models import Matchup, Platform, PlayerWeek, Season
from ..players import PlayerIndex
from ..records import round_points
from .common import resolve_player
from .score import score_sleeper


def player_week_pool(
    season: Season,
    matchups: list[Matchup],
    players: PlayerIndex,
    *,
    through_week: int | None,
) -> list[PlayerWeek]:
    if season.platform is Platform.SLEEPER:
        rows = _sleeper_pool(season, players, through_week=through_week)
    else:
        rows = _espn_pool(season, matchups, players)
    _overlay_lineups(rows, matchups, players)
    return list(rows.values())


def _sleeper_pool(
    season: Season,
    players: PlayerIndex,
    *,
    through_week: int | None,
) -> dict[tuple[int, int, str], PlayerWeek]:
    folder = season_dir(season)
    league = load_json(folder / "league.json")
    settings = league.get("scoring_settings") or {}
    rows: dict[tuple[int, int, str], PlayerWeek] = {}
    weeks = folder / "weeks"
    if not weeks.is_dir():
        return rows
    for week_dir in sorted(weeks.iterdir()):
        if not week_dir.is_dir():
            continue
        week = int(week_dir.name)
        if through_week is not None and week > through_week:
            continue
        path = week_dir / "stats.json"
        if not path.is_file():
            continue
        stats = load_json(path)
        if not isinstance(stats, dict):
            continue
        for player_id, raw in stats.items():
            if str(player_id) in SKIP_SLEEPER_IDS or not isinstance(raw, dict):
                continue
            if str(player_id).startswith("TEAM_"):
                continue
            meta = players.from_sleeper(str(player_id))
            if meta is None:
                continue
            points = score_sleeper(raw, settings)
            if points == 0:
                continue
            canonical_id, name = resolve_player(players, Platform.SLEEPER, player_id)
            rows[(season.year, week, canonical_id)] = PlayerWeek(
                year=season.year,
                week=week,
                player_id=canonical_id,
                player_name=meta.display_name or name,
                position=meta.position,
                points=points,
            )
    return rows


def _espn_pool(
    season: Season,
    matchups: list[Matchup],
    players: PlayerIndex,
) -> dict[tuple[int, int, str], PlayerWeek]:
    folder = season_dir(season)
    matchup_weeks = {m.week for m in matchups if m.kind != "vs_median"}
    rows: dict[tuple[int, int, str], PlayerWeek] = {}
    cards = folder / "player_cards"
    if not cards.is_dir():
        return rows
    for path in sorted(cards.glob("*.json")):
        payload = load_json(path)
        for item in payload.get("players") or []:
            player = item.get("player") if isinstance(item, dict) else None
            if not isinstance(player, dict):
                continue
            espn_id = player.get("id")
            if not isinstance(espn_id, int):
                continue
            name = str(player.get("fullName") or "")
            position = ESPN_POSITIONS.get(int(player.get("defaultPositionId") or 0))
            canonical_id, display = resolve_player(players, Platform.ESPN, espn_id, name, position)
            for week, points in _espn_weekly_actuals(player).items():
                if matchup_weeks and week not in matchup_weeks:
                    continue
                if points == 0:
                    continue
                rows[(season.year, week, canonical_id)] = PlayerWeek(
                    year=season.year,
                    week=week,
                    player_id=canonical_id,
                    player_name=display or name,
                    position=position,
                    points=points,
                )
    return rows


def _espn_weekly_actuals(player: dict[str, Any]) -> dict[int, float]:
    weekly: dict[int, tuple[int, float]] = {}
    for raw in player.get("stats") or []:
        if not isinstance(raw, dict) or raw.get("statSourceId") != 0:
            continue
        week = raw.get("scoringPeriodId")
        if not isinstance(week, int) or week <= 0:
            continue
        split = raw.get("statSplitTypeId")
        rank = 1 if split == 1 else 0
        points = round_points(raw.get("appliedTotal"))
        current = weekly.get(week)
        if current is None or rank >= current[0]:
            weekly[week] = (rank, points)
    return {week: pts for week, (_rank, pts) in weekly.items()}


def _overlay_lineups(
    rows: dict[tuple[int, int, str], PlayerWeek],
    matchups: list[Matchup],
    players: PlayerIndex,
) -> None:
    for matchup in matchups:
        if matchup.kind == "vs_median":
            continue
        for side in (matchup.home, matchup.away):
            if not side.manager_id:
                continue
            for slot in side.lineup:
                key = (matchup.year, matchup.week, slot.player_id)
                current = rows.get(key)
                meta = players.from_sleeper(slot.player_id)
                rows[key] = PlayerWeek(
                    year=matchup.year,
                    week=matchup.week,
                    player_id=slot.player_id,
                    player_name=slot.player_name or (current.player_name if current else slot.player_id),
                    position=(current.position if current else None)
                    or (meta.position if meta else None),
                    points=slot.points,
                    rostered=True,
                    started=slot.started,
                    manager_id=side.manager_id,
                )
