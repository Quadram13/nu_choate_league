from __future__ import annotations

import statistics

from .catalog import load_managers
from .models import (
    AlternateGame,
    AlternateRound,
    AlternateSeason,
    AlternateSide,
    AlternateUniverse,
    Matchup,
    MatchupSide,
    PlayoffFormat,
    SeasonBundle,
    TeamSeason,
)
from .records import apply_records, round_points, scored, sort_standings


UNIVERSES = (
    ("always_median", "H2H + vs median"),
    ("never_median", "H2H only"),
)


def alternate_season(bundle: SeasonBundle) -> AlternateSeason | None:
    if not any(_played(team) for team in bundle.teams):
        return None
    outcome = bundle.outcome
    result = AlternateSeason(
        year=bundle.season.year,
        official_champion=outcome.champion if outcome else None,
        official_runner_up=outcome.runner_up if outcome else None,
        official_regular_season_champion=outcome.regular_season_champion if outcome else None,
    )
    for universe_id, label in UNIVERSES:
        result.universes.append(_universe(bundle, universe_id, label))
    return result


def format_alternate(alt: AlternateSeason) -> str:
    names = {manager.id: manager.display_name for manager in load_managers()}
    lines = [
        f"{alt.year} official champ { _name(names, alt.official_champion) }  "
        f"RS { _name(names, alt.official_regular_season_champion) }"
    ]
    for universe in alt.universes:
        flag = " = official" if universe.matches_official else ""
        lines.append(f"  {universe.id}{flag}:")
        lines.append(
            f"    RS {_name(names, universe.regular_season_champion)}  "
            f"champ {_name(names, universe.champion)}  "
            f"runner-up {_name(names, universe.runner_up)}"
        )
        for team in universe.teams[:6]:
            seed = f"s{team.playoff_seed}" if team.playoff_seed else "  "
            record = f"{team.wins}-{team.losses}-{team.ties}"
            lines.append(
                f"    {team.final_rank or 0:2} {seed:>2} {_name(names, team.manager_id):20} "
                f"{record:8} {team.points_for:7.2f}"
            )
        for note in universe.notes:
            lines.append(f"    note: {note}")
    return "\n".join(lines) + "\n"


def _universe(bundle: SeasonBundle, universe_id: str, label: str) -> AlternateUniverse:
    with_median = universe_id == "always_median"
    teams = _standings(bundle, with_median=with_median)
    fmt = bundle.outcome.playoff_format if bundle.outcome else None
    field = _playoff_field(teams, fmt)
    for index, team in enumerate(field, start=1):
        team.playoff_seed = index
    playoff_ids = [team.manager_id for team in field]
    notes: list[str] = []
    bracket: list[AlternateRound] = []
    champion = None
    runner_up = None
    if fmt and field and bundle.outcome and bundle.outcome.champion:
        bracket, champion, runner_up, notes = _simulate(field, fmt, bundle)
    rs = teams[0].manager_id if teams else None
    official_records = {(team.manager_id, team.wins, team.losses, team.ties) for team in bundle.teams}
    alt_records = {(team.manager_id, team.wins, team.losses, team.ties) for team in teams}
    matches = official_records == alt_records and champion == (bundle.outcome.champion if bundle.outcome else None)
    return AlternateUniverse(
        id=universe_id,
        label=label,
        teams=sort_standings(teams),
        champion=champion,
        runner_up=runner_up,
        regular_season_champion=rs,
        playoff_managers=playoff_ids,
        bracket=bracket,
        notes=notes,
        matches_official=matches,
    )


def _standings(bundle: SeasonBundle, *, with_median: bool) -> list[TeamSeason]:
    teams = [
        team.model_copy(
            update={
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "points_for": 0.0,
                "points_against": 0.0,
                "playoff_seed": None,
                "final_rank": None,
            }
        )
        for team in bundle.teams
    ]
    matchups = list(bundle.matchups)
    if with_median and not any(matchup.kind == "vs_median" for matchup in matchups):
        matchups.extend(_synthesize_median(matchups, bundle.through_week))
    kinds = {"regular", "vs_median"} if with_median else {"regular"}
    apply_records(teams, matchups, through_week=bundle.through_week, kinds=kinds)
    return sort_standings(teams)


def _synthesize_median(matchups: list[Matchup], through_week: int | None) -> list[Matchup]:
    by_week: dict[int, list[Matchup]] = {}
    for matchup in matchups:
        if matchup.kind != "regular":
            continue
        if through_week is not None and matchup.week > through_week:
            continue
        if not scored(matchup):
            continue
        by_week.setdefault(matchup.week, []).append(matchup)
    extra: list[Matchup] = []
    for week, games in by_week.items():
        sides = [
            side
            for game in games
            for side in (game.home, game.away)
            if side.manager_id
        ]
        if not sides:
            continue
        median = round_points(statistics.median(side.points for side in sides))
        for side in sides:
            extra.append(
                Matchup(
                    id=f"{games[0].year}-w{week:02d}-median-{side.manager_id}",
                    year=games[0].year,
                    week=week,
                    kind="vs_median",
                    home=MatchupSide(
                        manager_id=side.manager_id,
                        team_name=side.team_name,
                        platform_team_id=side.platform_team_id,
                        points=side.points,
                        lineup=[],
                    ),
                    away=MatchupSide(team_name="Median", points=median, lineup=[]),
                )
            )
    return extra


