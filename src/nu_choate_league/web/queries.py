from __future__ import annotations

from collections import defaultdict
from typing import Any

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

from ..db import database_url
from . import brackets
from .names import flavor_team

SLOT_ORDER = {
    "QB": 0,
    "RB": 1,
    "WR": 2,
    "TE": 3,
    "FLEX": 4,
    "K": 5,
    "DEF": 6,
    "BN": 50,
    "IR": 51,
}

KIND_LABELS = {
    "regular": "Regular season",
    "playoff": "Playoffs",
    "consolation": "Consolation",
}


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url(), row_factory=dict_row)


def fetchall(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())
    except psycopg.OperationalError as exc:
        raise HTTPException(
            status_code=503,
            detail="Cannot reach Postgres. Start Docker Desktop, then `docker compose up -d`.",
        ) from exc
    except psycopg.errors.UndefinedTable as exc:
        raise HTTPException(
            status_code=503,
            detail="Analysis views are missing. Run `uv run nu-choate-league load`.",
        ) from exc


def fetchone(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rows = fetchall(sql, params)
    return rows[0] if rows else None


def list_seasons() -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            s.year,
            s.platform,
            s.vs_median,
            s.name,
            oc.id AS champion_id,
            oc.display_name AS champion,
            ru.display_name AS runner_up,
            rs.display_name AS regular_season_champion,
            mp.display_name AS most_points
        FROM seasons s
        LEFT JOIN season_outcomes o ON o.year = s.year
        LEFT JOIN managers oc ON oc.id = o.champion
        LEFT JOIN managers ru ON ru.id = o.runner_up
        LEFT JOIN managers rs ON rs.id = o.regular_season_champion
        LEFT JOIN managers mp ON mp.id = o.most_points
        ORDER BY s.year DESC
        """
    )


def latest_scored_year() -> int | None:
    row = fetchone(
        """
        SELECT MAX(year) AS year
        FROM v_standings_official
        WHERE wins + losses + ties > 0
        """
    )
    year = row["year"] if row else None
    return int(year) if year is not None else None


def season_row(year: int) -> dict[str, Any] | None:
    return fetchone(
        """
        SELECT
            s.year,
            s.platform,
            s.vs_median,
            s.name,
            oc.id AS champion_id,
            oc.display_name AS champion,
            ru.display_name AS runner_up,
            rs.display_name AS regular_season_champion,
            mp.display_name AS most_points
        FROM seasons s
        LEFT JOIN season_outcomes o ON o.year = s.year
        LEFT JOIN managers oc ON oc.id = o.champion
        LEFT JOIN managers ru ON ru.id = o.runner_up
        LEFT JOIN managers rs ON rs.id = o.regular_season_champion
        LEFT JOIN managers mp ON mp.id = o.most_points
        WHERE s.year = %(year)s
        """,
        {"year": year},
    )


def standings(year: int) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT rank, manager_id, display_name, team_name,
               wins, losses, ties, points_for, win_pct
        FROM v_standings_official
        WHERE year = %(year)s
        ORDER BY rank, manager_id
        """,
        {"year": year},
    )


