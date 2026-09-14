from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

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

FAAB_START_YEAR = 2026
LEAGUE_TZ = ZoneInfo("America/New_York")

TRADE_EVEN_GAP = 15
TRADE_SWING_GAP = 50
TRADE_FLEECE_LOSER = 15
TRADE_LABELS = {
    "even": "even",
    "win": "win",
    "big-win": "big win",
    "fleece": "fleece",
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
            s.through_week,
            oc.id AS champion_id,
            oc.display_name AS champion,
            ru.id AS runner_up_id,
            ru.display_name AS runner_up,
            rs.id AS regular_season_champion_id,
            rs.display_name AS regular_season_champion,
            mp.id AS most_points_id,
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
    rows = fetchall(
        """
        SELECT
            o.rank,
            o.manager_id,
            o.display_name,
            o.team_name,
            o.wins,
            o.losses,
            o.ties,
            o.points_for,
            o.win_pct,
            h.wins AS h2h_wins,
            h.losses AS h2h_losses,
            h.ties AS h2h_ties,
            h.win_pct AS h2h_win_pct,
            h.points_against,
            med.wins AS median_wins,
            med.losses AS median_losses,
            med.ties AS median_ties,
            med.win_pct AS median_win_pct,
            ap.wins AS all_play_wins,
            ap.losses AS all_play_losses,
            ap.ties AS all_play_ties,
            ap.win_pct AS all_play_win_pct
        FROM v_standings_official o
        LEFT JOIN v_standings_h2h h
            ON h.year = o.year AND h.manager_id = o.manager_id
        LEFT JOIN (
            SELECT
                year,
                manager_id,
                count(*) FILTER (WHERE result = 'win') AS wins,
                count(*) FILTER (WHERE result = 'loss') AS losses,
                count(*) FILTER (WHERE result = 'tie') AS ties,
                CASE
                    WHEN count(*) = 0 THEN NULL
                    ELSE (
                        count(*) FILTER (WHERE result = 'win')
                        + 0.5 * count(*) FILTER (WHERE result = 'tie')
                    ) / count(*)
                END AS win_pct
            FROM v_games
            WHERE kind = 'vs_median'
            GROUP BY year, manager_id
        ) med ON med.year = o.year AND med.manager_id = o.manager_id
        LEFT JOIN v_all_play_season ap
            ON ap.year = o.year AND ap.manager_id = o.manager_id
        WHERE o.year = %(year)s
        ORDER BY o.rank, o.manager_id
        """,
        {"year": year},
    )
    for row in rows:
        row["record"] = _record(int(row["wins"] or 0), int(row["losses"] or 0), int(row["ties"] or 0))
        row["h2h"] = _maybe_record(row["h2h_wins"], row["h2h_losses"], row["h2h_ties"])
        row["median"] = _maybe_record(row["median_wins"], row["median_losses"], row["median_ties"])
        row["all_play"] = _maybe_record(
            row["all_play_wins"], row["all_play_losses"], row["all_play_ties"]
        )
    return rows


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


def season_page(year: int) -> dict[str, Any] | None:
    current = season_row(year)
    if current is None:
        return None
    table = standings(year)
    through = current.get("through_week")
    draft = _season_draft(year)
    lineups = _season_lineups(year)
    return {
        "current": current,
        "seasons": list_seasons(),
        "standings": table,
        "teams": len(table),
        "now_week": int(through) if through else None,
        "schedule": season_schedule(year),
        "universes": _season_universes(year),
        "notables": _season_notables(year),
        "trades": _season_trades(year),
        "wire": _season_wire(year),
        "draft": draft,
        "lineups": lineups,
        "scoring": _season_scoring(year),
    }


def _season_scoring(year: int) -> dict[str, Any] | None:
    rows = fetchall(
        """
        SELECT
            w.week,
            min(w.points) AS low,
            max(w.points) AS high,
            avg(w.points) AS avg,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY w.points) AS median
        FROM week_scores w
        JOIN seasons s ON s.year = w.year
        WHERE w.year = %(year)s
            AND w.paired
            AND (s.through_week IS NULL OR w.week <= s.through_week)
            AND EXISTS (
                SELECT 1
                FROM matchups m
                WHERE m.year = w.year
                    AND m.week = w.week
                    AND m.kind = 'regular'
                    AND (m.home_points <> 0 OR m.away_points <> 0)
            )
        GROUP BY w.week
        ORDER BY w.week
        """,
        {"year": year},
    )
    if not rows:
        return None
    weeks = [int(row["week"]) for row in rows]
    series = {
        "high": [float(row["high"] or 0) for row in rows],
        "avg": [float(row["avg"] or 0) for row in rows],
        "median": [float(row["median"] or 0) for row in rows],
        "low": [float(row["low"] or 0) for row in rows],
    }
    y_min = min(series["low"])
    y_max = max(series["high"])
    pad = (y_max - y_min) * 0.12 if y_max > y_min else 1
    y_min -= pad
    y_max += pad
    y_span = y_max - y_min or 1
    w_min, w_max = min(weeks), max(weeks)
    w_span = w_max - w_min or 1
    width, height = 720, 168
    left, right, top, bottom = 36, 10, 8, 22
    plot_w = width - left - right
    plot_h = height - top - bottom

    def sx(week: int) -> float:
        return left + (week - w_min) / w_span * plot_w

    def sy(value: float) -> float:
        return top + (1 - (value - y_min) / y_span) * plot_h

    def pack(values: list[float]) -> list[dict[str, Any]]:
        return [
            {"week": week, "value": value, "x": sx(week), "y": sy(value)}
            for week, value in zip(weeks, values, strict=True)
        ]

    packed = {name: pack(values) for name, values in series.items()}

    def path(points: list[dict[str, Any]]) -> str:
        return "M " + " L ".join(f"{pt['x']:.1f},{pt['y']:.1f}" for pt in points)

    highs, lows = packed["high"], packed["low"]
    band = (
        "M "
        + " L ".join(f"{pt['x']:.1f},{pt['y']:.1f}" for pt in highs)
        + " L "
        + " L ".join(f"{pt['x']:.1f},{pt['y']:.1f}" for pt in reversed(lows))
        + " Z"
    )
    y_ticks = [y_min + y_span * i / 2 for i in (0, 1, 2)]
    return {
        "width": width,
        "height": height,
        "left": left,
        "top": top,
        "plot_w": plot_w,
        "plot_h": plot_h,
        "band": band,
        "paths": {name: path(points) for name, points in packed.items()},
        "points": packed,
        "x_ticks": [{"week": week, "x": sx(week)} for week in weeks],
        "y_ticks": [{"value": tick, "y": sy(tick)} for tick in y_ticks],
    }


def _season_universes(year: int) -> dict[str, Any] | None:
    packed = next((row for row in universe_titles() if row["year"] == year), None)
    if packed is None:
        return None
    if not packed.get("official_champ") and not packed.get("h2h_champ") and not packed.get("median_champ"):
        return None
    return packed


def _season_notables(year: int) -> dict[str, Any]:
    high = _season_extreme_week(year, high=True)
    low = _season_extreme_week(year, high=False)
    blowout = _season_margin_game(year, closest=False)
    closest = _season_margin_game(year, closest=True)
    _stamp_alltime(
        high,
        high_weeks(),
        "/records#high",
        "highest",
        lambda notable, row: (
            int(row["year"]) == int(notable["year"])
            and int(row["week"]) == int(notable["week"])
            and row["manager_id"] == notable.get("scorer_id")
        ),
    )
    _stamp_alltime(
        low,
        low_weeks(),
        "/records#low",
        "lowest",
        lambda notable, row: (
            int(row["year"]) == int(notable["year"])
            and int(row["week"]) == int(notable["week"])
            and row["manager_id"] == notable.get("scorer_id")
        ),
    )
    _stamp_alltime(
        blowout,
        blowouts(),
        "/records#blowouts",
        "biggest",
        lambda notable, row: row["matchup_id"] == notable.get("id"),
    )
    _stamp_alltime(
        closest,
        closest_games(),
        "/records#closest",
        "closest",
        lambda notable, row: row["matchup_id"] == notable.get("id"),
    )
    return {
        "high": high,
        "low": low,
        "blowout": blowout,
        "closest": closest,
        "lucky": _season_luck_flag(year, lucky=True),
        "unlucky": _season_luck_flag(year, lucky=False),
    }


def _stamp_alltime(
    notable: dict[str, Any] | None,
    board: list[dict[str, Any]],
    href: str,
    kind: str,
    same,
) -> None:
    if notable is None:
        return
    for index, row in enumerate(board, 1):
        if same(notable, row):
            notable["alltime_rank"] = index
            notable["alltime_label"] = f"{_ordinal(index)}-{kind}"
            notable["records_href"] = href
            return


def _season_extreme_week(year: int, *, high: bool) -> dict[str, Any] | None:
    row = fetchone(
        f"""
        SELECT w.year, w.week, w.manager_id, w.display_name, w.points
        FROM v_record_weeks w
        WHERE w.year = %(year)s
            AND w.paired
            AND EXISTS (
                SELECT 1
                FROM matchups m
                WHERE m.year = w.year AND m.week = w.week
                    AND m.kind = 'regular'
                    AND (m.home_points <> 0 OR m.away_points <> 0)
            )
        ORDER BY w.points {"DESC" if high else "ASC"}, w.week, w.manager_id
        LIMIT 1
        """,
        {"year": year},
    )
    if row is None:
        return None
    game = _regular_game(year, int(row["week"]), row["manager_id"])
    if game is None:
        return None
    packed = _score_game(game)
    packed["label"] = "Highest week" if high else "Lowest week"
    packed["year"] = year
    packed["week"] = int(row["week"])
    packed["scorer_id"] = row["manager_id"]
    return packed


def _season_margin_game(year: int, *, closest: bool) -> dict[str, Any] | None:
    row = fetchone(
        f"""
        SELECT matchup_id, year, week, manager_id, opponent_id
        FROM v_record_matchups
        WHERE year = %(year)s
        ORDER BY abs_margin {"ASC" if closest else "DESC"}, week, matchup_id
        LIMIT 1
        """,
        {"year": year},
    )
    if row is None:
        return None
    game = _game_by_id(row["matchup_id"])
    if game is None:
        return None
    packed = _score_game(game)
    packed["label"] = "Closest" if closest else "Blowout"
    packed["year"] = year
    packed["week"] = int(row["week"])
    return packed


def _season_luck_flag(year: int, *, lucky: bool) -> dict[str, Any] | None:
    row = fetchone(
        f"""
        SELECT
            year, week, matchup_id, manager_id, display_name,
            opponent_id, opponent_name, points, opp_points, pf_rank, teams
        FROM v_luck_weeks
        WHERE year = %(year)s
            AND {"lucky_win" if lucky else "unlucky_loss"}
        ORDER BY pf_rank {"DESC" if lucky else "ASC"}, week, display_name
        LIMIT 1
        """,
        {"year": year},
    )
    if row is None:
        return None
    row["flag"] = "Luckiest win" if lucky else "Unluckiest loss"
    return row


def _regular_game(year: int, week: int, manager_id: str) -> dict[str, Any] | None:
    return _matchup_row(
        """
        WHERE m.year = %(year)s
            AND m.week = %(week)s
            AND m.kind = 'regular'
            AND (m.home_manager_id = %(manager_id)s OR m.away_manager_id = %(manager_id)s)
        ORDER BY m.id
        LIMIT 1
        """,
        {"year": year, "week": week, "manager_id": manager_id},
    )


def _game_by_id(matchup_id: str) -> dict[str, Any] | None:
    return _matchup_row("WHERE m.id = %(id)s", {"id": matchup_id})


def _matchup_row(where: str, params: dict[str, Any]) -> dict[str, Any] | None:
    return fetchone(
        f"""
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
        {where}
        """,
        params,
    )


def _season_trades(year: int) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            transaction_id, year, week, left_id, left_name, left_received, left_vorp,
            right_id, right_name, right_received, right_vorp,
            vorp_gap, winner_id
        FROM v_trade_grades
        WHERE year = %(year)s
        ORDER BY week, vorp_gap DESC, left_id
        """,
        {"year": year},
    )
    for row in rows:
        row["verdict"] = _trade_verdict(row.get("left_vorp"), row.get("right_vorp"))
        row["home"], row["away"] = _trade_card_sides(row)
    _attach_trade_card_players(rows)
    return rows


def _trade_verdict(left_vorp: Any, right_vorp: Any) -> dict[str, Any]:
    left = float(left_vorp or 0)
    right = float(right_vorp or 0)
    gap = round(abs(left - right), 1)
    loser = min(left, right)
    if gap < TRADE_EVEN_GAP:
        kind = "even"
    elif gap >= TRADE_SWING_GAP and loser < TRADE_FLEECE_LOSER:
        kind = "fleece"
    elif gap >= TRADE_SWING_GAP:
        kind = "big-win"
    else:
        kind = "win"
    return {"kind": kind, "label": TRADE_LABELS[kind], "gap": gap}


def _trade_card_sides(row: dict[str, Any], *, winner_first: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    left = {
        "id": row["left_id"],
        "name": row["left_name"],
        "vorp": row["left_vorp"],
        "received": row.get("left_received"),
    }
    right = {
        "id": row["right_id"],
        "name": row["right_name"],
        "vorp": row["right_vorp"],
        "received": row.get("right_received"),
    }
    if winner_first and row.get("winner_id") == row["right_id"]:
        return right, left
    return left, right


def _attach_trade_card_players(rows: list[dict[str, Any]]) -> None:
    ids = [row["transaction_id"] for row in rows]
    if not ids:
        return
    assets = fetchall(
        """
        SELECT transaction_id, to_manager_id, player_id, player_name
        FROM v_trade_assets
        WHERE transaction_id = ANY(%(ids)s)
        ORDER BY ros_vorp DESC NULLS LAST, player_name
        """,
        {"ids": ids},
    )
    by: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for item in assets:
        by[item["transaction_id"]][item["to_manager_id"]].append(
            {
                "player_id": item["player_id"],
                "player_name": item["player_name"],
            }
        )
    for row in rows:
        packed = by.get(row["transaction_id"], {})
        row["home"]["players"] = packed.get(row["home"]["id"], [])
        row["away"]["players"] = packed.get(row["away"]["id"], [])


def trade_page(year: int, transaction_id: str) -> dict[str, Any] | None:
    trades = _season_trades(year)
    idx = next((i for i, row in enumerate(trades) if row["transaction_id"] == transaction_id), None)
    if idx is None:
        return None
    row = trades[idx]
    onward = _trade_onward(transaction_id)
    asset_ids = [transaction_id, *{item["next_id"] for item in onward}]
    all_assets = fetchall(
        """
        SELECT
            transaction_id, player_id, player_name, position,
            from_manager_id, from_manager_name,
            to_manager_id, to_manager_name,
            ros_starter, ros_starts, ros_vorp, tenure_starter, tenure_vorp
        FROM v_trade_assets
        WHERE transaction_id = ANY(%(ids)s)
        ORDER BY ros_vorp DESC NULLS LAST, player_name
        """,
        {"ids": asset_ids},
    )
    assets = [item for item in all_assets if item["transaction_id"] == transaction_id]
    teams = {
        item["manager_id"]: flavor_team(item["display_name"], item["team_name"])
        for item in fetchall(
            """
            SELECT ts.manager_id, ts.team_name, m.display_name
            FROM team_seasons ts
            JOIN managers m ON m.id = ts.manager_id
            WHERE ts.year = %(year)s
                AND ts.manager_id IN (%(left)s, %(right)s)
            """,
            {"year": year, "left": row["left_id"], "right": row["right_id"]},
        )
    }
    left = _trade_side(row, "left", assets, teams)
    right = _trade_side(row, "right", assets, teams)
    week_nums = [
        int(item["week"])
        for item in fetchall(
            """
            SELECT DISTINCT week
            FROM player_week_scores
            WHERE year = %(year)s AND week >= %(week)s
            ORDER BY week
            """,
            {"year": year, "week": row["week"]},
        )
    ]
    player_ids = [asset["player_id"] for asset in assets if asset["player_id"]]
    scored: list[dict[str, Any]] = []
    if player_ids:
        scored = fetchall(
            """
            SELECT player_id, manager_id, week, points, started, rostered
            FROM player_week_scores
            WHERE year = %(year)s
                AND week >= %(week)s
                AND player_id = ANY(%(ids)s)
            """,
            {"year": year, "week": row["week"], "ids": player_ids},
        )
    by_player: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for item in scored:
        by_player[item["player_id"]][int(item["week"])] = item
    for side in (left, right):
        for player in side["players"]:
            cells = []
            weeks_for = by_player.get(player["player_id"] or "", {})
            for week in week_nums:
                cell = weeks_for.get(week)
                if cell is None or cell["manager_id"] != side["id"]:
                    cells.append(None)
                else:
                    cells.append(
                        {
                            "points": cell["points"],
                            "started": cell["started"],
                            "rostered": cell["rostered"],
                        }
                    )
            player["weeks"] = cells
    flips = _attach_trade_flips(left, right, onward, all_assets)
    return {
        "id": transaction_id,
        "year": year,
        "week": int(row["week"]),
        "left": left,
        "right": right,
        "winner_id": row["winner_id"],
        "verdict": row["verdict"],
        "flips": flips,
        "weeks": week_nums,
        "prev": _trade_brief(trades[idx - 1]) if idx else None,
        "next": _trade_brief(trades[idx + 1]) if idx + 1 < len(trades) else None,
    }


def _trade_side(
    row: dict[str, Any],
    face: str,
    assets: list[dict[str, Any]],
    teams: dict[str, str | None],
) -> dict[str, Any]:
    manager_id = row[f"{face}_id"]
    players = [asset for asset in assets if asset["to_manager_id"] == manager_id]
    return {
        "id": manager_id,
        "name": row[f"{face}_name"],
        "team": teams.get(manager_id),
        "vorp": row[f"{face}_vorp"],
        "ros": sum(float(player["ros_starter"] or 0) for player in players),
        "starts": sum(int(player["ros_starts"] or 0) for player in players),
        "players": players,
    }


def _trade_brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["transaction_id"],
        "week": row["week"],
        "label": f"{row['left_name']} vs {row['right_name']}",
    }


def _trade_onward(transaction_id: str) -> list[dict[str, Any]]:
    return fetchall(
        """
        WITH ranked AS (
            SELECT
                a.player_id,
                a.to_manager_id AS holder_id,
                a.to_manager_name AS holder_name,
                n.transaction_id AS next_id,
                n.year AS next_year,
                n.week AS next_week,
                n.to_manager_id AS next_to_id,
                n.to_manager_name AS next_to_name,
                row_number() OVER (
                    PARTITION BY a.player_id
                    ORDER BY n.year, n.week, coalesce(tn.at, 0), n.transaction_id
                ) AS rn
            FROM v_trades a
            JOIN transactions ta ON ta.id = a.transaction_id
            JOIN v_trades n
                ON n.player_id = a.player_id
                AND n.from_manager_id = a.to_manager_id
                AND n.transaction_id <> a.transaction_id
            JOIN transactions tn
                ON tn.id = n.transaction_id AND tn.status = 'complete'
            WHERE a.transaction_id = %(id)s
                AND (n.year, n.week, coalesce(tn.at, 0), n.transaction_id)
                    > (a.year, a.week, coalesce(ta.at, 0), a.transaction_id)
        )
        SELECT
            player_id, holder_id, holder_name, next_id, next_year, next_week,
            next_to_id, next_to_name
        FROM ranked
        WHERE rn = 1
        """,
        {"id": transaction_id},
    )


def _attach_trade_flips(
    left: dict[str, Any],
    right: dict[str, Any],
    onward: list[dict[str, Any]],
    all_assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_player = {item["player_id"]: item for item in onward}
    by_trade: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in all_assets:
        by_trade[item["transaction_id"]].append(item)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for side in (left, right):
        for player in side["players"]:
            nxt = by_player.get(player["player_id"])
            if nxt is None:
                continue
            extra = by_trade.get(nxt["next_id"], [])
            got = [item for item in extra if item["to_manager_id"] == nxt["holder_id"]]
            residual = next(
                (item for item in extra if item["player_id"] == player["player_id"]),
                None,
            )
            after = None if residual is None else residual.get("ros_vorp")
            player["flip"] = {
                "id": nxt["next_id"],
                "year": nxt["next_year"],
                "week": nxt["next_week"],
                "after": after,
            }
            key = (nxt["next_id"], nxt["holder_id"])
            packed = grouped.get(key)
            if packed is None:
                packed = {
                    "id": nxt["next_id"],
                    "year": nxt["next_year"],
                    "week": nxt["next_week"],
                    "holder_id": nxt["holder_id"],
                    "holder_name": nxt["holder_name"],
                    "opponent_id": nxt["next_to_id"],
                    "opponent_name": nxt["next_to_name"],
                    "sent": [],
                    "got": got,
                    "got_vorp": sum(float(item["ros_vorp"] or 0) for item in got),
                }
                grouped[key] = packed
            packed["sent"].append(
                {
                    "player_id": player["player_id"],
                    "player_name": player["player_name"],
                    "after": after,
                }
            )
    return list(grouped.values())


def _season_wire(year: int) -> dict[str, Any]:
    adds = _season_wire_adds(year)
    misses = fetchall(
        """
        SELECT
            year, week, manager_id, manager_name, reason,
            missed_transaction_id, missed_seq, missed_player_id, missed_player,
            missed_position, missed_vorp, won_transaction_id, won_seq,
            won_player_id, won_player, won_vorp, vorp_gap
        FROM v_waiver_misses
        WHERE year = %(year)s
            AND reason IN ('own_claim_order', 'lost_on_wire')
        ORDER BY vorp_gap DESC, week, missed_player
        LIMIT 5
        """,
        {"year": year},
    )
    for row in misses:
        row["flag"] = "own order" if row["reason"] == "own_claim_order" else "lost on wire"
    dodges = fetchall(
        """
        SELECT
            year, week, manager_id, manager_name,
            lost_transaction_id, lost_seq, lost_player_id, lost_player, lost_position,
            lost_vorp, won_transaction_id, won_seq, won_player_id, won_player,
            won_vorp, vorp_gap
        FROM v_waiver_dodges
        WHERE year = %(year)s
        ORDER BY vorp_gap DESC, week, lost_player
        LIMIT 5
        """,
        {"year": year},
    )
    managers = fetchall(
        """
        SELECT
            a.manager_id,
            a.manager_name,
            t.team_name,
            a.adds,
            a.waivers,
            a.free_agents,
            a.ros_vorp,
            a.waiver_vorp,
            a.fa_vorp,
            a.best_vorp,
            coalesce(m.misses, 0) AS misses
        FROM v_add_season a
        JOIN team_seasons t ON t.year = a.year AND t.manager_id = a.manager_id
        LEFT JOIN (
            SELECT manager_id, count(*) AS misses
            FROM v_waiver_misses
            WHERE year = %(year)s
                AND reason IN ('own_claim_order', 'lost_on_wire')
            GROUP BY manager_id
        ) m ON m.manager_id = a.manager_id
        WHERE a.year = %(year)s
        ORDER BY a.ros_vorp DESC NULLS LAST, a.manager_name
        """,
        {"year": year},
    )
    return {"adds": adds, "misses": misses, "dodges": dodges, "managers": managers}


def _wire_add_highlights(
    *,
    year: int | None = None,
    manager_id: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            v.year, v.week, v.type, v.transaction_id, v.manager_id, v.manager_name,
            v.player_id, v.player_name, v.position, v.ros_vorp,
            mv.bid, mv.priority
        FROM v_add_value v
        LEFT JOIN v_moves mv
            ON mv.transaction_id = v.transaction_id
            AND mv.player_id = v.player_id
            AND mv.manager_id = v.manager_id
            AND mv.direction = 'add'
        WHERE (%(year)s::integer IS NULL OR v.year = %(year)s)
            AND (%(manager_id)s::text IS NULL OR v.manager_id = %(manager_id)s)
        ORDER BY v.ros_vorp DESC NULLS LAST, v.year, v.week, v.player_name
        LIMIT %(limit)s
        """,
        {"year": year, "manager_id": manager_id, "limit": limit},
    )
    for row in rows:
        row["kind"] = "wav" if row["type"] == "waiver" else "FA"
        row["bid_label"] = _wire_bid(row)
    return rows


