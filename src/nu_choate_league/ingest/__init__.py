from __future__ import annotations

from ..catalog import IdentityIndex, load_managers, load_seasons
from ..history import attach_outcomes
from ..models import Platform, Season, SeasonBundle
from ..players import PlayerIndex
from ..records import sort_standings
from .espn import ingest_espn
from .sleeper import ingest_sleeper


def ingest_season(
    season: Season,
    *,
    managers: IdentityIndex | None = None,
    players: PlayerIndex | None = None,
) -> SeasonBundle:
    managers = managers or IdentityIndex(load_managers())
    players = players or PlayerIndex()
    if season.platform is Platform.ESPN:
        teams, matchups, official, draft_picks, transactions, week_scores, through_week = ingest_espn(
            season, managers, players
        )
    else:
        teams, matchups, official, draft_picks, transactions, week_scores, through_week = ingest_sleeper(
            season, managers, players
        )
    return SeasonBundle(
        season=season,
        teams=sort_standings(teams),
        matchups=matchups,
        official=official,
        draft_picks=draft_picks,
        transactions=transactions,
        through_week=through_week,
        week_scores=week_scores,
    )


def ingest_all(*, year: int | None = None) -> list[SeasonBundle]:
    managers = IdentityIndex(load_managers())
    players = PlayerIndex()
    bundles: list[SeasonBundle] = []
    for season in load_seasons():
        if year is not None and season.year != year:
            continue
        bundles.append(ingest_season(season, managers=managers, players=players))
    return attach_outcomes(bundles)