def season_schedule(year: int) -> dict[str, Any]:
    rows = fetchall(
        """
        SELECT
            m.id,
            m.week,
            m.kind,
            m.home_manager_id,
            m.away_manager_id,
            hm.display_name AS home_name,
            am.display_name AS away_name,
            m.home_team_name,
            m.away_team_name,
            m.home_points,
            m.away_points,
            (hp.manager_id IS NOT NULL) AS home_playoff,
            (ap.manager_id IS NOT NULL) AS away_playoff
        FROM matchups m
        LEFT JOIN managers hm ON hm.id = m.home_manager_id
        LEFT JOIN managers am ON am.id = m.away_manager_id
        LEFT JOIN season_playoff_managers hp
            ON hp.year = m.year AND hp.manager_id = m.home_manager_id
        LEFT JOIN season_playoff_managers ap
            ON ap.year = m.year AND ap.manager_id = m.away_manager_id
        JOIN seasons s ON s.year = m.year
        WHERE m.year = %(year)s
            AND m.kind IN ('regular', 'playoff', 'consolation')
            AND (s.through_week IS NULL OR m.week <= s.through_week)
            AND (m.home_points <> 0 OR m.away_points <> 0)
        ORDER BY m.week, m.kind, m.id
        """,
        {"year": year},
    )
    regular: dict[int, list[dict[str, Any]]] = defaultdict(list)
    postseason: list[dict[str, Any]] = []
    for row in rows:
        week = int(row["week"])
        if row["kind"] == "regular":
            regular[week].append(row)
        else:
            postseason.append(row)
    meta = fetchone(
        """
        SELECT s.platform, o.playoff_start_week
        FROM seasons s
        LEFT JOIN season_outcomes o ON o.year = s.year
        WHERE s.year = %(year)s
        """,
        {"year": year},
    )
    platform = (meta or {}).get("platform")
    start_week = int((meta or {}).get("playoff_start_week") or 15)
    winners_tree = None
    consolation_tree = None
    if platform == "sleeper":
        roster = {
            int(row["platform_team_id"]): {
                "id": row["manager_id"],
                "name": row["display_name"],
                "team": flavor_team(row["display_name"], row["team_name"]),
            }
            for row in fetchall(
                """
                SELECT ts.platform_team_id, ts.manager_id, m.display_name, ts.team_name
                FROM team_seasons ts
                JOIN managers m ON m.id = ts.manager_id
                WHERE ts.year = %(year)s
                """,
                {"year": year},
            )
            if row["platform_team_id"]
        }
        winners_tree = brackets.sleeper_tree(
            brackets.load_sleeper_bracket(year, "winners_bracket.json"),
            roster,
            postseason,
            start_week,
            championship=True,
        )
        consolation_tree = brackets.sleeper_tree(
            brackets.load_sleeper_bracket(year, "losers_bracket.json"),
            roster,
            postseason,
            start_week,
            championship=False,
        )
    else:
        winners_tree = brackets.espn_winners_tree(postseason)
        consolation_tree = brackets.espn_consolation_ladder(postseason)
    return {
        "regular": [(week, regular[week]) for week in regular],
        "weeks": sorted({int(row["week"]) for row in rows}),
        "winners_tree": winners_tree,
        "consolation_tree": consolation_tree,
    }


def week_slate(year: int, week: int) -> dict[str, Any] | None:
    games = _week_games(year, week)
    if not games:
        return None
    packed = [_score_game(game) for game in games]
    return {**_week_nav(year, week), "groups": _group_games(packed)}


def gamecenter(year: int, week: int, matchup_id: str) -> dict[str, Any] | None:
    games = _week_games(year, week)
    row = next((game for game in games if game["id"] == matchup_id), None)
    if row is None:
        return None
    slots = fetchall(
        """
        SELECT matchup_id, manager_id, player_name, slot, started, points
        FROM v_player_weeks
        WHERE matchup_id = %(matchup_id)s
        """,
        {"matchup_id": matchup_id},
    )
    manager_ids = [
        manager_id
        for manager_id in (row["home_manager_id"], row["away_manager_id"])
        if manager_id
    ]
    bench_rows = fetchall(
        """
        SELECT manager_id, started_points, bench_points
        FROM v_bench
        WHERE year = %(year)s AND week = %(week)s
            AND manager_id = ANY(%(manager_ids)s)
        """,
        {"year": year, "week": week, "manager_ids": manager_ids},
    ) if manager_ids else []
    by_side: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for slot in slots:
        by_side[slot["manager_id"]].append(slot)
    bench_by = {item["manager_id"]: item for item in bench_rows}
    siblings = [_score_game(game) for game in games]
    index = next(i for i, game in enumerate(siblings) if game["id"] == matchup_id)
    return {
        **_week_nav(year, week),
        "game": _score_game(row, by_side=by_side, bench_by=bench_by),
        "kind_label": KIND_LABELS.get(row["kind"], row["kind"]),
        "siblings": siblings,
        "prev_match": siblings[index - 1] if index > 0 else None,
        "next_match": siblings[index + 1] if index < len(siblings) - 1 else None,
    }


