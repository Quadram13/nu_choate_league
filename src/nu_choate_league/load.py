from __future__ import annotations

from collections.abc import Iterable

import psycopg

from .build import _compare
from .catalog import load_managers
from .db import apply_schema, connect
from .ingest import ingest_all
from .models import Matchup, SeasonBundle, Transaction
from .players import PlayerIndex


def load_facts(*, year: int | None = None) -> list[str]:
    bundles = ingest_all(year=year)
    if not bundles:
        raise SystemExit("No seasons to load.")
    with connect() as conn:
        apply_schema(conn)
        if year is None:
            _truncate_facts(conn)
        else:
            for bundle in bundles:
                conn.execute("DELETE FROM seasons WHERE year = %s", (bundle.season.year,))
        _upsert_managers(conn)
        _upsert_players(conn, bundles)
        for bundle in bundles:
            _insert_season(conn, bundle)
        conn.commit()
    lines: list[str] = []
    for bundle in bundles:
        lines.extend(_compare(bundle))
        lines.append(f"  loaded {bundle.season.year} into postgres")
    return lines


def _truncate_facts(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        TRUNCATE
            lineup_slots,
            transaction_moves,
            week_scores,
            draft_picks,
            transactions,
            matchups,
            official_records,
            season_playoff_managers,
            season_outcomes,
            team_seasons,
            seasons,
            manager_platform_ids,
            managers,
            players
        RESTART IDENTITY CASCADE
        """
    )


def _executemany(conn: psycopg.Connection, sql: str, rows: list[tuple]) -> None:
    if not rows:
        return
    with conn.cursor() as cur:
        cur.executemany(sql, rows)


def _upsert_managers(conn: psycopg.Connection) -> None:
    managers = load_managers()
    _executemany(
        conn,
        """
        INSERT INTO managers (id, display_name)
        VALUES (%s, %s)
        ON CONFLICT (id) DO UPDATE SET display_name = EXCLUDED.display_name
        """,
        [(manager.id, manager.display_name) for manager in managers],
    )
    conn.execute("DELETE FROM manager_platform_ids")
    rows: list[tuple[str, str, str]] = []
    for manager in managers:
        for espn_id in manager.espn_member_ids:
            rows.append((manager.id, "espn", espn_id))
        for sleeper_id in manager.sleeper_user_ids:
            rows.append((manager.id, "sleeper", sleeper_id))
    _executemany(
        conn,
        """
        INSERT INTO manager_platform_ids (manager_id, platform, platform_id)
        VALUES (%s, %s, %s)
        """,
        rows,
    )


def _upsert_players(conn: psycopg.Connection, bundles: Iterable[SeasonBundle]) -> None:
    index = PlayerIndex()
    rows: dict[str, tuple[str, str, str | None, int | None]] = {}
    for bundle in bundles:
        for matchup in bundle.matchups:
            for side in (matchup.home, matchup.away):
                for slot in side.lineup:
                    _remember_player(rows, index, slot.player_id, slot.player_name)
        for pick in bundle.draft_picks:
            _remember_player(rows, index, pick.player_id, pick.player_name)
        for txn in bundle.transactions:
            for move in (*txn.adds, *txn.drops):
                _remember_player(rows, index, move.player_id, move.player_name)
    _executemany(
        conn,
        """
        INSERT INTO players (id, display_name, position, espn_id)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            position = COALESCE(EXCLUDED.position, players.position),
            espn_id = COALESCE(EXCLUDED.espn_id, players.espn_id)
        """,
        list(rows.values()),
    )


def _remember_player(
    rows: dict[str, tuple[str, str, str | None, int | None]],
    index: PlayerIndex,
    player_id: str,
    name: str,
) -> None:
    if player_id in rows:
        return
    player = index.from_sleeper(player_id)
    if player is None:
        rows[player_id] = (player_id, name or player_id, None, None)
        return
    rows[player_id] = (
        player.id,
        player.display_name or name or player.id,
        player.position,
        player.espn_id,
    )


def _insert_season(conn: psycopg.Connection, bundle: SeasonBundle) -> None:
    season = bundle.season
    conn.execute(
        """
        INSERT INTO seasons (year, platform, league_id, name, vs_median, through_week)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            season.year,
            season.platform.value,
            season.league_id,
            season.name,
            season.vs_median,
            bundle.through_week,
        ),
    )
    _executemany(
        conn,
        """
        INSERT INTO team_seasons (year, manager_id, team_name, platform_team_id)
        VALUES (%s, %s, %s, %s)
        """,
        [
            (season.year, team.manager_id, team.team_name, team.platform_team_id)
            for team in bundle.teams
        ],
    )
    _executemany(
        conn,
        """
        INSERT INTO official_records (year, manager_id, wins, losses, ties, points_for)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        [
            (season.year, row.manager_id, row.wins, row.losses, row.ties, row.points_for)
            for row in bundle.official
        ],
    )
    _executemany(
        conn,
        """
        INSERT INTO matchups (
            id, year, week, kind,
            home_manager_id, away_manager_id,
            home_team_name, away_team_name,
            home_platform_team_id, away_platform_team_id,
            home_points, away_points
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [_matchup_row(matchup) for matchup in bundle.matchups],
    )
    _executemany(
        conn,
        """
        INSERT INTO lineup_slots (matchup_id, side, player_id, player_name, slot, points, started)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        _lineup_rows(bundle.matchups),
    )
    _executemany(
        conn,
        """
        INSERT INTO draft_picks (year, overall, round, manager_id, player_id, player_name, keeper)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                pick.year,
                pick.overall,
                pick.round,
                pick.manager_id,
                pick.player_id,
                pick.player_name,
                pick.keeper,
            )
            for pick in bundle.draft_picks
        ],
    )
    _executemany(
        conn,
        """
        INSERT INTO transactions (id, year, week, type, status, at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        [
            (txn.id, txn.year, txn.week, txn.type, txn.status, txn.at)
            for txn in bundle.transactions
        ],
    )
    _executemany(
        conn,
        """
        INSERT INTO transaction_moves (transaction_id, direction, player_id, player_name, manager_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        _move_rows(bundle.transactions),
    )
    _executemany(
        conn,
        """
        INSERT INTO week_scores (year, week, manager_id, points, paired)
        VALUES (%s, %s, %s, %s, %s)
        """,
        [
            (season.year, row.week, row.manager_id, row.points, row.paired)
            for row in bundle.week_scores
        ],
    )
    outcome = bundle.outcome
    if outcome is not None:
        fmt = outcome.playoff_format
        conn.execute(
            """
            INSERT INTO season_outcomes (
                year, champion, runner_up, regular_season_champion, most_points,
                playoff_teams, playoff_start_week
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                season.year,
                outcome.champion,
                outcome.runner_up,
                outcome.regular_season_champion,
                outcome.most_points,
                fmt.teams if fmt else None,
                fmt.start_week if fmt else None,
            ),
        )
        _executemany(
            conn,
            """
            INSERT INTO season_playoff_managers (year, manager_id)
            VALUES (%s, %s)
            """,
            [(season.year, manager_id) for manager_id in outcome.playoff_managers],
        )


def _matchup_row(matchup: Matchup) -> tuple:
    return (
        matchup.id,
        matchup.year,
        matchup.week,
        matchup.kind,
        matchup.home.manager_id,
        matchup.away.manager_id,
        matchup.home.team_name,
        matchup.away.team_name,
        matchup.home.platform_team_id,
        matchup.away.platform_team_id,
        matchup.home.points,
        matchup.away.points,
    )


def _lineup_rows(matchups: Iterable[Matchup]) -> list[tuple]:
    rows: list[tuple] = []
    for matchup in matchups:
        for side_name, side in (("home", matchup.home), ("away", matchup.away)):
            for slot in side.lineup:
                rows.append(
                    (
                        matchup.id,
                        side_name,
                        slot.player_id,
                        slot.player_name,
                        slot.slot,
                        slot.points,
                        slot.started,
                    )
                )
    return rows


def _move_rows(transactions: Iterable[Transaction]) -> list[tuple]:
    rows: list[tuple] = []
    for txn in transactions:
        for move in txn.adds:
            rows.append((txn.id, "add", move.player_id, move.player_name, move.manager_id))
        for move in txn.drops:
            rows.append((txn.id, "drop", move.player_id, move.player_name, move.manager_id))
    return rows
