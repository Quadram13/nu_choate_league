from __future__ import annotations

from collections import defaultdict
from typing import Any

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

from ..db import database_url


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


def matchups_by_week(year: int) -> list[tuple[int, str, list[dict[str, Any]]]]:
    rows = fetchall(
        """
        SELECT
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
            AND (s.through_week IS NULL OR m.week <= s.through_week)
            AND (m.home_points <> 0 OR m.away_points <> 0)
        ORDER BY m.week, m.kind, m.id
        """,
        {"year": year},
    )
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["week"]), row["kind"])].append(row)
    return [(week, kind, grouped[(week, kind)]) for week, kind in grouped]


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
