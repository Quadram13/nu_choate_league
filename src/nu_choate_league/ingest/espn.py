from __future__ import annotations

from typing import Any

from ..catalog import IdentityIndex
from ..dumps import ESPN_POSITIONS, DumpError, load_json, season_dir
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

ESPN_SLOTS = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    16: "DEF",
    17: "K",
    20: "BN",
    21: "IR",
    23: "FLEX",
}
ESPN_BENCH = {"BN", "IR"}
ESPN_KIND = {
    "NONE": "regular",
    "WINNERS_BRACKET": "playoff",
    "WINNERS_CONSOLATION_LADDER": "consolation",
    "LOSERS_CONSOLATION_LADDER": "consolation",
}


ESPN_TXN_TYPES = {
    "WAIVER": "waiver",
    "FREEAGENT": "free_agent",
    "TRADE_ACCEPT": "trade",
    "ROSTER": "drop",
}
ESPN_KEEP_STATUS = {"EXECUTED", "FAILED_INVALIDPLAYERSOURCE", "FAILED_PLAYERALREADYDROPPED", "FAILED_ROSTERLIMIT"}


def ingest_espn(
    season: Season,
    managers: IdentityIndex,
    players: PlayerIndex,
) -> tuple[list[TeamSeason], list[Matchup], list[OfficialRecord], list[DraftPick], list[Transaction], list[WeekScore], int | None]:
    folder = season_dir(season)
    league = load_json(folder / "league.json")
    teams, official, team_names = _teams(season, league, managers)
    owner_by_team = {int(team.platform_team_id): team.manager_id for team in teams}
    player_info = _espn_player_info(folder)
    period_weeks = _matchup_period_weeks(league)
    matchups = _matchups(season, folder, owner_by_team, team_names, players, period_weeks)
    draft_picks = _draft(season, folder, owner_by_team, managers, players, player_info)
    transactions = _transactions(season, folder, owner_by_team, players, player_info)
    apply_records(teams, matchups)
    return teams, matchups, official, draft_picks, transactions, _week_scores(matchups), None


def _teams(
    season: Season,
    league: dict[str, Any],
    managers: IdentityIndex,
) -> tuple[list[TeamSeason], list[OfficialRecord], dict[int, str]]:
    teams: list[TeamSeason] = []
    official: list[OfficialRecord] = []
    names: dict[int, str] = {}
    for raw in league.get("teams") or []:
        team_id = int(raw["id"])
        owner = str(raw.get("primaryOwner") or "")
        manager = managers.resolve(season.platform, owner)
        if manager is None:
            raise DumpError(f"{season.year} ESPN team {team_id} owner {owner} is unmapped")
        name = str(raw.get("name") or manager.display_name).strip()
        names[team_id] = name
        record = (raw.get("record") or {}).get("overall") or {}
        seed = raw.get("playoffSeed")
        teams.append(
            TeamSeason(
                manager_id=manager.id,
                team_name=name,
                platform_team_id=str(team_id),
                playoff_seed=int(seed) if seed else None,
            )
        )
        official.append(
            OfficialRecord(
                manager_id=manager.id,
                wins=int(record.get("wins") or 0),
                losses=int(record.get("losses") or 0),
                ties=int(record.get("ties") or 0),
                points_for=round_points(raw.get("points")),
            )
        )
    return teams, official, names


def _matchup_period_weeks(league: dict[str, Any]) -> dict[int, list[int]]:
    settings = (league.get("settings") or {}).get("scheduleSettings") or {}
    raw = settings.get("matchupPeriods") or {}
    mapping: dict[int, list[int]] = {}
    for period, weeks in raw.items():
        mapping[int(period)] = [int(week) for week in weeks]
    return mapping


