from __future__ import annotations

from .models import Matchup, TeamSeason


def round_points(value: object) -> float:
    try:
        return round(float(value or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def scored(matchup: Matchup) -> bool:
    return matchup.home.points != 0 or matchup.away.points != 0


def apply_records(
    teams: list[TeamSeason],
    matchups: list[Matchup],
    *,
    through_week: int | None = None,
    kinds: set[str] | None = None,
) -> None:
    count = kinds if kinds is not None else {"regular", "vs_median"}
    by_id = {team.manager_id: team for team in teams}
    for matchup in matchups:
        if through_week is not None and matchup.week > through_week:
            continue
        if matchup.kind not in count or not scored(matchup):
            continue
        home = by_id.get(matchup.home.manager_id or "")
        away = by_id.get(matchup.away.manager_id or "")
        hp = matchup.home.points
        ap = matchup.away.points
        if home:
            if matchup.kind == "regular":
                home.points_for = round_points(home.points_for + hp)
                home.points_against = round_points(home.points_against + ap)
            if hp > ap:
                home.wins += 1
            elif hp < ap:
                home.losses += 1
            else:
                home.ties += 1
        if away:
            if matchup.kind == "regular":
                away.points_for = round_points(away.points_for + ap)
                away.points_against = round_points(away.points_against + hp)
            if ap > hp:
                away.wins += 1
            elif ap < hp:
                away.losses += 1
            else:
                away.ties += 1
    ranked = sorted(
        teams,
        key=lambda team: (
            _win_pct(team),
            team.points_for,
            team.wins,
        ),
        reverse=True,
    )
    for index, team in enumerate(ranked, start=1):
        team.final_rank = index


def _win_pct(team: TeamSeason) -> float:
    games = team.wins + team.losses + team.ties
    if games == 0:
        return 0.0
    return (team.wins + 0.5 * team.ties) / games


def sort_standings(teams: list[TeamSeason]) -> list[TeamSeason]:
    return sorted(teams, key=lambda team: (team.final_rank or 99, team.manager_id))