def _season_wire_adds(year: int) -> list[dict[str, Any]]:
    return _wire_add_highlights(year=year, limit=5)


def _claim_outcome(row: dict[str, Any]) -> dict[str, str]:
    status = str(row.get("status") or "")
    if row.get("type") == "free_agent" and status == "complete":
        return {"kind": "won", "label": "free agent"}
    if status == "complete":
        return {"kind": "won", "label": "won"}
    note = str(row.get("note") or "")
    lower = note.lower()
    if "claimed by another" in lower or note == "FAILED_INVALIDPLAYERSOURCE":
        return {"kind": "lost", "label": "lost on wire"}
    if "too many players" in lower or note == "FAILED_ROSTERLIMIT":
        return {"kind": "order", "label": "roster limit"}
    if row.get("type") == "free_agent":
        return {"kind": "won", "label": "free agent"}
    return {"kind": "failed", "label": "failed"}


def _uses_faab(year: int | None) -> bool:
    return year is not None and int(year) >= FAAB_START_YEAR


def _wire_bid(row: dict[str, Any]) -> str | None:
    year = row.get("year")
    if _uses_faab(year):
        bid = row.get("bid")
        return f"${int(bid)}" if bid is not None else None
    priority = row.get("priority")
    if priority is not None:
        return f"pri {int(priority)}"
    return None