def _playoff_field(teams: list[TeamSeason], fmt: PlayoffFormat | None) -> list[TeamSeason]:
    if fmt is None or fmt.teams <= 0:
        return []
    return [team for team in sort_standings(teams) if _played(team)][: fmt.teams]


def _simulate(
    field: list[TeamSeason],
    fmt: PlayoffFormat,
    bundle: SeasonBundle,
) -> tuple[list[AlternateRound], str | None, str | None, list[str]]:
    scores = {(row.week, row.manager_id): row.points for row in bundle.week_scores}
    by_seed = {index: team for index, team in enumerate(field, start=1)}
    notes: list[str] = []
    rounds: list[AlternateRound] = []
    names = [row.name for row in fmt.rounds]
    if names == ["semifinal", "championship"] and len(field) >= 4:
        semi_week = fmt.rounds[0].week
        final_week = fmt.rounds[1].week
        semi, notes = _games(
            [(by_seed[1], by_seed[4]), (by_seed[2], by_seed[3])],
            semi_week,
            scores,
            notes,
        )
        rounds.append(AlternateRound(name="semifinal", week=semi_week, games=semi))
        winners = [_winner_team(game, field) for game in semi]
        if any(team is None for team in winners) or len(winners) < 2:
            return rounds, None, None, notes
        final, notes = _games([(winners[0], winners[1])], final_week, scores, notes)
        rounds.append(AlternateRound(name="championship", week=final_week, games=final))
        return rounds, *_finalists(final, notes)
    if names == ["wildcard", "semifinal", "championship"] and len(field) >= 6:
        wc_week, semi_week, final_week = (row.week for row in fmt.rounds)
        byes = [by_seed[1].manager_id, by_seed[2].manager_id]
        wc, notes = _games(
            [(by_seed[3], by_seed[6]), (by_seed[4], by_seed[5])],
            wc_week,
            scores,
            notes,
        )
        rounds.append(AlternateRound(name="wildcard", week=wc_week, byes=byes, games=wc))
        w36 = _winner_team(wc[0], field) if wc else None
        w45 = _winner_team(wc[1], field) if len(wc) > 1 else None
        if w36 is None or w45 is None:
            return rounds, None, None, notes
        semi, notes = _games(
            [(by_seed[1], w45), (by_seed[2], w36)],
            semi_week,
            scores,
            notes,
        )
        rounds.append(AlternateRound(name="semifinal", week=semi_week, games=semi))
        winners = [_winner_team(game, field) for game in semi]
        if any(team is None for team in winners) or len(winners) < 2:
            return rounds, None, None, notes
        final, notes = _games([(winners[0], winners[1])], final_week, scores, notes)
        rounds.append(AlternateRound(name="championship", week=final_week, games=final))
        return rounds, *_finalists(final, notes)
    notes.append(f"unsupported playoff shape {names} with {len(field)} teams")
    return rounds, None, None, notes


def _games(
    pairs: list[tuple[TeamSeason, TeamSeason]],
    week: int,
    scores: dict[tuple[int, str], float],
    notes: list[str],
) -> tuple[list[AlternateGame], list[str]]:
    games: list[AlternateGame] = []
    for home, away in pairs:
        home_seed = home.playoff_seed or 0
        away_seed = away.playoff_seed or 0
        if home_seed > away_seed:
            home, away = away, home
            home_seed, away_seed = away_seed, home_seed
        hp = scores.get((week, home.manager_id))
        ap = scores.get((week, away.manager_id))
        if hp is None or ap is None:
            notes.append(
                f"missing week {week} score for {home.manager_id if hp is None else away.manager_id}"
            )
            games.append(
                AlternateGame(
                    home=AlternateSide(manager_id=home.manager_id, seed=home_seed, points=hp or 0.0),
                    away=AlternateSide(manager_id=away.manager_id, seed=away_seed, points=ap or 0.0),
                )
            )
            continue
        winner = home.manager_id if hp > ap else away.manager_id if ap > hp else None
        tiebreak = None
        if winner is None:
            winner = home.manager_id if home_seed <= away_seed else away.manager_id
            tiebreak = "higher_seed"
        games.append(
            AlternateGame(
                home=AlternateSide(manager_id=home.manager_id, seed=home_seed, points=hp),
                away=AlternateSide(manager_id=away.manager_id, seed=away_seed, points=ap),
                winner=winner,
                tiebreak=tiebreak,
            )
        )
    return games, notes


def _winner_team(game: AlternateGame, field: list[TeamSeason]) -> TeamSeason | None:
    if not game.winner:
        return None
    for team in field:
        if team.manager_id == game.winner:
            return team
    return None


def _finalists(
    games: list[AlternateGame], notes: list[str]
) -> tuple[str | None, str | None, list[str]]:
    if not games or not games[0].winner:
        return None, None, notes
    game = games[0]
    loser = game.away.manager_id if game.winner == game.home.manager_id else game.home.manager_id
    return game.winner, loser, notes


def _played(team: TeamSeason) -> bool:
    return team.wins + team.losses + team.ties > 0 or team.points_for > 0


def _name(names: dict[str, str], manager_id: str | None) -> str:
    if not manager_id:
        return "-"
    return names.get(manager_id, manager_id)
