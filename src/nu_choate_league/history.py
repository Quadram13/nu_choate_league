from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .catalog import load_managers, load_yaml
from .dumps import load_json, season_dir
from .models import (
    CareerRecord,
    CareerSeason,
    HeadToHeadPair,
    HeadToHeadSide,
    Matchup,
    Platform,
    PlayoffFormat,
    PlayoffRound,
    SeasonBundle,
    SeasonOutcome,
    TeamSeason,
)
from .paths import maps_dir
from .records import round_points, scored, sort_standings


def attach_outcomes(bundles: list[SeasonBundle]) -> list[SeasonBundle]:
    overrides = _load_overrides()
    for bundle in bundles:
        bundle.outcome = season_outcome(bundle, overrides=overrides)
    return bundles


def season_outcome(
    bundle: SeasonBundle,
    *,
    overrides: dict[int, dict[str, str]] | None = None,
) -> SeasonOutcome:
    override = (overrides or _load_overrides()).get(bundle.season.year) or {}
    regular_champ = _regular_season_champion(bundle.teams)
    most_points = _most_points(bundle.teams)
    champion, runner_up, playoff_managers = _playoff_result(bundle)
    if "champion" in override:
        champion = override["champion"]
    if "runner_up" in override:
        runner_up = override["runner_up"]
    return SeasonOutcome(
        year=bundle.season.year,
        champion=champion,
        runner_up=runner_up,
        regular_season_champion=regular_champ,
        most_points=most_points,
        playoff_managers=sorted(playoff_managers),
        playoff_format=_playoff_format(bundle, playoff_managers),
    )


def career_records(bundles: list[SeasonBundle]) -> list[CareerRecord]:
    by_id: dict[str, CareerRecord] = {}
    for bundle in bundles:
        outcome = bundle.outcome or season_outcome(bundle)
        playoff = set(outcome.playoff_managers)
        for team in bundle.teams:
            if not _played(team):
                continue
            row = by_id.setdefault(team.manager_id, CareerRecord(manager_id=team.manager_id))
            year = CareerSeason(
                year=bundle.season.year,
                team_name=team.team_name,
                wins=team.wins,
                losses=team.losses,
                ties=team.ties,
                points_for=team.points_for,
                points_against=team.points_against,
                regular_season_rank=team.final_rank,
                playoff=team.manager_id in playoff,
                champion=team.manager_id == outcome.champion,
                runner_up=team.manager_id == outcome.runner_up,
                regular_season_champion=team.manager_id == outcome.regular_season_champion,
                most_points=team.manager_id == outcome.most_points,
            )
            row.years.append(year)
            row.seasons += 1
            row.wins += team.wins
            row.losses += team.losses
            row.ties += team.ties
            row.points_for = round_points(row.points_for + team.points_for)
            row.points_against = round_points(row.points_against + team.points_against)
            row.titles += int(year.champion)
            row.runner_up += int(year.runner_up)
            row.playoff_appearances += int(year.playoff)
            row.regular_season_titles += int(year.regular_season_champion)
            row.most_points_titles += int(year.most_points)
    for row in by_id.values():
        row.years.sort(key=lambda item: item.year)
    return sorted(
        by_id.values(),
        key=lambda row: (
            -row.titles,
            -_win_pct(row),
            -row.points_for,
            row.manager_id,
        ),
    )


def head_to_head(bundles: list[SeasonBundle]) -> list[HeadToHeadPair]:
    pairs: dict[tuple[str, str], HeadToHeadPair] = {}
    for bundle in bundles:
        playoff_ids = set((bundle.outcome or season_outcome(bundle)).playoff_managers)
        for matchup in bundle.matchups:
            if bundle.through_week is not None and matchup.week > bundle.through_week:
                continue
            if not scored(matchup):
                continue
            left_id = matchup.home.manager_id
            right_id = matchup.away.manager_id
            if not left_id or not right_id:
                continue
            if matchup.kind == "regular":
                bucket = "regular"
            elif matchup.kind == "playoff" and left_id in playoff_ids and right_id in playoff_ids:
                bucket = "playoff"
            else:
                continue
            key = (left_id, right_id) if left_id < right_id else (right_id, left_id)
            pair = pairs.setdefault(key, HeadToHeadPair(left=key[0], right=key[1]))
            side: HeadToHeadSide = pair.regular if bucket == "regular" else pair.playoff
            _add_h2h(side, matchup, key[0])
    return sorted(
        pairs.values(),
        key=lambda pair: (
            -(pair.regular.games + pair.playoff.games),
            pair.left,
            pair.right,
        ),
    )


