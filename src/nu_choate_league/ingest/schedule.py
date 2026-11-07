"""NFL team-weeks from ESPN pro_schedule.json (2022 and 2023).

The team-id crosswalk is maps/dst.yaml. ESPN proTeamId maps to the Sleeper
abbreviation stored on players.nfl_team. That file is the D/ST identity map
and the schedule map: 32 clubs, ids 1-30 plus 33 (BAL) and 34 (HOU). ESPN's
own abbrev is a different spelling ("Wsh", "Jax", "Ind") and is not the join
key. Id 0 is the FA placeholder and is not a club.

Sleeper seasons have no pro schedule dump. Player and gamecenter labels join
players.nfl_team through this crosswalk, so they only appear on weeks the
table actually covers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..dumps import DumpError, load_json
from ..paths import data_dir
from ..players import load_dst_map


@dataclass(frozen=True)
class NflClub:
    espn_pro_team_id: int
    abbr: str
    location: str
    name: str


@dataclass(frozen=True)
class NflTeamWeek:
    year: int
    week: int
    espn_pro_team_id: int
    opponent_espn_pro_team_id: int | None
    is_home: bool | None
    is_bye: bool


def parse_pro_schedule(year: int) -> tuple[list[NflClub], list[NflTeamWeek]]:
    path = data_dir() / "espn" / str(year) / "pro_schedule.json"
    if not path.is_file():
        return [], []
    payload = load_json(path)
    teams = ((payload.get("settings") or {}).get("proTeams") if isinstance(payload, dict) else None)
    if not isinstance(teams, list):
        raise DumpError(f"{path} has no settings.proTeams list")
    crosswalk = load_dst_map()
    clubs: list[NflClub] = []
    weeks: list[NflTeamWeek] = []
    for team in teams:
        if not isinstance(team, dict):
            continue
        team_id = int(team.get("id") or 0)
        if team_id == 0:
            continue
        abbr = crosswalk.get(team_id)
        if not abbr:
            raise DumpError(f"{year} pro team {team_id} ({team.get('abbrev')}) is not in maps/dst.yaml")
        clubs.append(
            NflClub(
                espn_pro_team_id=team_id,
                abbr=abbr,
                location=str(team.get("location") or "").strip(),
                name=str(team.get("name") or "").strip(),
            )
        )
        weeks.extend(_team_weeks(year, team_id, team, crosswalk))
    return clubs, weeks


def _team_weeks(
    year: int,
    team_id: int,
    team: dict[str, Any],
    crosswalk: dict[int, str],
) -> list[NflTeamWeek]:
    rows: list[NflTeamWeek] = []
    seen: set[int] = set()
    games = team.get("proGamesByScoringPeriod") or {}
    if not isinstance(games, dict):
        raise DumpError(f"{year} pro team {team_id} proGamesByScoringPeriod is not an object")
    for week_key, entries in games.items():
        week = int(week_key)
        if not isinstance(entries, list) or not entries:
            continue
        game = entries[0]
        if not isinstance(game, dict):
            continue
        home_id = int(game.get("homeProTeamId") or 0)
        away_id = int(game.get("awayProTeamId") or 0)
        if team_id == home_id:
            opponent_id, is_home = away_id, True
        elif team_id == away_id:
            opponent_id, is_home = home_id, False
        else:
            continue
        if opponent_id not in crosswalk:
            raise DumpError(f"{year} W{week} team {team_id} opponent {opponent_id} is not in maps/dst.yaml")
        rows.append(
            NflTeamWeek(
                year=year,
                week=week,
                espn_pro_team_id=team_id,
                opponent_espn_pro_team_id=opponent_id,
                is_home=is_home,
                is_bye=False,
            )
        )
        seen.add(week)
    bye = int(team.get("byeWeek") or 0)
    if 1 <= bye <= 18 and bye not in seen:
        rows.append(
            NflTeamWeek(
                year=year,
                week=bye,
                espn_pro_team_id=team_id,
                opponent_espn_pro_team_id=None,
                is_home=None,
                is_bye=True,
            )
        )
        seen.add(bye)
    if len(seen) != 18 or sum(1 for row in rows if row.is_bye) != 1:
        raise DumpError(
            f"{year} pro team {team_id} produced {len(rows)} team-weeks "
            f"({sum(1 for row in rows if row.is_bye)} byes); expected 18 with one bye"
        )
    return rows
