from __future__ import annotations

import json
import time
from collections.abc import Iterable
from datetime import date

import psycopg

from .build import _compare
from .catalog import load_managers
from .db import apply_schema, connect, refresh_analysis
from .dumps import ESPN_POSITIONS, load_json, season_dir
from .ingest import ingest_all
from .ingest.common import resolve_player
from .ingest.espn import espn_id_backfill_pairs
from .ingest.schedule import parse_pro_schedule
from .ingest.score import (
    COUNTING_STAT_FIELDS,
    counting_stat_values,
    counting_stat_values_espn,
    espn_point_buckets,
    score_sleeper_buckets,
)
from .ingest.sleeper_context import SLEEPER_CONTEXT_COLUMNS, context_insert_tuple, sleeper_context_rows
from .models import EspnMarket, Matchup, Platform, Season, SeasonBundle, Transaction
from .players import PlayerIndex, catalog_identity, sleeper_catalog_as_of


def _progress(message: str) -> None:
    print(f"load: {message}", flush=True)


def load_facts(*, year: int | None = None) -> list[str]:
    started = time.perf_counter()
    bundles = ingest_all(year=year, progress=_progress)
    if not bundles:
        raise SystemExit("No seasons to load.")
    with connect() as conn:
        apply_schema(conn, refresh=False, progress=_progress)
        if year is None:
            _progress("truncate facts")
            _truncate_facts(conn)
        else:
            for bundle in bundles:
                _progress(f"delete {bundle.season.year}")
                conn.execute("DELETE FROM seasons WHERE year = %s", (bundle.season.year,))
        _progress("upsert managers and players")
        _upsert_managers(conn)
        _upsert_players(conn, bundles)
        _backfill_espn_ids(conn, bundles)
        for bundle in bundles:
            step = time.perf_counter()
            _insert_season(conn, bundle)
            _insert_stat_lines(conn, bundle)
            _insert_espn_market(conn, bundle)
            _insert_roster_extras(conn, bundle)
            _insert_nfl_schedule(conn, bundle)
            _insert_sleeper_context(conn, bundle)
            _progress(f"insert {bundle.season.year} ({time.perf_counter() - step:.1f}s)")
        refresh_analysis(conn, progress=_progress)
        conn.commit()
    _progress(f"done ({time.perf_counter() - started:.1f}s)")
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
            player_week_scores,
            player_week_stat_lines,
            player_week_counting_stats,
            player_week_sleeper_context,
            draft_picks,
            espn_market,
            nfl_team_weeks,
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


_PLAYER_ROW_WIDTH = 20


def _upsert_players(conn: psycopg.Connection, bundles: Iterable[SeasonBundle]) -> None:
    index = PlayerIndex()
    as_of = sleeper_catalog_as_of()
    rows: dict[str, tuple] = {}
    for bundle in bundles:
        for matchup in bundle.matchups:
            for side in (matchup.home, matchup.away):
                for slot in side.lineup:
                    _remember_player(rows, index, slot.player_id, slot.player_name, as_of)
        for pick in bundle.draft_picks:
            _remember_player(rows, index, pick.player_id, pick.player_name, as_of)
        for txn in bundle.transactions:
            for move in (*txn.adds, *txn.drops):
                _remember_player(rows, index, move.player_id, move.player_name, as_of)
        for row in bundle.player_weeks:
            _remember_player(rows, index, row.player_id, row.player_name, as_of)
    bad = next((row for row in rows.values() if len(row) != _PLAYER_ROW_WIDTH), None)
    if bad is not None:
        raise RuntimeError(f"player row has {len(bad)} values, expected {_PLAYER_ROW_WIDTH}")
    _executemany(
        conn,
        """
        INSERT INTO players (
            id, display_name, position, espn_id, nfl_team, college, years_exp, jersey_number,
            birth_date, height_in, weight_lb, high_school, rookie_year,
            catalog_as_of, nfl_status, injury_status, injury_body_part, injury_notes,
            depth_chart_position, depth_chart_order
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            position = COALESCE(EXCLUDED.position, players.position),
            espn_id = COALESCE(EXCLUDED.espn_id, players.espn_id),
            nfl_team = COALESCE(EXCLUDED.nfl_team, players.nfl_team),
            college = COALESCE(EXCLUDED.college, players.college),
            years_exp = COALESCE(EXCLUDED.years_exp, players.years_exp),
            jersey_number = COALESCE(EXCLUDED.jersey_number, players.jersey_number),
            birth_date = COALESCE(EXCLUDED.birth_date, players.birth_date),
            height_in = COALESCE(EXCLUDED.height_in, players.height_in),
            weight_lb = COALESCE(EXCLUDED.weight_lb, players.weight_lb),
            high_school = COALESCE(EXCLUDED.high_school, players.high_school),
            rookie_year = COALESCE(EXCLUDED.rookie_year, players.rookie_year),
            -- Snapshot columns replace, including null. A healed player must not
            -- keep last load's injury. Static facts above still coalesce.
            catalog_as_of = EXCLUDED.catalog_as_of,
            nfl_status = EXCLUDED.nfl_status,
            injury_status = EXCLUDED.injury_status,
            injury_body_part = EXCLUDED.injury_body_part,
            injury_notes = EXCLUDED.injury_notes,
            depth_chart_position = EXCLUDED.depth_chart_position,
            depth_chart_order = EXCLUDED.depth_chart_order
        """,
        list(rows.values()),
    )


