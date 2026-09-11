from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from ..catalog import IdentityIndex
from ..dumps import DumpError, SKIP_SLEEPER_IDS, load_json, season_dir
from ..models import (
    DraftPick,
    LineupSlot,
    Matchup,
    MatchupSide,
    OfficialRecord,
    Platform,
    PlayerMove,
    Season,
    TeamSeason,
    Transaction,
    WeekScore,
)
from ..players import PlayerIndex
from ..records import apply_records, round_points
from .common import resolve_player


def ingest_sleeper(
    season: Season,
    managers: IdentityIndex,
    players: PlayerIndex,
) -> tuple[list[TeamSeason], list[Matchup], list[OfficialRecord], list[DraftPick], list[Transaction], list[WeekScore], int | None]:
    folder = season_dir(season)
    league = load_json(folder / "league.json")
    users = {user["user_id"]: user for user in load_json(folder / "users.json")}
    rosters = load_json(folder / "rosters.json")
    teams, official, names, roster_owners = _teams(season, rosters, users, managers)
    starter_slots = [slot for slot in (league.get("roster_positions") or []) if slot != "BN"]
    playoff_start = int((league.get("settings") or {}).get("playoff_week_start") or 15)
    playoff_teams = int((league.get("settings") or {}).get("playoff_teams") or 0)
    through_week = sleeper_through_week(league)
    matchups, week_scores = _matchups(
        season,
        folder,
        roster_owners,
        names,
        players,
        starter_slots,
        playoff_start,
        vs_median=season.vs_median,
    )
    draft_picks = _draft(season, folder, roster_owners, players)
    transactions = _transactions(season, folder, roster_owners, players)
    apply_records(teams, matchups, through_week=through_week)
    _assign_playoff_seeds(teams, playoff_teams)
    return teams, matchups, official, draft_picks, transactions, week_scores, through_week


def sleeper_through_week(league: dict[str, Any]) -> int | None:
    last_scored = (league.get("settings") or {}).get("last_scored_leg")
    if last_scored is not None:
        return int(last_scored)
    if league.get("status") != "complete":
        return 0
    return None


def _teams(
    season: Season,
    rosters: list[Any],
    users: dict[str, Any],
    managers: IdentityIndex,
) -> tuple[list[TeamSeason], list[OfficialRecord], dict[int, str], dict[int, str]]:
    teams: list[TeamSeason] = []
    official: list[OfficialRecord] = []
    names: dict[int, str] = {}
    roster_owners: dict[int, str] = {}
    for roster in rosters:
        roster_id = int(roster["roster_id"])
        owner_id = str(roster.get("owner_id") or "")
        manager = managers.resolve(season.platform, owner_id)
        if manager is None:
            raise DumpError(f"{season.year} Sleeper roster {roster_id} owner {owner_id} is unmapped")
        user = users.get(owner_id) or {}
        meta = user.get("metadata") or {}
        team_name = str(meta.get("team_name") or "").strip() or f"Team {user.get('display_name') or manager.display_name}"
        names[roster_id] = team_name
        roster_owners[roster_id] = manager.id
        settings = roster.get("settings") or {}
        teams.append(
            TeamSeason(
                manager_id=manager.id,
                team_name=team_name,
                platform_team_id=str(roster_id),
            )
        )
        official.append(
            OfficialRecord(
                manager_id=manager.id,
                wins=int(settings.get("wins") or 0),
                losses=int(settings.get("losses") or 0),
                ties=int(settings.get("ties") or 0),
                points_for=round_points(
                    int(settings.get("fpts") or 0) + int(settings.get("fpts_decimal") or 0) / 100
                ),
            )
        )
    return teams, official, names, roster_owners