def _claim_order_sql(year: int) -> str:
    won_first = "CASE WHEN status = 'complete' THEN 0 ELSE 1 END"
    if _uses_faab(year):
        return f"{won_first}, bid DESC NULLS LAST, priority NULLS LAST, seq NULLS LAST"
    return f"{won_first}, priority NULLS LAST, seq NULLS LAST"


def _attach_wire_drops(rows: list[dict[str, Any]]) -> None:
    ids = [row["transaction_id"] for row in rows if row.get("transaction_id")]
    if not ids:
        for row in rows:
            row["drops"] = []
        return
    drops = fetchall(
        """
        SELECT transaction_id, player_id, player_name, position
        FROM v_moves
        WHERE transaction_id = ANY(%(ids)s)
            AND direction = 'drop'
        ORDER BY player_name
        """,
        {"ids": ids},
    )
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in drops:
        by[row["transaction_id"]].append(row)
    for row in rows:
        row["drops"] = by.get(row["transaction_id"], [])


def _annotate_wire_row(row: dict[str, Any]) -> dict[str, Any]:
    packed = dict(row)
    packed["outcome"] = _claim_outcome(packed)
    packed["bid_label"] = _wire_bid(packed)
    packed.update(_wire_when(packed.get("at")))
    if "drops" not in packed:
        packed["drops"] = []
    return packed