def _remember_player(
    rows: dict[str, tuple],
    index: PlayerIndex,
    player_id: str,
    name: str,
    as_of: date,
) -> None:
    if player_id in rows:
        return
    player = index.from_sleeper(player_id)
    record = index.catalog.get(player_id) or {}
    if player is None:
        rows[player_id] = (player_id, name or player_id, *([None] * (_PLAYER_ROW_WIDTH - 2)))
        return
    number = record.get("number")
    years = record.get("years_exp")
    try:
        years_exp = int(years) if years is not None else None
    except (TypeError, ValueError):
        years_exp = None
    identity = catalog_identity(record)
    rows[player_id] = (
        player.id,
        player.display_name or name or player.id,
        player.position,
        player.espn_id,
        str(record.get("team") or "") or None,
        str(record.get("college") or "") or None,
        years_exp,
        str(number) if number is not None and str(number) != "" else None,
        identity.birth_date,
        identity.height_in,
        identity.weight_lb,
        identity.high_school,
        identity.rookie_year,
        as_of,
        identity.nfl_status,
        identity.injury_status,
        identity.injury_body_part,
        identity.injury_notes,
        identity.depth_chart_position,
        identity.depth_chart_order,
    )


def _insert_season(conn: psycopg.Connection, bundle: SeasonBundle) -> None:
    season = bundle.season
    conn.execute(
        """
        INSERT INTO seasons (
            year, platform, league_id, name, vs_median, through_week,
            scoring_settings, faab_budget
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        """,
        (
            season.year,
            season.platform.value,
            season.league_id,
            season.name,
            season.vs_median,
            bundle.through_week,
            json.dumps(_scoring_settings(season)),
            season.faab_budget,
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
        INSERT INTO transactions (id, year, week, type, status, at, seq, priority, bid, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                txn.id,
                txn.year,
                txn.week,
                txn.type,
                txn.status,
                txn.at,
                txn.seq,
                txn.priority,
                txn.bid,
                txn.note,
            )
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
    _executemany(
        conn,
        """
        INSERT INTO player_week_scores (
            year, week, player_id, player_name, position, points, rostered, started, manager_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                season.year,
                row.week,
                row.player_id,
                row.player_name,
                row.position,
                row.points,
                row.rostered,
                row.started,
                row.manager_id,
            )
            for row in bundle.player_weeks
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


def _scoring_settings(season) -> dict | list | None:
    path = season_dir(season) / "league.json"
    try:
        league = load_json(path)
    except Exception:
        return None
    if not isinstance(league, dict):
        return None
    if season.platform is Platform.SLEEPER:
        settings = league.get("scoring_settings")
        return settings if isinstance(settings, dict) else None
    settings = (league.get("settings") or {}).get("scoringSettings")
    return settings if settings is not None else None


def _backfill_espn_ids(conn: psycopg.Connection, bundles: Iterable[SeasonBundle]) -> None:
    """Stamp players.espn_id from ESPN cards so market rows join draft picks.

    Catalog espn ids already landed in `_upsert_players`. This only fills
    nulls, and only when the card resolution is unambiguous. `espn:` player
    ids that never matched a Sleeper record get the id embedded in their key.
    """
    rows: list[EspnMarket] = []
    for bundle in bundles:
        rows.extend(bundle.espn_market)
    pairs = espn_id_backfill_pairs(rows)
    _executemany(
        conn,
        """
        UPDATE players AS p
        SET espn_id = %s
        WHERE p.id = %s
          AND p.espn_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM players other
              WHERE other.espn_id = %s AND other.id <> %s
          )
        """,
        [(espn_id, player_id, espn_id, player_id) for espn_id, player_id in pairs],
    )
    conn.execute(
        """
        UPDATE players AS p
        SET espn_id = substring(p.id FROM 6)::integer
        WHERE p.espn_id IS NULL
          AND p.id ~ '^espn:-?[0-9]+$'
          AND NOT EXISTS (
              SELECT 1 FROM players other
              WHERE other.espn_id = substring(p.id FROM 6)::integer
                AND other.id <> p.id
          )
        """
    )
    _progress(f"espn_id backfill candidates {len(pairs)}")


def _insert_espn_market(conn: psycopg.Connection, bundle: SeasonBundle) -> None:
    if not bundle.espn_market:
        return
    season_year = bundle.season.year
    conn.execute("DELETE FROM espn_market WHERE year = %s", (season_year,))
    _executemany(
        conn,
        """
        INSERT INTO espn_market (
            year, espn_id, average_draft_position, percent_owned,
            percent_started, auction_value_average
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (year, espn_id) DO UPDATE SET
            average_draft_position = EXCLUDED.average_draft_position,
            percent_owned = EXCLUDED.percent_owned,
            percent_started = EXCLUDED.percent_started,
            auction_value_average = EXCLUDED.auction_value_average
        """,
        [
            (
                row.year,
                row.espn_id,
                row.average_draft_position,
                row.percent_owned,
                row.percent_started,
                row.auction_value_average,
            )
            for row in bundle.espn_market
        ],
    )
    _progress(f"espn market {season_year}: {len(bundle.espn_market)} rows")


def _insert_stat_lines(conn: psycopg.Connection, bundle: SeasonBundle) -> None:
    season = bundle.season
    players = PlayerIndex()
    if season.platform is Platform.SLEEPER:
        line_rows, count_rows = _sleeper_stat_rows(season, through_week=bundle.through_week, players=players)
    elif season.platform is Platform.ESPN:
        line_rows, count_rows = _espn_stat_rows(season, through_week=bundle.through_week, players=players)
    else:
        return
    _write_stat_rows(conn, line_rows, count_rows)


def _sleeper_stat_rows(
    season: Season,
    *,
    through_week: int | None,
    players: PlayerIndex,
) -> tuple[list[tuple], list[tuple]]:
    folder = season_dir(season)
    league_path = folder / "league.json"
    try:
        league = load_json(league_path)
    except Exception:
        return [], []
    settings = league.get("scoring_settings") if isinstance(league, dict) else None
    if not isinstance(settings, dict):
        return [], []
    weeks = folder / "weeks"
    if not weeks.is_dir():
        return [], []
    # Same gate for point buckets and counting stats: skip all-zero buckets
    # (byes, inactives, and anyone who did not score). Counting columns may
    # still be zero when the points came from a key outside the fan box score.
    line_rows: list[tuple] = []
    count_rows: list[tuple] = []
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
            buckets = score_sleeper_buckets(raw, settings)
            if not any(buckets.values()):
                continue
            meta = players.from_sleeper(str(player_id))
            canonical = meta.id if meta is not None else str(player_id)
            line_rows.append(_line_tuple(season.year, week, canonical, buckets))
            count_rows.append((season.year, week, canonical, *counting_stat_values(raw)))
    return line_rows, count_rows


def _espn_stat_rows(
    season: Season,
    *,
    through_week: int | None,
    players: PlayerIndex,
) -> tuple[list[tuple], list[tuple]]:
    """Boxscore actuals for one ESPN season.

    A row is kept only when applied point buckets are not all zero — the same
    gate as Sleeper, and the same (year, week, player_id) as the stat line.
    Player ids go through PlayerIndex.resolve_espn, the same path as the pool.
    That does not read players.espn_id, so it does not depend on ticket #25's
    load-time backfill. Two ESPN ids that collapse to one canonical id keep
    the line with the larger absolute point total. appliedTotalCeiling is a
    projection and is not stored.
    """
    folder = season_dir(season)
    weeks = folder / "weeks"
    if not weeks.is_dir():
        return [], []
    chosen: dict[tuple[int, int, str], tuple[float, tuple, tuple]] = {}
    for week_dir in sorted(weeks.iterdir()):
        if not week_dir.is_dir():
            continue
        week = int(week_dir.name)
        if through_week is not None and week > through_week:
            continue
        path = week_dir / "boxscore.json"
        if not path.is_file():
            continue
        try:
            payload = load_json(path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for game in payload.get("schedule") or []:
            if not isinstance(game, dict):
                continue
            for side_name in ("home", "away"):
                side = game.get(side_name) or {}
                if not isinstance(side, dict):
                    continue
                roster = side.get("rosterForCurrentScoringPeriod") or {}
                if not isinstance(roster, dict):
                    continue
                entries = roster.get("entries") or []
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    parsed = _espn_roster_actual(entry, week)
                    if parsed is None:
                        continue
                    espn_id, name, position, applied, raw = parsed
                    buckets = espn_point_buckets(applied)
                    if not any(buckets.values()):
                        continue
                    canonical, _display = resolve_player(players, Platform.ESPN, espn_id, name, position)
                    key = (season.year, week, canonical)
                    weight = sum(abs(value) for value in buckets.values())
                    previous = chosen.get(key)
                    if previous is not None and previous[0] >= weight:
                        continue
                    chosen[key] = (
                        weight,
                        _line_tuple(season.year, week, canonical, buckets),
                        (season.year, week, canonical, *counting_stat_values_espn(raw)),
                    )
    line_rows = [row[1] for row in chosen.values()]
    count_rows = [row[2] for row in chosen.values()]
    return line_rows, count_rows


def _espn_roster_actual(
    entry: dict,
    week: int,
) -> tuple[int, str, str | None, dict, dict] | None:
    pool = entry.get("playerPoolEntry") or {}
    player = pool.get("player") if isinstance(pool, dict) else None
    if not isinstance(player, dict):
        player = {}
    espn_id = player.get("id", entry.get("playerId"))
    if not isinstance(espn_id, int):
        return None
    actual = None
    for item in player.get("stats") or []:
        if not isinstance(item, dict):
            continue
        if item.get("statSourceId") != 0 or item.get("statSplitTypeId") != 1:
            continue
        if item.get("scoringPeriodId") != week:
            continue
        actual = item
    if actual is None:
        return None
    applied = actual.get("appliedStats") or {}
    raw = actual.get("stats") or {}
    if not isinstance(applied, dict):
        applied = {}
    if not isinstance(raw, dict):
        raw = {}
    position_id = player.get("defaultPositionId")
    position = ESPN_POSITIONS.get(int(position_id)) if isinstance(position_id, int) else None
    name = str(player.get("fullName") or "")
    return espn_id, name, position, applied, raw


def _line_tuple(year: int, week: int, player_id: str, buckets: dict[str, float]) -> tuple:
    return (
        year,
        week,
        player_id,
        buckets["pass"],
        buckets["rush"],
        buckets["rec"],
        buckets["misc"],
    )


def _write_stat_rows(
    conn: psycopg.Connection,
    line_rows: list[tuple],
    count_rows: list[tuple],
) -> None:
    _executemany(
        conn,
        """
        INSERT INTO player_week_stat_lines (
            year, week, player_id, pass_points, rush_points, rec_points, misc_points
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (year, week, player_id) DO UPDATE SET
            pass_points = EXCLUDED.pass_points,
            rush_points = EXCLUDED.rush_points,
            rec_points = EXCLUDED.rec_points,
            misc_points = EXCLUDED.misc_points
        """,
        line_rows,
    )
    count_columns = [name for name, _key in COUNTING_STAT_FIELDS]
    count_sql = """
        INSERT INTO player_week_counting_stats (
            year, week, player_id, {columns}
        )
        VALUES ({placeholders})
        ON CONFLICT (year, week, player_id) DO UPDATE SET
            {updates}
    """.format(
        columns=", ".join(count_columns),
        placeholders=", ".join("%s" for _ in range(3 + len(count_columns))),
        updates=", ".join(f"{name} = EXCLUDED.{name}" for name in count_columns),
    )
    _executemany(conn, count_sql, count_rows)


def _insert_roster_extras(conn: psycopg.Connection, bundle: SeasonBundle) -> None:
    """Write Sleeper ppts, points-against, waiver slot, and move count.

    The base official_records insert stays wins and fpts. These columns are
    null on ESPN. A Sleeper 0 is written as 0, not left null.
    """
    rows = [
        (
            row.points_against,
            row.ppts,
            row.waiver_position,
            row.total_moves,
            bundle.season.year,
            row.manager_id,
        )
        for row in bundle.official
        if any(
            value is not None
            for value in (row.points_against, row.ppts, row.waiver_position, row.total_moves)
        )
    ]
    _executemany(
        conn,
        """
        UPDATE official_records
        SET points_against = %s,
            ppts = %s,
            waiver_position = %s,
            total_moves = %s
        WHERE year = %s AND manager_id = %s
        """,
        rows,
    )
    if rows:
        _progress(f"roster extras {bundle.season.year}: {len(rows)} managers")


def _insert_nfl_schedule(conn: psycopg.Connection, bundle: SeasonBundle) -> None:
    """ESPN pro schedule for this season. Sleeper years have no dump, so skip."""
    if bundle.season.platform is not Platform.ESPN:
        return
    clubs, weeks = parse_pro_schedule(bundle.season.year)
    if not weeks:
        return
    _executemany(
        conn,
        """
        INSERT INTO nfl_team_crosswalk (espn_pro_team_id, abbr, location, name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (espn_pro_team_id) DO UPDATE SET
            abbr = EXCLUDED.abbr,
            location = EXCLUDED.location,
            name = EXCLUDED.name
        """,
        [(club.espn_pro_team_id, club.abbr, club.location, club.name) for club in clubs],
    )
    conn.execute("DELETE FROM nfl_team_weeks WHERE year = %s", (bundle.season.year,))
    _executemany(
        conn,
        """
        INSERT INTO nfl_team_weeks (
            year, week, espn_pro_team_id, opponent_espn_pro_team_id, is_home, is_bye
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        [
            (
                row.year,
                row.week,
                row.espn_pro_team_id,
                row.opponent_espn_pro_team_id,
                row.is_home,
                row.is_bye,
            )
            for row in weeks
        ],
    )
    _progress(f"nfl schedule {bundle.season.year}: {len(weeks)} team-weeks")


def _insert_sleeper_context(conn: psycopg.Connection, bundle: SeasonBundle) -> None:
    """Sleeper stats.json context. ESPN seasons have no equivalent dump."""
    season = bundle.season
    if season.platform is not Platform.SLEEPER:
        _progress(f"sleeper context {season.year}: none ({season.platform.value} has no stats.json)")
        return
    rows = sleeper_context_rows(
        season,
        through_week=bundle.through_week,
        players=PlayerIndex(),
    )
    columns = list(SLEEPER_CONTEXT_COLUMNS)
    sql = """
        INSERT INTO player_week_sleeper_context (
            year, week, player_id, {columns}
        )
        VALUES ({placeholders})
        ON CONFLICT (year, week, player_id) DO UPDATE SET
            {updates}
    """.format(
        columns=", ".join(columns),
        placeholders=", ".join("%s" for _ in range(3 + len(columns))),
        updates=", ".join(f"{name} = EXCLUDED.{name}" for name in columns),
    )
    _executemany(conn, sql, [context_insert_tuple(row) for row in rows])
    _progress(f"sleeper context {season.year}: {len(rows)} rows")