def _matchups(
    season: Season,
    folder,
    roster_owners: dict[int, str],
    names: dict[int, str],
    players: PlayerIndex,
    starter_slots: list[str],
    playoff_start: int,
    *,
    vs_median: bool,
) -> tuple[list[Matchup], list[WeekScore]]:
    matchups: list[Matchup] = []
    week_scores: list[WeekScore] = []
    weeks = folder / "weeks"
    if not weeks.is_dir():
        return matchups, week_scores
    for week_dir in sorted(weeks.iterdir()):
        if not week_dir.is_dir():
            continue
        week = int(week_dir.name)
        path = week_dir / "matchups.json"
        if not path.is_file():
            continue
        rows = load_json(path)
        if not isinstance(rows, list):
            continue
        kind = "regular" if week < playoff_start else "playoff"
        groups: dict[object, list[Any]] = defaultdict(list)
        for row in rows:
            matchup_id = row.get("matchup_id")
            if matchup_id is None:
                continue
            groups[matchup_id].append(row)
        paired_rosters: set[int] = set()
        week_h2h_scores: list[float] = []
        h2h: list[Matchup] = []
        for matchup_id, sides in groups.items():
            if len(sides) != 2:
                continue
            home = _side(sides[0], roster_owners, names, players, starter_slots)
            away = _side(sides[1], roster_owners, names, players, starter_slots)
            paired_rosters.add(int(sides[0]["roster_id"]))
            paired_rosters.add(int(sides[1]["roster_id"]))
            week_h2h_scores.extend([home.points, away.points])
            h2h.append(
                Matchup(
                    id=f"{season.year}-w{week:02d}-{matchup_id}",
                    year=season.year,
                    week=week,
                    kind=kind,
                    home=home,
                    away=away,
                )
            )
        matchups.extend(h2h)
        for row in rows:
            roster_id = int(row.get("roster_id") or 0)
            manager_id = roster_owners.get(roster_id)
            if manager_id is None:
                continue
            points = row.get("custom_points")
            if points is None:
                points = row.get("points")
            week_scores.append(
                WeekScore(
                    week=week,
                    manager_id=manager_id,
                    points=round_points(points),
                    paired=roster_id in paired_rosters,
                )
            )
        if vs_median and kind == "regular" and week_h2h_scores:
            median = round_points(statistics.median(week_h2h_scores))
            for game in h2h:
                for side in (game.home, game.away):
                    matchups.append(
                        Matchup(
                            id=f"{season.year}-w{week:02d}-median-{side.manager_id}",
                            year=season.year,
                            week=week,
                            kind="vs_median",
                            home=MatchupSide(
                                manager_id=side.manager_id,
                                team_name=side.team_name,
                                platform_team_id=side.platform_team_id,
                                points=side.points,
                                lineup=[],
                            ),
                            away=MatchupSide(
                                manager_id=None,
                                team_name="Median",
                                points=median,
                                lineup=[],
                            ),
                        )
                    )
    week_scores.sort(key=lambda row: (row.week, row.manager_id))
    return matchups, week_scores


def _assign_playoff_seeds(teams: list[TeamSeason], playoff_teams: int) -> None:
    if playoff_teams <= 0:
        return
    if not any(team.wins + team.losses + team.ties > 0 or team.points_for > 0 for team in teams):
        return
    for team in teams:
        if team.final_rank and team.final_rank <= playoff_teams:
            team.playoff_seed = team.final_rank


def _side(
    raw: dict[str, Any],
    roster_owners: dict[int, str],
    names: dict[int, str],
    players: PlayerIndex,
    starter_slots: list[str],
) -> MatchupSide:
    roster_id = int(raw["roster_id"])
    manager_id = roster_owners.get(roster_id)
    if manager_id is None:
        raise DumpError(f"Sleeper roster {roster_id} has no mapped owner")
    points = raw.get("custom_points")
    if points is None:
        points = raw.get("points")
    return MatchupSide(
        manager_id=manager_id,
        team_name=names.get(roster_id) or manager_id,
        platform_team_id=str(roster_id),
        points=round_points(points),
        lineup=_lineup(raw, players, starter_slots),
    )


def _lineup(raw: dict[str, Any], players: PlayerIndex, starter_slots: list[str]) -> list[LineupSlot]:
    starters = [str(pid) for pid in (raw.get("starters") or []) if str(pid) not in SKIP_SLEEPER_IDS]
    starter_points = raw.get("starters_points") or []
    player_points = {str(k): round_points(v) for k, v in (raw.get("players_points") or {}).items()}
    all_players = [str(pid) for pid in (raw.get("players") or []) if str(pid) not in SKIP_SLEEPER_IDS]
    slots: list[LineupSlot] = []
    started = set(starters)
    for index, player_id in enumerate(starters):
        slot = starter_slots[index] if index < len(starter_slots) else "FLEX"
        points = (
            round_points(starter_points[index])
            if index < len(starter_points)
            else player_points.get(player_id, 0.0)
        )
        slots.append(_slot(player_id, slot, points, True, players))
    for player_id in all_players:
        if player_id in started:
            continue
        slots.append(_slot(player_id, "BN", player_points.get(player_id, 0.0), False, players))
    return slots