def _matchups(
    season: Season,
    folder,
    owner_by_team: dict[int, str],
    team_names: dict[int, str],
    players: PlayerIndex,
    period_weeks: dict[int, list[int]],
) -> list[Matchup]:
    matchups: list[Matchup] = []
    weeks = folder / "weeks"
    if not weeks.is_dir():
        return matchups
    for week_dir in sorted(weeks.iterdir()):
        if not week_dir.is_dir():
            continue
        week = int(week_dir.name)
        path = week_dir / "boxscore.json"
        if not path.is_file():
            continue
        payload = load_json(path)
        for raw in payload.get("schedule") or []:
            period = int(raw.get("matchupPeriodId") or 0)
            scoring_weeks = period_weeks.get(period) or [period]
            if week not in scoring_weeks:
                continue
            home_raw = raw.get("home")
            away_raw = raw.get("away")
            if not isinstance(home_raw, dict) or not isinstance(away_raw, dict):
                continue
            kind = ESPN_KIND.get(str(raw.get("playoffTierType") or "NONE"), "regular")
            home = _side(home_raw, owner_by_team, team_names, players, week, len(scoring_weeks))
            away = _side(away_raw, owner_by_team, team_names, players, week, len(scoring_weeks))
            matchups.append(
                Matchup(
                    id=f"{season.year}-w{week:02d}-{raw.get('id')}",
                    year=season.year,
                    week=week,
                    kind=kind,
                    home=home,
                    away=away,
                )
            )
    return matchups


def _espn_player_info(folder) -> dict[int, tuple[str, str | None]]:
    path = folder / "pro_players.json"
    info: dict[int, tuple[str, str | None]] = {}
    if not path.is_file():
        return info
    pool = load_json(path)
    if not isinstance(pool, list):
        return info
    for entry in pool:
        if not isinstance(entry, dict):
            continue
        player_id = entry.get("id")
        if not isinstance(player_id, int):
            continue
        name = str(entry.get("fullName") or "").strip()
        position_id = entry.get("defaultPositionId")
        position = ESPN_POSITIONS.get(int(position_id)) if isinstance(position_id, int) else None
        info[player_id] = (name, position)
    return info


def _resolve_espn(
    players: PlayerIndex,
    player_id: int,
    player_info: dict[int, tuple[str, str | None]],
) -> tuple[str, str]:
    name, position = player_info.get(player_id, ("", None))
    return resolve_player(players, Platform.ESPN, player_id, name, position)


def _draft(
    season: Season,
    folder,
    owner_by_team: dict[int, str],
    managers: IdentityIndex,
    players: PlayerIndex,
    player_info: dict[int, tuple[str, str | None]],
) -> list[DraftPick]:
    path = folder / "draft.json"
    if not path.is_file():
        return []
    payload = load_json(path)
    picks: list[DraftPick] = []
    for raw in (payload.get("draftDetail") or {}).get("picks") or []:
        team_id = int(raw.get("teamId") or 0)
        manager_id = owner_by_team.get(team_id)
        if manager_id is None:
            member = managers.resolve(season.platform, str(raw.get("memberId") or ""))
            manager_id = member.id if member else None
        if manager_id is None:
            continue
        player_id = raw.get("playerId")
        if not isinstance(player_id, int) or player_id == 0:
            continue
        canonical_id, name = _resolve_espn(players, player_id, player_info)
        picks.append(
            DraftPick(
                year=season.year,
                round=int(raw.get("roundId") or 0),
                overall=int(raw.get("overallPickNumber") or 0),
                manager_id=manager_id,
                player_id=canonical_id,
                player_name=name,
                keeper=bool(raw.get("keeper")),
            )
        )
    picks.sort(key=lambda pick: pick.overall)
    return picks


def _transactions(
    season: Season,
    folder,
    owner_by_team: dict[int, str],
    players: PlayerIndex,
    player_info: dict[int, tuple[str, str | None]],
) -> list[Transaction]:
    weeks = folder / "weeks"
    if not weeks.is_dir():
        return []
    seen: set[str] = set()
    trades_seen: set[str] = set()
    rows: list[Transaction] = []
    for week_dir in sorted(weeks.iterdir()):
        if not week_dir.is_dir():
            continue
        path = week_dir / "transactions.json"
        if not path.is_file():
            continue
        week = int(week_dir.name)
        payload = load_json(path)
        for raw in payload.get("transactions") or []:
            txn_id = str(raw.get("id") or "")
            if not txn_id or txn_id in seen:
                continue
            seen.add(txn_id)
            parsed = _espn_transaction(season, week, raw, owner_by_team, players, player_info, trades_seen)
            if parsed is not None:
                rows.append(parsed)
    # Weekly mTransactions2 only includes player lists on the cookie owner's
    # executed trades. Everyone else's completed deals are on player cards.
    for raw in _espn_player_card_trades(folder, trades_seen):
        week = int(raw.get("scoringPeriodId") or 0)
        if not week:
            continue
        parsed = _espn_transaction(season, week, raw, owner_by_team, players, player_info, trades_seen)
        if parsed is not None:
            rows.append(parsed)
    rows.sort(key=lambda txn: (txn.week, txn.at or 0, txn.id))
    return rows