def format_career(rows: list[CareerRecord]) -> str:
    names = {manager.id: manager.display_name for manager in load_managers()}
    lines = ["Manager              Yrs  W-L-T       PF       Titles  RS  PO"]
    for row in rows:
        label = names.get(row.manager_id, row.manager_id)
        record = f"{row.wins}-{row.losses}-{row.ties}"
        lines.append(
            f"{label:20} {row.seasons:3}  {record:10} {row.points_for:8.2f}  "
            f"{row.titles:6} {row.regular_season_titles:3} {row.playoff_appearances:3}"
        )
    return "\n".join(lines) + "\n"


def format_h2h(pairs: list[HeadToHeadPair], manager_id: str | None = None) -> str:
    names = {manager.id: manager.display_name for manager in load_managers()}
    if manager_id:
        pairs = [pair for pair in pairs if manager_id in {pair.left, pair.right}]
    lines = ["Matchup                              Reg W-L     PF-PA           Playoff"]
    for pair in pairs:
        left_id, right_id = pair.left, pair.right
        regular, playoff = pair.regular, pair.playoff
        if manager_id and manager_id == pair.right:
            left_id, right_id = pair.right, pair.left
            regular = _flip_h2h(regular)
            playoff = _flip_h2h(playoff)
        left = names.get(left_id, left_id)
        right = names.get(right_id, right_id)
        reg = _h2h_text(regular)
        po = _h2h_text(playoff) if playoff.games else "-"
        lines.append(f"{left:18} vs {right:18} {reg:28} {po}")
    return "\n".join(lines) + "\n"


def _flip_h2h(side: HeadToHeadSide) -> HeadToHeadSide:
    return HeadToHeadSide(
        wins=side.losses,
        losses=side.wins,
        ties=side.ties,
        points_for=side.points_against,
        points_against=side.points_for,
        games=side.games,
    )


def _h2h_text(side: HeadToHeadSide) -> str:
    return f"{side.wins}-{side.losses}-{side.ties}  {side.points_for:.1f}-{side.points_against:.1f}"


def _playoff_format(bundle: SeasonBundle, playoff_managers: list[str]) -> PlayoffFormat | None:
    if bundle.season.platform is Platform.SLEEPER:
        return _sleeper_format(bundle)
    return _espn_format(bundle, playoff_managers)


def _espn_format(bundle: SeasonBundle, playoff_managers: list[str]) -> PlayoffFormat | None:
    games = [matchup for matchup in bundle.matchups if matchup.kind == "playoff" and scored(matchup)]
    if not games:
        return None
    weeks = sorted({game.week for game in games})
    rounds: list[PlayoffRound] = []
    for index, week in enumerate(weeks):
        name = "championship" if index == len(weeks) - 1 else "semifinal"
        rounds.append(PlayoffRound(name=name, week=week, byes=0))
    return PlayoffFormat(
        teams=len(playoff_managers),
        byes=0,
        start_week=weeks[0],
        rounds=rounds,
    )


def _sleeper_format(bundle: SeasonBundle) -> PlayoffFormat | None:
    folder = season_dir(bundle.season)
    league_path = folder / "league.json"
    if not league_path.is_file():
        return None
    settings = load_json(league_path).get("settings") or {}
    teams = int(settings.get("playoff_teams") or 0)
    start = int(settings.get("playoff_week_start") or 15)
    if teams <= 0:
        return None
    bracket_path = folder / "winners_bracket.json"
    bracket_rounds: list[int] = []
    if bracket_path.is_file():
        rows = load_json(bracket_path)
        if isinstance(rows, list):
            bracket_rounds = [
                int(row["r"]) for row in rows if isinstance(row, dict) and row.get("r") is not None
            ]
    first_playing = _sleeper_first_round_playing(bracket_path)
    byes = max(teams - first_playing, 0) if first_playing else (2 if teams == 6 else 0)
    if not bracket_rounds:
        bracket_rounds = [1, 2, 3] if byes else [1, 2]
    unique_rounds = sorted(set(bracket_rounds))
    min_r = unique_rounds[0]
    max_r = unique_rounds[-1]
    rounds: list[PlayoffRound] = []
    for round_no in unique_rounds:
        week = start + (round_no - min_r)
        if round_no == max_r:
            name = "championship"
            round_byes = 0
        elif round_no == min_r and byes:
            name = "wildcard"
            round_byes = byes
        else:
            name = "semifinal"
            round_byes = 0
        rounds.append(PlayoffRound(name=name, week=week, byes=round_byes))
    return PlayoffFormat(teams=teams, byes=byes, start_week=start, rounds=rounds)


def _sleeper_first_round_playing(path: Path) -> int:
    if not path.is_file():
        return 0
    rows = load_json(path)
    if not isinstance(rows, list) or not rows:
        return 0
    round_nos = [int(row["r"]) for row in rows if isinstance(row, dict) and row.get("r") is not None]
    if not round_nos:
        return 0
    first = min(round_nos)
    playing = 0
    for row in rows:
        if not isinstance(row, dict) or int(row.get("r") or 0) != first or row.get("p") is not None:
            continue
        playing += sum(1 for key in ("t1", "t2") if row.get(key) is not None)
    return playing