def _draft(
    season: Season,
    folder,
    roster_owners: dict[int, str],
    players: PlayerIndex,
) -> list[DraftPick]:
    path = folder / "drafts" / "picks.json"
    if not path.is_file():
        return []
    rows = load_json(path)
    if not isinstance(rows, list):
        return []
    picks: list[DraftPick] = []
    for raw in rows:
        roster_id = int(raw.get("roster_id") or 0)
        manager_id = roster_owners.get(roster_id)
        if manager_id is None:
            continue
        player_id = raw.get("player_id")
        if player_id is None or str(player_id) in SKIP_SLEEPER_IDS:
            continue
        meta = raw.get("metadata") or {}
        hint = " ".join(part for part in (meta.get("first_name"), meta.get("last_name")) if part)
        canonical_id, name = resolve_player(players, season.platform, player_id, hint)
        picks.append(
            DraftPick(
                year=season.year,
                round=int(raw.get("round") or 0),
                overall=int(raw.get("pick_no") or 0),
                manager_id=manager_id,
                player_id=canonical_id,
                player_name=name,
                keeper=bool(raw.get("is_keeper")),
            )
        )
    picks.sort(key=lambda pick: pick.overall)
    return picks


def _transactions(
    season: Season,
    folder,
    roster_owners: dict[int, str],
    players: PlayerIndex,
) -> list[Transaction]:
    weeks = folder / "weeks"
    if not weeks.is_dir():
        return []
    rows: list[Transaction] = []
    for week_dir in sorted(weeks.iterdir()):
        if not week_dir.is_dir():
            continue
        path = week_dir / "transactions.json"
        if not path.is_file():
            continue
        payload = load_json(path)
        if not isinstance(payload, list):
            continue
        week = int(week_dir.name)
        for raw in payload:
            parsed = _sleeper_transaction(season, week, raw, roster_owners, players)
            if parsed is not None:
                rows.append(parsed)
    rows.sort(key=lambda txn: (txn.week, txn.at or 0, txn.id))
    return rows


def _sleeper_transaction(
    season: Season,
    week: int,
    raw: dict[str, Any],
    roster_owners: dict[int, str],
    players: PlayerIndex,
) -> Transaction | None:
    kind = {
        "waiver": "waiver",
        "free_agent": "free_agent",
        "trade": "trade",
        "commissioner": "commissioner",
    }.get(str(raw.get("type") or ""))
    if kind is None:
        return None
    status = str(raw.get("status") or "")
    if status not in {"complete", "failed"}:
        return None
    adds = _sleeper_moves(raw.get("adds") or {}, roster_owners, players)
    drops = _sleeper_moves(raw.get("drops") or {}, roster_owners, players)
    if not adds and not drops:
        return None
    created = raw.get("created")
    return Transaction(
        id=str(raw.get("transaction_id") or ""),
        year=season.year,
        week=int(raw.get("leg") or week),
        type=kind,
        status=status,
        at=int(created) if isinstance(created, int) else None,
        adds=adds,
        drops=drops,
    )


def _sleeper_moves(
    mapping: dict[str, Any],
    roster_owners: dict[int, str],
    players: PlayerIndex,
) -> list[PlayerMove]:
    moves: list[PlayerMove] = []
    if not isinstance(mapping, dict):
        return moves
    for player_id, roster_id in mapping.items():
        if str(player_id) in SKIP_SLEEPER_IDS:
            continue
        manager_id = roster_owners.get(int(roster_id))
        if manager_id is None:
            continue
        canonical_id, name = resolve_player(players, Platform.SLEEPER, player_id)
        moves.append(PlayerMove(player_id=canonical_id, player_name=name, manager_id=manager_id))
    return moves


def _slot(player_id: str, slot: str, points: float, started: bool, players: PlayerIndex) -> LineupSlot:
    resolved = players.from_sleeper(player_id)
    name = resolved.display_name if resolved else player_id
    return LineupSlot(
        player_id=resolved.id if resolved else player_id,
        player_name=name,
        slot=slot,
        points=points,
        started=started,
    )