def _espn_player_card_trades(folder, trades_seen: set[str]) -> list[dict[str, Any]]:
    cards = folder / "player_cards"
    if not cards.is_dir():
        return []
    best: dict[str, dict[str, Any]] = {}
    for path in sorted(cards.glob("*.json")):
        payload = load_json(path)
        for entry in payload.get("players") or []:
            if not isinstance(entry, dict):
                continue
            for raw in entry.get("transactions") or []:
                if not isinstance(raw, dict):
                    continue
                if raw.get("type") != "TRADE_ACCEPT" or raw.get("status") != "EXECUTED":
                    continue
                items = [item for item in (raw.get("items") or []) if item.get("type") == "TRADE"]
                if not items:
                    continue
                related = str(raw.get("relatedTransactionId") or raw.get("id") or "")
                txn_id = str(raw.get("id") or "")
                if not related or related in trades_seen or txn_id in trades_seen:
                    continue
                current = best.get(related)
                current_n = (
                    len([item for item in (current.get("items") or []) if item.get("type") == "TRADE"])
                    if current
                    else -1
                )
                if current is None or len(items) > current_n:
                    best[related] = raw
    return list(best.values())


def _espn_transaction(
    season: Season,
    week: int,
    raw: dict[str, Any],
    owner_by_team: dict[int, str],
    players: PlayerIndex,
    player_info: dict[int, tuple[str, str | None]],
    trades_seen: set[str],
) -> Transaction | None:
    espn_type = str(raw.get("type") or "")
    kind = ESPN_TXN_TYPES.get(espn_type)
    if kind is None:
        return None
    status_raw = str(raw.get("status") or "")
    if kind == "trade":
        items = [item for item in (raw.get("items") or []) if item.get("type") == "TRADE"]
        if not items:
            return None
        if status_raw != "EXECUTED":
            return None
        related = str(raw.get("relatedTransactionId") or raw.get("id"))
        txn_id = str(raw.get("id") or related)
        if related in trades_seen or txn_id in trades_seen:
            return None
        team_ids: set[int] = set()
        for item in items:
            for key in ("fromTeamId", "toTeamId"):
                team_id = int(item.get(key) or 0)
                if team_id:
                    team_ids.add(team_id)
        if len(team_ids) != 2 or not team_ids.issubset(owner_by_team):
            return None
        trades_seen.add(related)
        trades_seen.add(txn_id)
        adds, drops = _espn_trade_moves(items, owner_by_team, players, player_info)
        if not adds and not drops:
            return None
        return Transaction(
            id=str(raw.get("id")),
            year=season.year,
            week=int(raw.get("scoringPeriodId") or week),
            type="trade",
            status="complete",
            at=_espn_timestamp(raw),
            adds=adds,
            drops=drops,
        )
    if status_raw not in ESPN_KEEP_STATUS:
        return None
    status = "complete" if status_raw == "EXECUTED" else "failed"
    adds: list[PlayerMove] = []
    drops: list[PlayerMove] = []
    for item in raw.get("items") or []:
        item_type = item.get("type")
        player_id = item.get("playerId")
        if item_type not in {"ADD", "DROP"} or not isinstance(player_id, int) or player_id == 0:
            continue
        canonical_id, name = _resolve_espn(players, player_id, player_info)
        if item_type == "ADD":
            manager_id = owner_by_team.get(int(item.get("toTeamId") or 0))
            if manager_id:
                adds.append(PlayerMove(player_id=canonical_id, player_name=name, manager_id=manager_id))
        else:
            manager_id = owner_by_team.get(int(item.get("fromTeamId") or 0))
            if manager_id:
                drops.append(PlayerMove(player_id=canonical_id, player_name=name, manager_id=manager_id))
    if kind == "drop" and not drops:
        return None
    if kind in {"waiver", "free_agent"} and not adds and not drops:
        return None
    bid = raw.get("bidAmount")
    return Transaction(
        id=str(raw.get("id")),
        year=season.year,
        week=int(raw.get("scoringPeriodId") or week),
        type=kind,
        status=status,
        at=_espn_timestamp(raw),
        bid=int(bid) if isinstance(bid, int) else None,
        note=status_raw if status == "failed" else None,
        adds=adds,
        drops=drops,
    )


