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


def season_page(year: int) -> dict[str, Any] | None:
    current = season_row(year)
    if current is None:
        return None
    table = standings(year)
    through = current.get("through_week")
    draft = _season_draft(year)
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
        "draft_hits": draft[0],
        "draft_misses": draft[1],
    }


def _season_universes(year: int) -> dict[str, Any] | None:
    packed = next((row for row in universe_titles() if row["year"] == year), None)
    if packed is None:
        return None
    if not packed.get("official_champ") and not packed.get("h2h_champ") and not packed.get("median_champ"):
        return None
    return packed


def _season_notables(year: int) -> dict[str, Any]:
    return {
        "high": _season_extreme_week(year, high=True),
        "low": _season_extreme_week(year, high=False),
        "blowout": _season_margin_game(year, closest=False),
        "closest": _season_margin_game(year, closest=True),
        "lucky": _season_luck_flag(year, lucky=True),
        "unlucky": _season_luck_flag(year, lucky=False),
    }


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
    packed["week"] = int(row["week"])
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


def _season_wire(year: int) -> dict[str, list[dict[str, Any]]]:
    adds = _season_wire_adds(year)
    misses = fetchall(
        """
        SELECT
            year, week, manager_id, manager_name, reason,
            missed_seq, missed_player_id, missed_player, missed_position,
            missed_vorp, won_seq, won_player_id, won_player, won_vorp, vorp_gap
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
            lost_seq, lost_player_id, lost_player, lost_position, lost_vorp,
            won_seq, won_player_id, won_player, won_vorp, vorp_gap
        FROM v_waiver_dodges
        WHERE year = %(year)s
        ORDER BY vorp_gap DESC, week, lost_player
        LIMIT 5
        """,
        {"year": year},
    )
    return {"adds": adds, "misses": misses, "dodges": dodges}


def _season_wire_adds(year: int) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        WITH pool AS (
            SELECT week, player_id, position, points, started
            FROM player_week_scores
            WHERE year = %(year)s
        ),
        starters AS (
            SELECT week, position, count(*) AS n_starters
            FROM pool
            WHERE started AND position IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')
            GROUP BY week, position
        ),
        ranked AS (
            SELECT week, position, points,
                row_number() OVER (
                    PARTITION BY week, position
                    ORDER BY points DESC, player_id
                ) AS rnk
            FROM pool
            WHERE position IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')
        ),
        repl AS (
            SELECT s.week, s.position, r.points AS replacement
            FROM starters s
            JOIN ranked r
                ON r.week = s.week AND r.position = s.position
                AND r.rnk = greatest(s.n_starters, 1)
        )
        SELECT
            mv.week, mv.type, mv.manager_id, mv.manager_name,
            mv.player_id, mv.player_name, mv.position, mv.bid,
            coalesce(sum(pw.points) FILTER (WHERE pw.started), 0) AS league_ros,
            coalesce(sum(pw.points - r.replacement) FILTER (
                WHERE pw.started AND r.replacement IS NOT NULL
            ), 0) AS league_vorp
        FROM v_moves mv
        LEFT JOIN pool pw
            ON pw.player_id = mv.player_id AND pw.week >= mv.week
        LEFT JOIN repl r
            ON r.week = pw.week AND r.position = pw.position
        WHERE mv.year = %(year)s
            AND mv.type IN ('waiver', 'free_agent')
            AND mv.direction = 'add'
            AND mv.status = 'complete'
        GROUP BY
            mv.transaction_id, mv.week, mv.type, mv.manager_id, mv.manager_name,
            mv.player_id, mv.player_name, mv.position, mv.bid
        ORDER BY league_vorp DESC, week, player_name
        LIMIT 20
        """,
        {"year": year},
    )
    seen: set[str] = set()
    packed: list[dict[str, Any]] = []
    for row in rows:
        player_id = row["player_id"]
        if player_id in seen:
            continue
        seen.add(player_id)
        row["kind"] = "wav" if row["type"] == "waiver" else "FA"
        packed.append(row)
        if len(packed) == 5:
            break
    return packed


def _season_draft(year: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # Season VORP vs that round's drafted average — v_draft_grades is too slow here.
    rows = fetchall(
        """
        SELECT
            d.year, d.round, d.overall, d.manager_id, d.manager_name,
            d.player_id, d.player_name, d.position,
            p.vorp AS ros_vorp,
            p.vorp - avg(p.vorp) OVER (PARTITION BY d.round) AS vs_vorp
        FROM v_draft d
        LEFT JOIN v_vorp_season p
            ON p.year = d.year AND p.player_id = d.player_id
        WHERE d.year = %(year)s
        ORDER BY vs_vorp DESC NULLS LAST, overall
        """,
        {"year": year},
    )
    ranked = [row for row in rows if row.get("vs_vorp") is not None]
    hits = ranked[:5]
    rest = ranked[5:]
    misses = list(reversed(rest[-5:])) if rest else []
    return hits, misses


def week_slate(year: int, week: int) -> dict[str, Any] | None:
    games = _week_games(year, week)
    if not games:
        return None
    ranks = _week_ranks(year, week)
    packed = [_score_game(game) for game in games]
    for game in packed:
        _apply_week_context(game, ranks)
    return {**_week_nav(year, week), "groups": _group_games(packed)}


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