def _txn_at(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        raw = int(value)
    except (TypeError, ValueError):
        return None
    if raw <= 0:
        return None
    if raw > 10_000_000_000:
        raw = raw / 1000
    return datetime.fromtimestamp(raw, tz=timezone.utc).astimezone(LEAGUE_TZ)


def _wire_when(value: Any) -> dict[str, Any]:
    when = _txn_at(value)
    if when is None:
        return {"day_key": "", "day_label": "No timestamp", "at_label": None}
    return {
        "day_key": when.date().isoformat(),
        "day_label": when.strftime("%a %b %d").replace(" 0", " "),
        "at_label": when.strftime("%I:%M %p").lstrip("0"),
    }


def _wire_days(
    claims: list[dict[str, Any]],
    fa: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for kind, rows in (("claims", claims), ("fa", fa)):
        for row in rows:
            key = str(row.get("day_key") or "")
            bucket = buckets.get(key)
            if bucket is None:
                bucket = {
                    "key": key,
                    "label": row.get("day_label") or "No timestamp",
                    "claims": [],
                    "fa": [],
                }
                buckets[key] = bucket
            bucket[kind].append(row)
    days = list(buckets.values())
    days.sort(key=lambda day: (day["key"] == "", day["key"]))
    return days


def _week_wire(year: int, week: int) -> dict[str, Any]:
    claims = fetchall(
        f"""
        SELECT
            transaction_id, year, week, status, manager_id, manager_name,
            player_id, player_name, position, bid, priority, seq, note, at,
            league_ros, league_starts, league_vorp
        FROM v_waiver_claims
        WHERE year = %(year)s AND week = %(week)s
        ORDER BY
            {_claim_order_sql(year)},
            league_vorp DESC,
            player_name
        """,
        {"year": year, "week": week},
    )
    for row in claims:
        row["type"] = "waiver"
    fa = fetchall(
        """
        SELECT
            mv.transaction_id, mv.year, mv.week, mv.status, mv.manager_id,
            mv.manager_name, mv.player_id, mv.player_name, mv.position,
            mv.bid, mv.priority, mv.seq, mv.note, mv.type, mv.at,
            v.ros_starter AS league_ros,
            v.ros_starts AS league_starts,
            v.ros_vorp AS league_vorp
        FROM v_moves mv
        LEFT JOIN v_add_value v
            ON v.transaction_id = mv.transaction_id
            AND v.player_id = mv.player_id
            AND v.manager_id = mv.manager_id
        WHERE mv.year = %(year)s
            AND mv.week = %(week)s
            AND mv.type = 'free_agent'
            AND mv.direction = 'add'
            AND mv.status = 'complete'
        ORDER BY mv.at NULLS LAST, v.ros_vorp DESC NULLS LAST, mv.player_name
        """,
        {"year": year, "week": week},
    )
    _attach_wire_drops(claims + fa)
    claims = [_annotate_wire_row(row) for row in claims]
    fa = [_annotate_wire_row(row) for row in fa]
    return {
        "claims": claims,
        "fa": fa,
        "days": _wire_days(claims, fa),
        "faab": _uses_faab(year),
        "show_order": _uses_faab(year) or any(row.get("bid_label") for row in claims),
    }


def wire_page(year: int, transaction_id: str) -> dict[str, Any] | None:
    claim = fetchone(
        """
        SELECT
            transaction_id, year, week, status, manager_id, manager_name,
            player_id, player_name, position, bid, priority, seq, note, at,
            league_ros, league_starts, league_vorp
        FROM v_waiver_claims
        WHERE year = %(year)s AND transaction_id = %(transaction_id)s
        """,
        {"year": year, "transaction_id": transaction_id},
    )
    kind = "waiver"
    if claim is None:
        claim = fetchone(
            """
            SELECT
                mv.transaction_id, mv.year, mv.week, mv.status, mv.manager_id,
                mv.manager_name, mv.player_id, mv.player_name, mv.position,
                mv.bid, mv.priority, mv.seq, mv.note, mv.type, mv.at,
                v.ros_starter AS league_ros,
                v.ros_starts AS league_starts,
                v.ros_vorp AS league_vorp
            FROM v_moves mv
            LEFT JOIN v_add_value v
                ON v.transaction_id = mv.transaction_id
                AND v.player_id = mv.player_id
                AND v.manager_id = mv.manager_id
            WHERE mv.year = %(year)s
                AND mv.transaction_id = %(transaction_id)s
                AND mv.type = 'free_agent'
                AND mv.direction = 'add'
                AND mv.status = 'complete'
            """,
            {"year": year, "transaction_id": transaction_id},
        )
        kind = "free_agent"
    if claim is None:
        return None
    claim["type"] = kind
    _attach_wire_drops([claim])
    packed = _annotate_wire_row(claim)
    tenure = fetchone(
        """
        SELECT ros_vorp, ros_starter, ros_starts, tenure_vorp
        FROM v_add_value
        WHERE transaction_id = %(transaction_id)s
            AND player_id = %(player_id)s
            AND manager_id = %(manager_id)s
        """,
        {
            "transaction_id": transaction_id,
            "player_id": packed["player_id"],
            "manager_id": packed["manager_id"],
        },
    )
    if tenure:
        packed["tenure_vorp"] = tenure.get("tenure_vorp")
        packed["ros_vorp"] = tenure.get("ros_vorp")
        packed["ros_starter"] = tenure.get("ros_starter")
        packed["ros_starts"] = tenure.get("ros_starts")
    rivals: list[dict[str, Any]] = []
    if kind == "waiver" and packed.get("player_id"):
        rivals = fetchall(
            f"""
            SELECT
                transaction_id, year, week, status, manager_id, manager_name,
                player_id, player_name, position, bid, priority, seq, note,
                league_ros, league_starts, league_vorp
            FROM v_waiver_claims
            WHERE year = %(year)s
                AND week = %(week)s
                AND player_id = %(player_id)s
            ORDER BY
                {_claim_order_sql(year)},
                manager_name
            """,
            {
                "year": year,
                "week": packed["week"],
                "player_id": packed["player_id"],
            },
        )
        for row in rivals:
            row["type"] = "waiver"
        _attach_wire_drops(rivals)
        rivals = [_annotate_wire_row(row) for row in rivals]
    nav = _wire_nav(year, transaction_id)
    return {**packed, "rivals": rivals, "faab": _uses_faab(year), **nav}


def _wire_nav(year: int, transaction_id: str) -> dict[str, Any]:
    rows = fetchall(
        """
        SELECT
            transaction_id,
            min(week) AS week,
            min(player_name) AS player_name
        FROM v_moves
        WHERE year = %(year)s
            AND type IN ('waiver', 'free_agent')
            AND direction = 'add'
        GROUP BY transaction_id
        ORDER BY min(week), transaction_id
        """,
        {"year": year},
    )
    index = next(
        (i for i, row in enumerate(rows) if row["transaction_id"] == transaction_id),
        None,
    )
    if index is None:
        return {"prev": None, "next": None}

    def chip(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["transaction_id"],
            "label": f"W{row['week']} {row['player_name']}",
        }

    return {
        "prev": chip(rows[index - 1]) if index > 0 else None,
        "next": chip(rows[index + 1]) if index < len(rows) - 1 else None,
    }


def draft_page(year: int) -> dict[str, Any] | None:
    picks = fetchall(
        """
        SELECT
            g.year, g.round, g.overall, g.manager_id, g.manager_name,
            t.team_name, g.player_id, g.player_name, g.position, g.keeper,
            g.ros_starter, g.ros_starts, g.ros_vorp, g.vs_vorp, g.round_vorp,
            g.adp, g.times_drafted, g.pick_vs_adp, g.hit
        FROM v_draft_grades g
        JOIN team_seasons t ON t.year = g.year AND t.manager_id = g.manager_id
        WHERE g.year = %(year)s
        ORDER BY g.overall
        """,
        {"year": year},
    )
    if not picks:
        return None
    years = [int(row["year"]) for row in fetchall("SELECT DISTINCT year FROM v_draft ORDER BY year")]
    index = years.index(year) if year in years else -1
    scale = max(
        50.0,
        max((abs(float(row["vs_vorp"] or 0)) for row in picks), default=0.0),
    )
    for row in picks:
        _annotate_draft_pick(row, scale)
    return {
        "board": _draft_snake(picks),
        "years": years,
        "prev_year": years[index - 1] if index > 0 else None,
        "next_year": years[index + 1] if 0 <= index < len(years) - 1 else None,
        "has_keepers": any(row.get("keeper") for row in picks),
    }


def _season_draft(year: int) -> dict[str, Any]:
    rows = fetchall(
        """
        SELECT
            year, round, overall, manager_id, manager_name,
            player_id, player_name, position, keeper,
            ros_vorp, vs_vorp, ros_starts, hit
        FROM v_draft_grades
        WHERE year = %(year)s
        ORDER BY vs_vorp DESC NULLS LAST, overall
        """,
        {"year": year},
    )
    ranked = [row for row in rows if row.get("vs_vorp") is not None]
    hits = ranked[:5]
    rest = ranked[5:]
    misses = list(reversed(rest[-5:])) if rest else []
    managers = fetchall(
        """
        SELECT
            m.manager_id,
            m.manager_name,
            t.team_name,
            m.picks,
            m.keepers,
            m.ros_starter,
            m.ros_vorp,
            m.vs_vorp,
            m.hits,
            m.best_vorp,
            b.player_id AS best_player_id,
            b.player_name AS best_player,
            b.overall AS best_overall
        FROM v_draft_manager m
        JOIN team_seasons t ON t.year = m.year AND t.manager_id = m.manager_id
        LEFT JOIN LATERAL (
            SELECT player_id, player_name, overall
            FROM v_draft_grades g
            WHERE g.year = m.year
                AND g.manager_id = m.manager_id
            ORDER BY ros_vorp DESC NULLS LAST, overall
            LIMIT 1
        ) b ON true
        WHERE m.year = %(year)s
        ORDER BY m.vs_vorp DESC NULLS LAST, m.manager_name
        """,
        {"year": year},
    )
    return {
        "managers": managers,
        "hits": hits,
        "misses": misses,
        "has_keepers": any(int(row.get("keepers") or 0) for row in managers),
    }


def _annotate_draft_pick(row: dict[str, Any], scale: float) -> None:
    vs = float(row["vs_vorp"] or 0) if row.get("vs_vorp") is not None else None
    if vs is None or scale <= 0:
        row["heat"] = 0.0
        row["tone"] = "transparent"
    else:
        row["heat"] = min(1.0, abs(vs) / scale)
        row["tone"] = "#14532d" if vs >= 0 else "#9f1239"
    parts: list[str] = []
    starts = int(row["ros_starts"] or 0)
    parts.append(f"{starts} start" + ("s" if starts != 1 else ""))
    if row.get("ros_vorp") is not None:
        parts.append(f"{float(row['ros_vorp']):+.1f} VORP")
    if row.get("ros_starter") is not None:
        parts.append(f"{float(row['ros_starter']):.1f} PF")
    if row.get("vs_vorp") is not None:
        parts.append(f"{float(row['vs_vorp']):+.1f} vs round")
    if row.get("hit"):
        parts.append("hit")
    times = int(row.get("times_drafted") or 0)
    adp = row.get("adp")
    delta = row.get("pick_vs_adp")
    if adp is not None and delta is not None and times >= 2:
        delta_f = float(delta)
        when = "later" if delta_f > 0 else "earlier"
        parts.append(f"ADP {float(adp):.1f} {when} {abs(delta_f):.1f}")
    if row.get("keeper"):
        parts.append("keeper")
    row["tooltip"] = " · ".join(parts)


def _draft_snake(picks: list[dict[str, Any]]) -> dict[str, Any]:
    round1 = sorted(
        (row for row in picks if int(row["round"]) == 1),
        key=lambda row: int(row["overall"]),
    )
    columns = [
        {
            "manager_id": row["manager_id"],
            "manager_name": row["manager_name"],
            "team_name": row.get("team_name"),
        }
        for row in round1
    ]
    index = {col["manager_id"]: i for i, col in enumerate(columns)}
    n = len(columns)
    extras: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    max_round = max((int(row["round"]) for row in picks), default=0)
    by_round: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in picks:
        by_round[int(row["round"])].append(row)
    for rnd in range(1, max_round + 1):
        slots: list[dict[str, Any] | None] = [None] * n
        round_vorp = None
        for row in by_round.get(rnd, []):
            if round_vorp is None and row.get("round_vorp") is not None:
                round_vorp = float(row["round_vorp"])
            i = index.get(row["manager_id"])
            if i is None or slots[i] is not None:
                extras.append(row)
                continue
            slots[i] = row
        rows.append({"round": rnd, "slots": slots, "round_vorp": round_vorp})
    return {"columns": columns, "rows": rows, "extras": extras}


def _season_lineups(year: int) -> dict[str, Any]:
    coaches = fetchall(
        """
        SELECT
            s.manager_id,
            s.manager_name,
            t.team_name,
            s.weeks,
            s.actual_points,
            s.optimal_points,
            s.left_on_bench
        FROM v_management_season s
        JOIN team_seasons t ON t.year = s.year AND t.manager_id = s.manager_id
        WHERE s.year = %(year)s
        """,
        {"year": year},
    )
    weekly = fetchall(
        """
        SELECT
            week, matchup_id, manager_id,
            left_on_bench, management_pct
        FROM v_management_weeks
        WHERE year = %(year)s
            AND kind = 'regular'
        ORDER BY week, manager_id
        """,
        {"year": year},
    )
    week_nums = sorted({int(row["week"]) for row in weekly})
    by_mgr: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    max_left = 0.0
    for row in weekly:
        left = max(0.0, float(row["left_on_bench"] or 0))
        max_left = max(max_left, left)
        by_mgr[row["manager_id"]][int(row["week"])] = row
    for coach in coaches:
        actual = float(coach["actual_points"] or 0)
        ideal = float(coach["optimal_points"] or 0)
        coach["season_pct"] = (actual / ideal) if ideal else None
        pcts: list[float] = []
        cells: list[dict[str, Any]] = []
        for week in week_nums:
            row = by_mgr[coach["manager_id"]].get(week)
            if row is None:
                cells.append({"week": week, "left": None, "heat": None, "matchup_id": None})
                continue
            left = max(0.0, float(row["left_on_bench"] or 0))
            pct = row["management_pct"]
            if pct is not None:
                pcts.append(float(pct))
            cells.append(
                {
                    "week": week,
                    "left": left,
                    "heat": (left / max_left) if max_left else 0.0,
                    "matchup_id": row["matchup_id"],
                }
            )
        coach["cells"] = cells
        coach["min_pct"] = min(pcts) if pcts else None
        coach["max_pct"] = max(pcts) if pcts else None
    coaches.sort(
        key=lambda row: (
            -(row["season_pct"] if row["season_pct"] is not None else -1),
            row["manager_id"],
        )
    )
    for index, coach in enumerate(coaches, start=1):
        coach["coach_rank"] = index
    benches = fetchall(
        """
        SELECT
            week, matchup_id, manager_id, manager_name,
            player_id, player_name, position, points
        FROM v_start_sit
        WHERE year = %(year)s
            AND kind = 'regular'
            AND call = 'should_start'
        ORDER BY points DESC, week, player_name
        LIMIT 5
        """,
        {"year": year},
    )
    return {
        "coaches": coaches,
        "week_nums": week_nums,
        "max_left": max_left,
        "benches": benches,
    }


def week_slate(year: int, week: int) -> dict[str, Any] | None:
    games = _week_games(year, week)
    if not games:
        return None
    ranks = _week_ranks(year, week)
    packed = [_score_game(game) for game in games]
    for game in packed:
        _apply_week_context(game, ranks)
    return {
        **_week_nav(year, week),
        "groups": _group_games(packed),
        "wire": _week_wire(year, week),
    }


def gamecenter(year: int, week: int, matchup_id: str) -> dict[str, Any] | None:
    games = _week_games(year, week)
    row = next((game for game in games if game["id"] == matchup_id), None)
    if row is None:
        return None
    slots = fetchall(
        """
        SELECT matchup_id, manager_id, player_id, player_name, slot, started, points
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
    packed = _score_game(row, by_side=by_side, bench_by=bench_by)
    _apply_week_context(packed, _week_ranks(year, week))
    coach = _matchup_coach(matchup_id, packed["home"]["id"], packed["away"]["id"])
    if coach:
        _annotate_calls(packed["home"], coach["home"].get("optimal") or [])
        _annotate_calls(packed["away"], coach["away"].get("optimal") or [])
        actual_winner = packed.get("winner_id")
        opt_winner = coach.get("winner_id")
        coach["flipped"] = bool(
            actual_winner and opt_winner and actual_winner != opt_winner
        )
    return {
        **_week_nav(year, week),
        "game": packed,
        "kind_label": KIND_LABELS.get(row["kind"], row["kind"]),
        "siblings": siblings,
        "prev_match": siblings[index - 1] if index > 0 else None,
        "next_match": siblings[index + 1] if index < len(siblings) - 1 else None,
        "battle": _slot_battle(packed["home"].get("starters") or [], packed["away"].get("starters") or []),
        "bench": _slot_battle(packed["home"].get("bench") or [], packed["away"].get("bench") or []),
        "luck": _matchup_luck(
            matchup_id, packed["home"]["id"], packed["away"]["id"], year
        ),
        "coach": coach,
        "history": _matchup_history(packed["home"]["id"], packed["away"]["id"], matchup_id),
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
    margin = None
    if home["points"] is not None and away["points"] is not None:
        margin = round(float(home["points"]) - float(away["points"]), 2)
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
        "margin": margin,
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


def _week_ranks(year: int, week: int) -> dict[str, dict[str, Any]]:
    return {
        row["manager_id"]: row
        for row in fetchall(
            """
            SELECT
                w.manager_id,
                rank() OVER (ORDER BY w.points DESC, w.manager_id) AS pf_rank,
                count(*) OVER () AS teams,
                ap.wins AS all_play_wins,
                ap.losses AS all_play_losses,
                ap.ties AS all_play_ties
            FROM week_scores w
            LEFT JOIN v_all_play ap
                ON ap.year = w.year AND ap.week = w.week AND ap.manager_id = w.manager_id
            WHERE w.year = %(year)s AND w.week = %(week)s
            """,
            {"year": year, "week": week},
        )
    }


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _record(wins: int, losses: int, ties: int) -> str:
    if ties:
        return f"{wins}-{losses}-{ties}"
    return f"{wins}-{losses}"


def _maybe_record(wins: Any, losses: Any, ties: Any) -> str | None:
    if wins is None and losses is None and ties is None:
        return None
    return _record(int(wins or 0), int(losses or 0), int(ties or 0))


def _apply_week_context(game: dict[str, Any], ranks: dict[str, dict[str, Any]]) -> None:
    for side in (game["home"], game["away"]):
        ctx = ranks.get(side["id"]) if side["id"] else None
        if not ctx:
            continue
        side["pf_rank"] = int(ctx["pf_rank"])
        side["pf_ordinal"] = _ordinal(int(ctx["pf_rank"]))
        side["teams"] = int(ctx["teams"])
        side["all_play_wins"] = int(ctx["all_play_wins"] or 0)
        side["all_play_losses"] = int(ctx["all_play_losses"] or 0)
        side["all_play_ties"] = int(ctx["all_play_ties"] or 0)
        side["all_play"] = _record(
            side["all_play_wins"], side["all_play_losses"], side["all_play_ties"]
        )


def _slot_battle(
    home_starters: list[dict[str, Any]], away_starters: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if not home_starters and not away_starters:
        return None
    slots = sorted(
        {row["slot"] for row in home_starters + away_starters if row.get("slot")},
        key=lambda slot: (SLOT_ORDER.get(slot, 40), slot),
    )
    rows: list[dict[str, Any]] = []
    home_won = 0
    away_won = 0
    for slot in slots:
        home_list = [row for row in home_starters if row["slot"] == slot]
        away_list = [row for row in away_starters if row["slot"] == slot]
        for index in range(max(len(home_list), len(away_list), 1)):
            home = home_list[index] if index < len(home_list) else None
            away = away_list[index] if index < len(away_list) else None
            home_pts = float(home["points"]) if home and home["points"] is not None else None
            away_pts = float(away["points"]) if away and away["points"] is not None else None
            winner = None
            if home_pts is not None and away_pts is not None:
                if home_pts > away_pts:
                    winner = "home"
                    home_won += 1
                elif away_pts > home_pts:
                    winner = "away"
                    away_won += 1
            delta = None
            if home_pts is not None and away_pts is not None:
                delta = round(home_pts - away_pts, 2)
            rows.append(
                {
                    "slot": slot,
                    "home": home,
                    "away": away,
                    "delta": delta,
                    "winner": winner,
                }
            )
    return {"rows": rows, "home_won": home_won, "away_won": away_won}


def _matchup_coach(
    matchup_id: str, home_id: str | None, away_id: str | None
) -> dict[str, Any] | None:
    if not home_id or not away_id:
        return None
    slots = fetchall(
        """
        SELECT manager_id, player_id, player_name, position, points, started, opt_slot
        FROM v_optimal_slots
        WHERE matchup_id = %(matchup_id)s
        """,
        {"matchup_id": matchup_id},
    )
    weeks = {
        row["manager_id"]: row
        for row in fetchall(
            """
            SELECT manager_id, actual_points, optimal_points, left_on_bench, management_pct
            FROM v_management_weeks
            WHERE matchup_id = %(matchup_id)s
            """,
            {"matchup_id": matchup_id},
        )
    }
    if home_id not in weeks and away_id not in weeks and not slots:
        return None

    def side_optimal(manager_id: str) -> list[dict[str, Any]]:
        rows = [
            {**row, "slot": row["opt_slot"]}
            for row in slots
            if row["manager_id"] == manager_id
        ]
        rows.sort(
            key=lambda row: (
                SLOT_ORDER.get(row["slot"] or "", 40),
                row["slot"] or "",
                -(float(row["points"] or 0)),
            )
        )
        return rows

    home_opt = side_optimal(home_id)
    away_opt = side_optimal(away_id)
    home_week = dict(weeks.get(home_id) or {})
    away_week = dict(weeks.get(away_id) or {})
    home_week["optimal"] = home_opt
    away_week["optimal"] = away_opt
    winner_id = None
    home_pts = home_week.get("optimal_points")
    away_pts = away_week.get("optimal_points")
    if home_pts is not None and away_pts is not None:
        if home_pts > away_pts:
            winner_id = home_id
        elif away_pts > home_pts:
            winner_id = away_id
    battle = _slot_battle(home_opt, away_opt)
    packed = {"home": home_week, "away": away_week, "winner_id": winner_id}
    if battle:
        packed["battle"] = battle
    return packed


def _annotate_calls(side: dict[str, Any], optimal: list[dict[str, Any]]) -> None:
    by_player = {
        row["player_id"]: row for row in optimal if row.get("player_id")
    }
    if not by_player:
        return
    for row in (side.get("starters") or []) + (side.get("bench") or []):
        opt = by_player.get(row.get("player_id"))
        if row.get("started") and not opt:
            row["call"] = "sit"
        elif not row.get("started") and opt:
            row["call"] = "start"
            row["opt_slot"] = opt["opt_slot"]


def _matchup_luck(
    matchup_id: str, home_id: str | None, away_id: str | None, year: int
) -> dict[str, Any] | None:
    if not home_id or not away_id:
        return None
    rows = fetchall(
        """
        SELECT
            manager_id, lucky_win, unlucky_loss, underdog_win, favorite_loss,
            pf_rank, opp_pf_rank, teams, expected_win,
            all_play_wins, all_play_losses, all_play_ties
        FROM v_luck_weeks
        WHERE matchup_id = %(matchup_id)s
        """,
        {"matchup_id": matchup_id},
    )
    if not rows:
        return None
    season = {
        row["manager_id"]: row
        for row in fetchall(
            """
            SELECT manager_id, net_luck, wins_vs_expected, lucky_wins, unlucky_losses
            FROM v_luck_season
            WHERE year = %(year)s
                AND manager_id IN (%(home_id)s, %(away_id)s)
            """,
            {"year": year, "home_id": home_id, "away_id": away_id},
        )
    }
    by_id = {row["manager_id"]: row for row in rows}
    packed: dict[str, Any] = {}
    for manager_id in (home_id, away_id):
        week = by_id.get(manager_id)
        if not week:
            continue
        packed["home" if manager_id == home_id else "away"] = {**week, **(season.get(manager_id) or {})}
    if "home" not in packed and "away" not in packed:
        return None
    return packed


def _matchup_history(
    home_id: str | None, away_id: str | None, matchup_id: str
) -> dict[str, Any] | None:
    if not home_id or not away_id:
        return None
    pair = next((row for row in h2h_for(home_id) if row["opponent_id"] == away_id), None)
    meetings = fetchall(
        """
        SELECT matchup_id, year, week, kind, points, opp_points, result
        FROM v_games
        WHERE manager_id = %(home_id)s
            AND opponent_id = %(away_id)s
            AND kind IN ('regular', 'playoff', 'consolation')
        ORDER BY year, week, matchup_id
        """,
        {"home_id": home_id, "away_id": away_id},
    )
    for meeting in meetings:
        meeting["kind_label"] = KIND_LABELS.get(meeting["kind"], meeting["kind"])
        meeting["current"] = meeting["matchup_id"] == matchup_id
    if pair is None and not meetings:
        return None
    return {"h2h": pair, "meetings": meetings}


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
        SELECT
            c.manager_id, c.display_name, c.seasons, c.wins, c.losses, c.ties,
            c.points_for, c.win_pct, c.titles, c.runner_up,
            c.regular_season_titles, c.most_points_titles, c.playoff_appearances,
            s.result AS streak_result, s.length AS streak_length
        FROM v_career c
        LEFT JOIN LATERAL (
            SELECT result, length
            FROM v_streaks
            WHERE manager_id = c.manager_id AND is_current
            LIMIT 1
        ) s ON true
        ORDER BY c.titles DESC, c.win_pct DESC NULLS LAST, c.points_for DESC, c.manager_id
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


def member_page(manager_id: str) -> dict[str, Any] | None:
    person = career_one(manager_id)
    if person is None:
        return None
    person["streak"] = fetchone(
        """
        SELECT result, length, start_year, start_week, end_year, end_week
        FROM v_streaks
        WHERE manager_id = %(manager_id)s AND is_current
        LIMIT 1
        """,
        {"manager_id": manager_id},
    )
    h2h = h2h_for(manager_id)
    person["playoff"] = _member_playoff_record(h2h)
    person["rival"], person["favorite"] = _member_h2h_poles(h2h)
    return {
        "member": person,
        "finishes": _member_finishes(manager_id),
        "h2h": h2h,
        "draft": _member_draft(manager_id),
        "wire": _member_wire(manager_id),
        "trades": _member_trades(manager_id),
        "lineups": _member_lineups(manager_id),
        "luck": fetchone(
            """
            SELECT
                lucky_wins, unlucky_losses, net_luck,
                underdog_wins, favorite_losses, expected_wins, wins_vs_expected
            FROM v_luck_career
            WHERE manager_id = %(manager_id)s
            """,
            {"manager_id": manager_id},
        ),
        "highs": _member_highs(manager_id),
    }


def _member_finishes(manager_id: str) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            s.year, s.rank, s.team_name, s.wins, s.losses, s.ties,
            s.points_for, s.win_pct,
            (o.champion = s.manager_id) AS champion,
            (o.runner_up = s.manager_id) AS runner_up,
            (o.regular_season_champion = s.manager_id) AS rs_champ,
            (o.most_points = s.manager_id) AS most_points,
            (p.manager_id IS NOT NULL) AS playoff
        FROM v_standings_official s
        LEFT JOIN season_outcomes o ON o.year = s.year
        LEFT JOIN season_playoff_managers p
            ON p.year = s.year AND p.manager_id = s.manager_id
        WHERE s.manager_id = %(manager_id)s
        ORDER BY s.year
        """,
        {"manager_id": manager_id},
    )


def finishes(manager_id: str) -> list[dict[str, Any]]:
    return _member_finishes(manager_id)


def h2h_for(manager_id: str) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            left_id, left_name, right_id, right_name,
            regular_games, regular_wins, regular_losses, regular_ties,
            regular_points_for, regular_points_against,
            playoff_wins, playoff_losses, playoff_ties, playoff_games,
            playoff_points_for, playoff_points_against,
            regular_avg_margin, regular_biggest_blowout, regular_closest
        FROM v_h2h
        WHERE left_id = %(manager_id)s OR right_id = %(manager_id)s
        ORDER BY regular_games + playoff_games DESC, left_id, right_id
        """,
        {"manager_id": manager_id},
    )
    oriented: list[dict[str, Any]] = []
    for row in rows:
        flipped = row["right_id"] == manager_id
        margin = row.get("regular_avg_margin")
        if flipped and margin is not None:
            margin = -float(margin)
        oriented.append(
            {
                "opponent_id": row["left_id"] if flipped else row["right_id"],
                "opponent": row["left_name"] if flipped else row["right_name"],
                "regular_games": row["regular_games"],
                "regular_wins": row["regular_losses"] if flipped else row["regular_wins"],
                "regular_losses": row["regular_wins"] if flipped else row["regular_losses"],
                "regular_ties": row["regular_ties"],
                "regular_points_for": row["regular_points_against"] if flipped else row["regular_points_for"],
                "regular_points_against": row["regular_points_for"] if flipped else row["regular_points_against"],
                "playoff_wins": row["playoff_losses"] if flipped else row["playoff_wins"],
                "playoff_losses": row["playoff_wins"] if flipped else row["playoff_losses"],
                "playoff_ties": row["playoff_ties"],
                "playoff_games": row["playoff_games"],
                "playoff_points_for": row["playoff_points_against"] if flipped else row["playoff_points_for"],
                "playoff_points_against": row["playoff_points_for"] if flipped else row["playoff_points_against"],
                "regular_avg_margin": margin,
                "regular_biggest_blowout": row["regular_biggest_blowout"],
                "regular_closest": row["regular_closest"],
            }
        )
    return oriented


def _h2h_games(row: dict[str, Any]) -> int:
    return int(row.get("regular_games") or 0) + int(row.get("playoff_games") or 0)


def _h2h_wl(row: dict[str, Any]) -> tuple[int, int, int]:
    wins = int(row.get("regular_wins") or 0) + int(row.get("playoff_wins") or 0)
    losses = int(row.get("regular_losses") or 0) + int(row.get("playoff_losses") or 0)
    ties = int(row.get("regular_ties") or 0) + int(row.get("playoff_ties") or 0)
    return wins, losses, ties


def _h2h_pct(row: dict[str, Any]) -> float:
    wins, losses, ties = _h2h_wl(row)
    games = wins + losses + ties
    if games == 0:
        return 0.5
    return (wins + 0.5 * ties) / games


def _h2h_card(row: dict[str, Any]) -> dict[str, Any]:
    wins, losses, ties = _h2h_wl(row)
    return {
        "id": row["opponent_id"],
        "name": row["opponent"],
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "games": wins + losses + ties,
        "win_pct": _h2h_pct(row),
    }


def _member_playoff_record(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    wins = sum(int(row.get("playoff_wins") or 0) for row in rows)
    losses = sum(int(row.get("playoff_losses") or 0) for row in rows)
    ties = sum(int(row.get("playoff_ties") or 0) for row in rows)
    games = wins + losses + ties
    if games == 0:
        return None
    return {"wins": wins, "losses": losses, "ties": ties, "games": games}


def _member_h2h_poles(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    max_games = max((_h2h_games(row) for row in rows), default=0)
    min_games = 4 if max_games >= 4 else 2 if max_games >= 2 else 0
    eligible = [row for row in rows if _h2h_games(row) >= min_games] if min_games else []
    if not eligible:
        return None, None
    rival_row = min(
        eligible,
        key=lambda row: (_h2h_pct(row), -_h2h_games(row), row["opponent"] or ""),
    )
    favorite_row = max(
        eligible,
        key=lambda row: (_h2h_pct(row), _h2h_games(row), row["opponent"] or ""),
    )
    rival = _h2h_card(rival_row)
    favorite = _h2h_card(favorite_row)
    if rival["win_pct"] >= 0.5:
        rival = None
    if favorite and favorite["win_pct"] <= 0.5:
        favorite = None
    if rival and favorite and rival["id"] == favorite["id"]:
        favorite = None
    return rival, favorite


def _member_draft(manager_id: str) -> dict[str, Any]:
    totals = fetchone(
        """
        SELECT
            coalesce(sum(picks), 0) AS picks,
            coalesce(sum(hits), 0) AS hits,
            sum(vs_vorp) AS vs_vorp,
            sum(ros_vorp) AS ros_vorp
        FROM v_draft_manager
        WHERE manager_id = %(manager_id)s
        """,
        {"manager_id": manager_id},
    ) or {}
    rows = fetchall(
        """
        SELECT
            year, round, overall, manager_id, manager_name,
            player_id, player_name, position, keeper, vs_vorp, ros_vorp
        FROM v_draft_grades
        WHERE manager_id = %(manager_id)s
        ORDER BY vs_vorp DESC NULLS LAST, year, overall
        """,
        {"manager_id": manager_id},
    )
    ranked = [row for row in rows if row.get("vs_vorp") is not None]
    hits = ranked[:5]
    rest = ranked[5:]
    misses = list(reversed(rest[-5:])) if rest else []
    return {"totals": totals, "hits": hits, "misses": misses}


def _member_wire(manager_id: str) -> dict[str, Any]:
    totals = fetchone(
        """
        SELECT
            coalesce(sum(adds), 0) AS adds,
            coalesce(sum(waivers), 0) AS waivers,
            coalesce(sum(free_agents), 0) AS free_agents,
            sum(ros_vorp) AS ros_vorp
        FROM v_add_season
        WHERE manager_id = %(manager_id)s
        """,
        {"manager_id": manager_id},
    ) or {}
    misses = fetchall(
        """
        SELECT
            year, week, manager_id, manager_name, reason,
            missed_transaction_id, missed_player_id, missed_player,
            won_transaction_id, won_player_id, won_player, vorp_gap
        FROM v_waiver_misses
        WHERE manager_id = %(manager_id)s
            AND reason IN ('own_claim_order', 'lost_on_wire')
        ORDER BY vorp_gap DESC, year, week, missed_player
        LIMIT 5
        """,
        {"manager_id": manager_id},
    )
    for row in misses:
        row["flag"] = "own order" if row["reason"] == "own_claim_order" else "lost on wire"
    return {
        "totals": totals,
        "adds": _wire_add_highlights(manager_id=manager_id, limit=5),
        "misses": misses,
    }


def _member_trades(manager_id: str) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            transaction_id, year, week, left_id, left_name, left_received, left_vorp,
            right_id, right_name, right_received, right_vorp,
            vorp_gap, winner_id
        FROM v_trade_grades
        WHERE left_id = %(manager_id)s OR right_id = %(manager_id)s
        ORDER BY year DESC, week, vorp_gap DESC, left_id
        """,
        {"manager_id": manager_id},
    )
    for row in rows:
        row["verdict"] = _trade_verdict(row.get("left_vorp"), row.get("right_vorp"))
        home, away = _trade_card_sides(row)
        if home["id"] != manager_id:
            home, away = away, home
        row["home"], row["away"] = home, away
    _attach_trade_card_players(rows)
    return rows


def _member_lineups(manager_id: str) -> dict[str, Any]:
    career = fetchone(
        """
        SELECT weeks, actual_points, optimal_points, left_on_bench, management_pct
        FROM v_management_career
        WHERE manager_id = %(manager_id)s
        """,
        {"manager_id": manager_id},
    )
    return {
        "career": career,
        "worst": _member_lineup_weeks(manager_id, worst=True),
        "best": _member_lineup_weeks(manager_id, worst=False),
    }


def _member_lineup_weeks(manager_id: str, *, worst: bool, limit: int = 5) -> list[dict[str, Any]]:
    leftover = "DESC" if worst else "ASC"
    pct = "ASC" if worst else "DESC"
    return fetchall(
        f"""
        SELECT year, week, matchup_id, actual_points, optimal_points,
               left_on_bench, management_pct
        FROM v_management_weeks
        WHERE manager_id = %(manager_id)s
            AND kind = 'regular'
        ORDER BY left_on_bench {leftover} NULLS LAST,
            management_pct {pct} NULLS LAST, year, week
        LIMIT %(limit)s
        """,
        {"manager_id": manager_id, "limit": limit},
    )


def _member_highs(manager_id: str) -> dict[str, Any]:
    high = _member_extreme_week(manager_id, high=True)
    low = _member_extreme_week(manager_id, high=False)
    blowout = _member_margin_game(manager_id, closest=False)
    closest = _member_margin_game(manager_id, closest=True)
    win_streak = _member_longest_streak(manager_id, "win")
    loss_streak = _member_longest_streak(manager_id, "loss")
    _stamp_alltime(
        high,
        high_weeks(),
        "/records#high",
        "highest",
        lambda notable, row: (
            int(row["year"]) == int(notable["year"])
            and int(row["week"]) == int(notable["week"])
            and row["manager_id"] == notable.get("scorer_id")
        ),
    )
    _stamp_alltime(
        low,
        low_weeks(),
        "/records#low",
        "lowest",
        lambda notable, row: (
            int(row["year"]) == int(notable["year"])
            and int(row["week"]) == int(notable["week"])
            and row["manager_id"] == notable.get("scorer_id")
        ),
    )
    _stamp_alltime(
        blowout,
        blowouts(),
        "/records#blowouts",
        "biggest",
        lambda notable, row: row["matchup_id"] == notable.get("id"),
    )
    _stamp_alltime(
        closest,
        closest_games(),
        "/records#closest",
        "closest",
        lambda notable, row: row["matchup_id"] == notable.get("id"),
    )
    _stamp_alltime(
        win_streak,
        longest_streaks("win"),
        "/records#wins",
        "longest",
        lambda notable, row: (
            row["manager_id"] == notable.get("manager_id")
            and int(row["length"]) == int(notable["length"])
            and int(row["start_year"]) == int(notable["start_year"])
            and int(row["start_week"]) == int(notable["start_week"])
        ),
    )
    _stamp_alltime(
        loss_streak,
        longest_streaks("loss"),
        "/records#losses",
        "longest",
        lambda notable, row: (
            row["manager_id"] == notable.get("manager_id")
            and int(row["length"]) == int(notable["length"])
            and int(row["start_year"]) == int(notable["start_year"])
            and int(row["start_week"]) == int(notable["start_week"])
        ),
    )
    return {
        "high": high,
        "low": low,
        "blowout": blowout,
        "closest": closest,
        "win_streak": win_streak,
        "loss_streak": loss_streak,
    }


def _member_extreme_week(manager_id: str, *, high: bool) -> dict[str, Any] | None:
    row = fetchone(
        f"""
        SELECT w.year, w.week, w.manager_id, w.display_name, w.points
        FROM v_record_weeks w
        WHERE w.manager_id = %(manager_id)s
            AND w.paired
            AND EXISTS (
                SELECT 1
                FROM matchups m
                WHERE m.year = w.year AND m.week = w.week
                    AND m.kind = 'regular'
                    AND (m.home_points <> 0 OR m.away_points <> 0)
            )
        ORDER BY w.points {"DESC" if high else "ASC"}, w.year, w.week
        LIMIT 1
        """,
        {"manager_id": manager_id},
    )
    if row is None:
        return None
    game = _regular_game(int(row["year"]), int(row["week"]), manager_id)
    packed = {
        "year": int(row["year"]),
        "week": int(row["week"]),
        "points": row["points"],
        "scorer_id": row["manager_id"],
        "id": game["id"] if game else None,
        "label": "Highest week" if high else "Lowest week",
    }
    return packed


def _member_margin_game(manager_id: str, *, closest: bool) -> dict[str, Any] | None:
    row = fetchone(
        f"""
        SELECT matchup_id, year, week
        FROM v_record_matchups
        WHERE manager_id = %(manager_id)s OR opponent_id = %(manager_id)s
        ORDER BY abs_margin {"ASC" if closest else "DESC"}, year, week, matchup_id
        LIMIT 1
        """,
        {"manager_id": manager_id},
    )
    if row is None:
        return None
    game = _game_by_id(row["matchup_id"])
    if game is None:
        return None
    packed = _score_game(game)
    packed["label"] = "Closest" if closest else "Biggest blowout"
    packed["year"] = int(row["year"])
    packed["week"] = int(row["week"])
    return packed


def _member_longest_streak(manager_id: str, result: str) -> dict[str, Any] | None:
    return fetchone(
        """
        SELECT manager_id, length, start_year, start_week, end_year, end_week, is_current
        FROM v_streaks
        WHERE manager_id = %(manager_id)s AND result = %(result)s
        ORDER BY length DESC, start_year, start_week
        LIMIT 1
        """,
        {"manager_id": manager_id, "result": result},
    )


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


def lopsided_trades(limit: int = 10) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            transaction_id, year, week, winner_id,
            left_id, left_name, left_vorp, left_received,
            right_id, right_name, right_vorp, right_received, vorp_gap
        FROM v_trade_grades
        ORDER BY vorp_gap DESC, year, week, transaction_id
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    packed = []
    for index, row in enumerate(rows, 1):
        verdict = _trade_verdict(row.get("left_vorp"), row.get("right_vorp"))
        home, away = _trade_card_sides(row, winner_first=True)
        packed.append(
            {
                "rank": index,
                "transaction_id": row["transaction_id"],
                "year": row["year"],
                "week": row["week"],
                "verdict": verdict,
                "winner_id": row["winner_id"],
                "home": home,
                "away": away,
            }
        )
    return packed


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


def records_page() -> dict[str, Any]:
    return {
        "high_weeks": high_weeks(),
        "low_weeks": low_weeks(),
        "blowouts": blowouts(),
        "closest": closest_games(),
        "trades": lopsided_trades(),
        "draft_hits": _record_draft_picks(worst=False),
        "draft_misses": _record_draft_picks(worst=True),
        "drafts": _record_drafts(),
        "wire_adds": _record_wire_adds(),
        "wire_misses": _record_wire_misses(),
        "bench_weeks": _record_bench_weeks(),
        "bench_seasons": _record_bench_seasons(),
        "win_streaks": longest_streaks("win"),
        "loss_streaks": longest_streaks("loss"),
        "current_streaks": current_streaks(),
    }


def _record_draft_picks(*, worst: bool, limit: int = 10) -> list[dict[str, Any]]:
    order = "ASC" if worst else "DESC"
    return fetchall(
        f"""
        SELECT
            year, round, overall, manager_id, manager_name,
            player_id, player_name, position, keeper, vs_vorp, ros_vorp
        FROM v_draft_grades
        ORDER BY vs_vorp {order} NULLS LAST, year, overall
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def _record_drafts(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT year, manager_id, manager_name, picks, hits, vs_vorp, ros_vorp
        FROM v_draft_manager
        ORDER BY vs_vorp DESC NULLS LAST, year, manager_name
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def _record_wire_adds(limit: int = 10) -> list[dict[str, Any]]:
    return _wire_add_highlights(year=None, limit=limit)


def _record_wire_misses(limit: int = 10) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            year, week, manager_id, manager_name, reason,
            missed_transaction_id, missed_player_id, missed_player,
            won_transaction_id, won_player_id, won_player, vorp_gap
        FROM v_waiver_misses
        WHERE reason IN ('own_claim_order', 'lost_on_wire')
        ORDER BY vorp_gap DESC, year, week, missed_player
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    for row in rows:
        row["flag"] = "own order" if row["reason"] == "own_claim_order" else "lost on wire"
    return rows


def _record_bench_weeks(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            year, week, matchup_id, manager_id, manager_name,
            actual_points, optimal_points, left_on_bench, management_pct
        FROM v_management_weeks
        WHERE kind = 'regular'
        ORDER BY left_on_bench DESC NULLS LAST, year, week, manager_id
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def _record_bench_seasons(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            year, manager_id, manager_name, weeks,
            actual_points, optimal_points, left_on_bench, management_pct
        FROM v_management_season
        ORDER BY left_on_bench DESC NULLS LAST, year, manager_name
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def luck_career() -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            manager_id, display_name, seasons, games, wins, losses, ties,
            lucky_wins, unlucky_losses, net_luck,
            underdog_wins, favorite_losses, expected_wins, wins_vs_expected,
            CASE
                WHEN games = 0 THEN NULL
                ELSE (wins + 0.5 * ties) / games
            END AS win_pct
        FROM v_luck_career
        ORDER BY net_luck DESC, wins_vs_expected DESC NULLS LAST, display_name
        """
    )


def luck_seasons() -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            year, manager_id, display_name, games, wins, losses, ties,
            lucky_wins, unlucky_losses, net_luck,
            underdog_wins, favorite_losses, expected_wins, wins_vs_expected,
            CASE
                WHEN games = 0 THEN NULL
                ELSE (wins + 0.5 * ties) / games
            END AS win_pct
        FROM v_luck_season
        ORDER BY year DESC, net_luck DESC, wins_vs_expected DESC NULLS LAST, display_name
        """
    )


def luck_flagged_weeks() -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            year, week, matchup_id, manager_id, display_name,
            opponent_id, opponent_name, result, points, opp_points,
            pf_rank, teams, lucky_win, unlucky_loss
        FROM v_luck_weeks
        WHERE lucky_win OR unlucky_loss
        ORDER BY year DESC, week DESC, lucky_win DESC, display_name
        """
    )
    for row in rows:
        row["flag"] = "Lucky win" if row["lucky_win"] else "Unlucky loss"
    return rows