def _espn_trade_moves(
    items: list[Any],
    owner_by_team: dict[int, str],
    players: PlayerIndex,
    player_info: dict[int, tuple[str, str | None]],
) -> tuple[list[PlayerMove], list[PlayerMove]]:
    adds: list[PlayerMove] = []
    drops: list[PlayerMove] = []
    for item in items:
        player_id = item.get("playerId")
        if not isinstance(player_id, int) or player_id == 0:
            continue
        canonical_id, name = _resolve_espn(players, player_id, player_info)
        from_id = owner_by_team.get(int(item.get("fromTeamId") or 0))
        to_id = owner_by_team.get(int(item.get("toTeamId") or 0))
        if from_id:
            drops.append(PlayerMove(player_id=canonical_id, player_name=name, manager_id=from_id))
        if to_id:
            adds.append(PlayerMove(player_id=canonical_id, player_name=name, manager_id=to_id))
    return adds, drops


def _espn_timestamp(raw: dict[str, Any]) -> int | None:
    for key in ("processDate", "acceptedDate", "proposedDate"):
        value = raw.get(key)
        if isinstance(value, int):
            return value
    return None


def _week_scores(matchups: list[Matchup]) -> list[WeekScore]:
    best: dict[tuple[int, str], tuple[int, WeekScore]] = {}
    for matchup in matchups:
        if matchup.kind == "vs_median":
            continue
        priority = 2 if matchup.kind == "playoff" else 1
        for side in (matchup.home, matchup.away):
            if not side.manager_id:
                continue
            key = (matchup.week, side.manager_id)
            current = best.get(key)
            if current is None or priority >= current[0]:
                best[key] = (
                    priority,
                    WeekScore(
                        week=matchup.week,
                        manager_id=side.manager_id,
                        points=side.points,
                        paired=True,
                    ),
                )
    return sorted((row for _, row in best.values()), key=lambda item: (item.week, item.manager_id))


def _side(
    raw: dict[str, Any],
    owner_by_team: dict[int, str],
    team_names: dict[int, str],
    players: PlayerIndex,
    scoring_week: int,
    period_length: int,
) -> MatchupSide:
    team_id = int(raw.get("teamId") or 0)
    manager_id = owner_by_team.get(team_id)
    if manager_id is None:
        raise DumpError(f"ESPN team {team_id} has no mapped owner")
    roster = raw.get("rosterForCurrentScoringPeriod") or {}
    return MatchupSide(
        manager_id=manager_id,
        team_name=team_names.get(team_id) or manager_id,
        platform_team_id=str(team_id),
        points=_scoring_week_points(raw, scoring_week, period_length),
        lineup=_lineup(roster.get("entries") or [], players),
    )


def _scoring_week_points(raw: dict[str, Any], scoring_week: int, period_length: int) -> float:
    pbs = raw.get("pointsByScoringPeriod") or {}
    weekly = pbs.get(str(scoring_week))
    if weekly is None:
        weekly = pbs.get(scoring_week)
    if weekly is not None:
        return round_points(weekly)
    if period_length == 1:
        return round_points(raw.get("totalPoints"))
    return 0.0


def _lineup(entries: list[Any], players: PlayerIndex) -> list[LineupSlot]:
    slots: list[LineupSlot] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        player_id = entry.get("playerId")
        pool = entry.get("playerPoolEntry") or {}
        player = pool.get("player") if isinstance(pool.get("player"), dict) else {}
        if not isinstance(player_id, int) or player_id == 0:
            nested = player.get("id") if isinstance(player, dict) else None
            if isinstance(nested, int):
                player_id = nested
        if not isinstance(player_id, int) or player_id == 0:
            continue
        raw_slot = entry.get("lineupSlotId")
        slot_id = 20 if raw_slot is None else int(raw_slot)
        slot = ESPN_SLOTS.get(slot_id, "BN")
        name = str(player.get("fullName") or "")
        position = ESPN_POSITIONS.get(int(player.get("defaultPositionId") or 0))
        resolved = players.resolve_espn(player_id, name=name, position=position)
        slots.append(
            LineupSlot(
                player_id=resolved.id,
                player_name=resolved.display_name or name or resolved.id,
                slot=slot,
                points=round_points(pool.get("appliedStatTotal")),
                started=slot not in ESPN_BENCH,
            )
        )
    return slots