def _week_games(year: int, week: int) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            m.id,
            m.week,
            m.kind,
            m.home_manager_id,
            m.away_manager_id,
            hm.display_name AS home_name,
            am.display_name AS away_name,
            m.home_team_name,
            m.away_team_name,
            m.home_points,
            m.away_points
        FROM matchups m
        LEFT JOIN managers hm ON hm.id = m.home_manager_id
        LEFT JOIN managers am ON am.id = m.away_manager_id
        JOIN seasons s ON s.year = m.year
        WHERE m.year = %(year)s
            AND m.week = %(week)s
            AND m.kind IN ('regular', 'playoff', 'consolation')
            AND (s.through_week IS NULL OR m.week <= s.through_week)
            AND (m.home_points <> 0 OR m.away_points <> 0)
        ORDER BY m.kind, m.id
        """,
        {"year": year, "week": week},
    )


def _week_nav(year: int, week: int) -> dict[str, Any]:
    weeks = scored_weeks(year)
    index = weeks.index(week) if week in weeks else -1
    return {
        "week": week,
        "weeks": weeks,
        "prev_week": weeks[index - 1] if index > 0 else None,
        "next_week": weeks[index + 1] if 0 <= index < len(weeks) - 1 else None,
    }


def _score_game(
    game: dict[str, Any],
    *,
    by_side: dict[str, list[dict[str, Any]]] | None = None,
    bench_by: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    home = _side(
        game["home_manager_id"],
        game["home_name"],
        game["home_team_name"],
        game["home_points"],
        by_side=by_side,
        bench_by=bench_by,
    )
    away = _side(
        game["away_manager_id"],
        game["away_name"],
        game["away_team_name"],
        game["away_points"],
        by_side=by_side,
        bench_by=bench_by,
    )
    winner_id = None
    if home["points"] is not None and away["points"] is not None:
        if home["points"] > away["points"]:
            winner_id = home["id"]
        elif away["points"] > home["points"]:
            winner_id = away["id"]
    return {
        "id": game["id"],
        "kind": game["kind"],
        "home": home,
        "away": away,
        "winner_id": winner_id,
    }


def _side(
    manager_id: str | None,
    name: str | None,
    team_name: str | None,
    points: Any,
    *,
    by_side: dict[str, list[dict[str, Any]]] | None = None,
    bench_by: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    display = (name or "").strip() or (team_name or "").strip() or "Bye"
    packed = {
        "id": manager_id,
        "name": display,
        "team": flavor_team(display, team_name),
        "points": points,
    }
    if by_side is None:
        return packed
    lineup = by_side.get(manager_id, []) if manager_id else []
    starters = [row for row in lineup if row["started"]]
    bench = [row for row in lineup if not row["started"]]
    starters.sort(
        key=lambda row: (
            SLOT_ORDER.get(row["slot"] or "", 40),
            row["slot"] or "",
            -(float(row["points"] or 0)),
        )
    )
    bench.sort(key=lambda row: (-(float(row["points"] or 0)), row["player_name"] or ""))
    totals = bench_by.get(manager_id) if bench_by and manager_id else None
    packed["starters"] = starters
    packed["bench"] = bench
    packed["bench_points"] = (totals or {}).get("bench_points")
    return packed


def _group_games(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for game in games:
        grouped[game["kind"]].append(game)
    return [
        {"kind": kind, "label": KIND_LABELS[kind], "games": grouped[kind]}
        for kind in ("regular", "playoff", "consolation")
        if grouped[kind]
    ]


def scored_weeks(year: int) -> list[int]:
    return [
        int(row["week"])
        for row in fetchall(
            """
            SELECT DISTINCT m.week
            FROM matchups m
            JOIN seasons s ON s.year = m.year
            WHERE m.year = %(year)s
                AND m.kind IN ('regular', 'playoff', 'consolation')
                AND (s.through_week IS NULL OR m.week <= s.through_week)
                AND (m.home_points <> 0 OR m.away_points <> 0)
            ORDER BY m.week
            """,
            {"year": year},
        )
    ]


def career() -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT manager_id, display_name, seasons, wins, losses, ties, points_for,
               win_pct, titles, runner_up, regular_season_titles,
               most_points_titles, playoff_appearances
        FROM v_career
        ORDER BY titles DESC, win_pct DESC NULLS LAST, points_for DESC, manager_id
        """
    )


def career_one(manager_id: str) -> dict[str, Any] | None:
    return fetchone(
        """
        SELECT manager_id, display_name, seasons, wins, losses, ties, points_for,
               win_pct, titles, runner_up, regular_season_titles,
               most_points_titles, playoff_appearances
        FROM v_career
        WHERE manager_id = %(manager_id)s
        """,
        {"manager_id": manager_id},
    )