def universe_titles() -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            o.year,
            o.universe,
            o.matches_official,
            o.regular_season_champion AS rs_id,
            rs.display_name AS rs_name,
            o.champion AS champ_id,
            ch.display_name AS champ_name,
            oc.champion AS official_champ_id,
            och.display_name AS official_champ,
            oc.regular_season_champion AS official_rs_id,
            ors.display_name AS official_rs
        FROM v_universe_outcomes o
        LEFT JOIN managers rs ON rs.id = o.regular_season_champion
        LEFT JOIN managers ch ON ch.id = o.champion
        LEFT JOIN season_outcomes oc ON oc.year = o.year
        LEFT JOIN managers och ON och.id = oc.champion
        LEFT JOIN managers ors ON ors.id = oc.regular_season_champion
        ORDER BY o.year DESC,
            CASE o.universe WHEN 'never_median' THEN 0 ELSE 1 END
        """
    )
    by_year: dict[int, dict[str, Any]] = {}
    for row in rows:
        year = row["year"]
        packed = by_year.setdefault(
            year,
            {
                "year": year,
                "official_champ_id": row["official_champ_id"],
                "official_champ": row["official_champ"],
                "official_rs_id": row["official_rs_id"],
                "official_rs": row["official_rs"],
            },
        )
        key = "h2h" if row["universe"] == "never_median" else "median"
        packed[f"{key}_champ_id"] = row["champ_id"]
        packed[f"{key}_champ"] = row["champ_name"]
        packed[f"{key}_rs_id"] = row["rs_id"]
        packed[f"{key}_rs"] = row["rs_name"]
        packed[f"{key}_same"] = row["matches_official"]
    return list(by_year.values())


def players_index() -> dict[str, Any]:
    career = fetchall(
        """
        SELECT
            player_id, player_name, position, seasons, first_year, last_year,
            starts, bench_weeks, starter_points, rostered_weeks, fa_weeks,
            vorp, own_pct, times_drafted, times_added, times_traded
        FROM v_player_index
        ORDER BY starter_points DESC, vorp DESC, player_name
        """
    )
    seasons = fetchall(
        """
        SELECT
            year, player_id, player_name, position, rostered_weeks, starts,
            fa_weeks, points, started_points, vorp, own_pct, manager_id,
            owner_name, owned_weeks
        FROM v_player_season
        ORDER BY year DESC, started_points DESC, vorp DESC, player_name
        """
    )
    for row in career:
        row["avg"] = _per_start(row.get("starter_points"), row.get("starts"))
    for row in seasons:
        row["avg"] = _per_start(row.get("started_points"), row.get("starts"))
    return {
        "career": career,
        "seasons": seasons,
        "all_pro": _all_pro_years(seasons),
    }


def _per_start(points: Any, starts: Any) -> float | None:
    n = int(starts or 0)
    if n == 0 or points is None:
        return None
    return float(points) / n


def _all_pro(seasons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positions = ("QB", "RB", "WR", "TE", "K", "DEF")
    by_year: dict[int, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in seasons:
        pos = row["position"]
        if pos not in positions:
            continue
        by_year[int(row["year"])][pos].append(row)
    packed: list[dict[str, Any]] = []
    for year in sorted(by_year, reverse=True):
        for team, index in (("1st", 0), ("2nd", 1)):
            for pos in positions:
                group = sorted(
                    by_year[year][pos],
                    key=lambda row: (
                        float(row["started_points"] or 0),
                        float(row["vorp"] or 0),
                        int(row["starts"] or 0),
                    ),
                    reverse=True,
                )
                if index >= len(group):
                    continue
                pick = group[index]
                packed.append(
                    {
                        "year": year,
                        "team": team,
                        "position": pos,
                        "player_id": pick["player_id"],
                        "player_name": pick["player_name"],
                        "manager_id": pick["manager_id"],
                        "owner_name": pick["owner_name"],
                        "starts": pick["starts"],
                        "started_points": pick["started_points"],
                        "avg": pick["avg"],
                    }
                )
    return packed


def _all_pro_years(seasons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    years: list[dict[str, Any]] = []
    for row in _all_pro(seasons):
        year = row["year"]
        packed = grouped.get(year)
        if packed is None:
            packed = {"year": year, "first": [], "second": []}
            grouped[year] = packed
            years.append(packed)
        if row["team"] == "1st":
            packed["first"].append(row)
        else:
            packed["second"].append(row)
    return years


def player_page(player_id: str) -> dict[str, Any] | None:
    identity = fetchone(
        """
        SELECT
            player_id, player_name, position, seasons, first_year, last_year,
            starts, bench_weeks, starter_points, rostered_weeks, fa_weeks,
            vorp, own_pct, times_drafted, times_added, times_dropped, times_traded
        FROM v_player_index
        WHERE player_id = %(player_id)s
        """,
        {"player_id": player_id},
    )
    if identity is None:
        identity = fetchone(
            """
            SELECT
                v.player_id,
                max(v.player_name) AS player_name,
                v.position,
                count(*) AS seasons,
                min(v.year) AS first_year,
                max(v.year) AS last_year,
                sum(v.starts) AS starts,
                NULL::bigint AS bench_weeks,
                sum(v.points) AS starter_points,
                sum(v.rostered_weeks) AS rostered_weeks,
                sum(v.fa_weeks) AS fa_weeks,
                sum(v.vorp) AS vorp,
                CASE
                    WHEN sum(v.weeks) = 0 THEN NULL
                    ELSE sum(v.rostered_weeks)::double precision / sum(v.weeks)
                END AS own_pct,
                0 AS times_drafted,
                0 AS times_added,
                0 AS times_dropped,
                0 AS times_traded
            FROM v_vorp_season v
            WHERE v.player_id = %(player_id)s
            GROUP BY v.player_id, v.position
            """,
            {"player_id": player_id},
        )
    if identity is None:
        return None
    seasons = fetchall(
        """
        SELECT
            year, player_id, player_name, position, weeks, rostered_weeks,
            starts, fa_weeks, points, vorp, own_pct, manager_id, owner_name,
            owned_weeks
        FROM v_player_season
        WHERE player_id = %(player_id)s
        ORDER BY year DESC
        """,
        {"player_id": player_id},
    )
    weeks = fetchall(
        """
        SELECT
            p.year,
            p.week,
            p.points,
            p.rostered,
            p.started,
            p.manager_id,
            m.display_name AS manager_name,
            pw.matchup_id
        FROM v_pool_weeks p
        LEFT JOIN managers m ON m.id = p.manager_id
        LEFT JOIN LATERAL (
            SELECT matchup_id
            FROM v_player_weeks pw
            WHERE pw.year = p.year
                AND pw.week = p.week
                AND pw.player_id = p.player_id
                AND pw.manager_id IS NOT DISTINCT FROM p.manager_id
            LIMIT 1
        ) pw ON true
        WHERE p.player_id = %(player_id)s
        ORDER BY p.year, p.week
        """,
        {"player_id": player_id},
    )
    draft = fetchall(
        """
        SELECT year, overall, round, manager_id, manager_name, keeper
        FROM v_draft
        WHERE player_id = %(player_id)s
        ORDER BY year, overall
        """,
        {"player_id": player_id},
    )
    owners = fetchall(
        """
        SELECT year, manager_id, manager_name, weeks, starts, points
        FROM v_ownership_season
        WHERE player_id = %(player_id)s
        ORDER BY year DESC, weeks DESC, manager_id
        """,
        {"player_id": player_id},
    )
    return {
        "player": identity,
        "seasons": seasons,
        "weeks": weeks,
        "stints": _ownership_stints(weeks),
        "draft": draft,
        "owners": owners,
    }


def _ownership_stints(weeks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stints: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in weeks:
        owner_id = row["manager_id"] if row["rostered"] else None
        key = (row["year"], owner_id)
        if current and current["key"] == key:
            current["end_week"] = row["week"]
            current["weeks"] += 1
            if row["started"]:
                current["starts"] += 1
            current["points"] += float(row["points"] or 0)
            continue
        if current:
            stints.append(current)
        current = {
            "key": key,
            "year": row["year"],
            "manager_id": owner_id,
            "manager_name": row["manager_name"] if owner_id else None,
            "start_week": row["week"],
            "end_week": row["week"],
            "weeks": 1,
            "starts": 1 if row["started"] else 0,
            "points": float(row["points"] or 0),
        }
    if current:
        stints.append(current)
    for stint in stints:
        start = stint["start_week"]
        end = stint["end_week"]
        stint["span"] = f"W{start}" if start == end else f"W{start}–W{end}"
        del stint["key"]
    return stints