def _playoff_result(bundle: SeasonBundle) -> tuple[str | None, str | None, list[str]]:
    if bundle.season.platform is Platform.SLEEPER:
        return _sleeper_playoff(bundle)
    return _espn_playoff(bundle)


def _espn_playoff(bundle: SeasonBundle) -> tuple[str | None, str | None, list[str]]:
    games = [matchup for matchup in bundle.matchups if matchup.kind == "playoff" and scored(matchup)]
    managers = _managers_from_games(games)
    if not games:
        return None, None, []
    last_week = max(game.week for game in games)
    finals = [game for game in games if game.week == last_week]
    if len(finals) != 1:
        raise ValueError(
            f"{bundle.season.year} ESPN playoff final week {last_week} has {len(finals)} games; "
            "set maps/champions.yaml"
        )
    champion, runner_up = _winner_loser(finals[0])
    return champion, runner_up, managers


def _sleeper_playoff(bundle: SeasonBundle) -> tuple[str | None, str | None, list[str]]:
    path = season_dir(bundle.season) / "winners_bracket.json"
    if not path.is_file():
        return None, None, []
    rows = load_json(path)
    if not isinstance(rows, list):
        return None, None, []
    roster_owner = {int(team.platform_team_id): team.manager_id for team in bundle.teams}
    playoff: set[str] = set()
    champion = None
    runner_up = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in ("t1", "t2"):
            roster_id = row.get(key)
            if roster_id is None:
                continue
            manager_id = roster_owner.get(int(roster_id))
            if manager_id:
                playoff.add(manager_id)
        if row.get("p") != 1:
            continue
        winner = row.get("w")
        loser = row.get("l")
        if winner is None:
            return None, None, []
        champion = roster_owner.get(int(winner))
        runner_up = roster_owner.get(int(loser)) if loser is not None else None
    if champion is None:
        return None, None, []
    return champion, runner_up, sorted(playoff)


def _regular_season_champion(teams: list[TeamSeason]) -> str | None:
    played = [team for team in teams if _played(team)]
    if not played:
        return None
    return sort_standings(played)[0].manager_id


def _most_points(teams: list[TeamSeason]) -> str | None:
    played = [team for team in teams if _played(team)]
    if not played:
        return None
    best = max(played, key=lambda team: (team.points_for, -(team.final_rank or 99), team.manager_id))
    return best.manager_id


def _played(team: TeamSeason) -> bool:
    return team.wins + team.losses + team.ties > 0 or team.points_for > 0


def _winner_loser(matchup: Matchup) -> tuple[str | None, str | None]:
    home_id = matchup.home.manager_id
    away_id = matchup.away.manager_id
    if matchup.home.points > matchup.away.points:
        return home_id, away_id
    if matchup.away.points > matchup.home.points:
        return away_id, home_id
    return None, None


def _managers_from_games(games: list[Matchup]) -> list[str]:
    found: set[str] = set()
    for matchup in games:
        for side in (matchup.home, matchup.away):
            if side.manager_id:
                found.add(side.manager_id)
    return sorted(found)


def _add_h2h(side: HeadToHeadSide, matchup: Matchup, left_id: str) -> None:
    home_is_left = matchup.home.manager_id == left_id
    left_pts = matchup.home.points if home_is_left else matchup.away.points
    right_pts = matchup.away.points if home_is_left else matchup.home.points
    side.games += 1
    side.points_for = round_points(side.points_for + left_pts)
    side.points_against = round_points(side.points_against + right_pts)
    if left_pts > right_pts:
        side.wins += 1
    elif left_pts < right_pts:
        side.losses += 1
    else:
        side.ties += 1


def _win_pct(row: CareerRecord) -> float:
    games = row.wins + row.losses + row.ties
    if games == 0:
        return 0.0
    return (row.wins + 0.5 * row.ties) / games


@lru_cache(maxsize=1)
def _load_overrides() -> dict[int, dict[str, str]]:
    path: Path = maps_dir() / "champions.yaml"
    if not path.is_file():
        return {}
    data = load_yaml(path)
    raw = data.get("outcomes") or data
    result: dict[int, dict[str, str]] = {}
    if not isinstance(raw, dict):
        return result
    for year, row in raw.items():
        if str(year).startswith("#") or not isinstance(row, dict):
            continue
        try:
            year_n = int(year)
        except (TypeError, ValueError):
            continue
        result[year_n] = {
            key: str(value)
            for key, value in row.items()
            if key in {"champion", "runner_up"} and value
        }
    return result