def finishes(manager_id: str) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT year, rank, team_name, wins, losses, ties, points_for, win_pct
        FROM v_standings_official
        WHERE manager_id = %(manager_id)s
        ORDER BY year
        """,
        {"manager_id": manager_id},
    )


def h2h_for(manager_id: str) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            left_id, left_name, right_id, right_name,
            regular_wins, regular_losses, regular_ties,
            regular_points_for, regular_points_against,
            playoff_wins, playoff_losses, playoff_ties, playoff_games,
            playoff_points_for, playoff_points_against
        FROM v_h2h
        WHERE left_id = %(manager_id)s OR right_id = %(manager_id)s
        ORDER BY regular_games + playoff_games DESC, left_id, right_id
        """,
        {"manager_id": manager_id},
    )
    oriented: list[dict[str, Any]] = []
    for row in rows:
        if row["right_id"] == manager_id:
            oriented.append(
                {
                    "opponent_id": row["left_id"],
                    "opponent": row["left_name"],
                    "regular_wins": row["regular_losses"],
                    "regular_losses": row["regular_wins"],
                    "regular_ties": row["regular_ties"],
                    "regular_points_for": row["regular_points_against"],
                    "regular_points_against": row["regular_points_for"],
                    "playoff_wins": row["playoff_losses"],
                    "playoff_losses": row["playoff_wins"],
                    "playoff_ties": row["playoff_ties"],
                    "playoff_games": row["playoff_games"],
                    "playoff_points_for": row["playoff_points_against"],
                    "playoff_points_against": row["playoff_points_for"],
                }
            )
        else:
            oriented.append(
                {
                    "opponent_id": row["right_id"],
                    "opponent": row["right_name"],
                    "regular_wins": row["regular_wins"],
                    "regular_losses": row["regular_losses"],
                    "regular_ties": row["regular_ties"],
                    "regular_points_for": row["regular_points_for"],
                    "regular_points_against": row["regular_points_against"],
                    "playoff_wins": row["playoff_wins"],
                    "playoff_losses": row["playoff_losses"],
                    "playoff_ties": row["playoff_ties"],
                    "playoff_games": row["playoff_games"],
                    "playoff_points_for": row["playoff_points_for"],
                    "playoff_points_against": row["playoff_points_against"],
                }
            )
    return oriented


def high_weeks(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT w.year, w.week, w.manager_id, w.display_name, w.points
        FROM v_record_weeks w
        WHERE EXISTS (
            SELECT 1
            FROM matchups m
            WHERE m.year = w.year AND m.week = w.week
                AND m.kind = 'regular'
                AND (m.home_points <> 0 OR m.away_points <> 0)
        )
        ORDER BY w.points DESC, w.year, w.week, w.manager_id
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def low_weeks(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT w.year, w.week, w.manager_id, w.display_name, w.points
        FROM v_record_weeks w
        WHERE EXISTS (
            SELECT 1
            FROM matchups m
            WHERE m.year = w.year AND m.week = w.week
                AND m.kind = 'regular'
                AND (m.home_points <> 0 OR m.away_points <> 0)
        )
        ORDER BY w.points ASC, w.year, w.week, w.manager_id
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def blowouts(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT matchup_id, year, week, manager_id, manager_name, opponent_id, opponent_name,
               points, opp_points, abs_margin, result, blowout_rank
        FROM v_record_matchups
        WHERE blowout_rank <= %(limit)s
        ORDER BY blowout_rank, year, week
        """,
        {"limit": limit},
    )


def closest_games(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT matchup_id, year, week, manager_id, manager_name, opponent_id, opponent_name,
               points, opp_points, abs_margin, result, closest_rank
        FROM v_record_matchups
        WHERE closest_rank <= %(limit)s
        ORDER BY closest_rank, year, week
        """,
        {"limit": limit},
    )


def longest_streaks(result: str, limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT manager_id, display_name, length, start_year, start_week,
               end_year, end_week, is_current
        FROM v_streaks
        WHERE result = %(result)s
        ORDER BY length DESC, start_year, start_week, manager_id
        LIMIT %(limit)s
        """,
        {"result": result, "limit": limit},
    )


def current_streaks() -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT manager_id, display_name, result, length, start_year, start_week,
               end_year, end_week
        FROM v_streaks
        WHERE is_current
        ORDER BY length DESC, display_name
        """
    )
