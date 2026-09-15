from __future__ import annotations

from collections import defaultdict
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

from ..db import database_url
from . import brackets
from .names import flavor_team, manager_hue

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

SCORING_LABELS = {
    "pass_yd": "Pass yards",
    "pass_td": "Pass TD",
    "pass_int": "INT",
    "pass_2pt": "Pass 2-pt",
    "pass_int_td": "Pick-six",
    "rush_yd": "Rush yards",
    "rush_td": "Rush TD",
    "rush_2pt": "Rush 2-pt",
    "rec": "Reception",
    "rec_yd": "Rec yards",
    "rec_td": "Rec TD",
    "rec_2pt": "Rec 2-pt",
    "fum": "Fumble",
    "fum_lost": "Fumble lost",
    "fum_td": "Fumble TD",
    "bonus_rec_te": "TE rec bonus",
    "bonus_rec_rb": "RB rec bonus",
    "bonus_rec_wr": "WR rec bonus",
    "bonus_pass_yd_300": "300 pass-yd bonus",
    "bonus_rush_yd_100": "100 rush-yd bonus",
    "bonus_rec_yd_100": "100 rec-yd bonus",
    "fgm": "FG made",
    "fgm_0_19": "FG 0–19",
    "fgm_20_29": "FG 20–29",
    "fgm_30_39": "FG 30–39",
    "fgm_40_39": "FG 40–39",
    "fgm_40_49": "FG 40–49",
    "fgm_50p": "FG 50+",
    "xpm": "XP made",
    "xpmiss": "XP miss",
    "fgmiss": "FG miss",
    "st_td": "ST TD",
    "def_td": "D/ST TD",
    "sack": "Sack",
    "int": "D/ST INT",
    "fum_rec": "Fumble recovery",
    "safe": "Safety",
    "blk_kick": "Blocked kick",
    "pts_allow_0": "0 PA",
    "pts_allow_1_6": "1–6 PA",
    "pts_allow_7_13": "7–13 PA",
    "pts_allow_14_20": "14–20 PA",
    "pts_allow_21_27": "21–27 PA",
    "pts_allow_28_34": "28–34 PA",
    "pts_allow_35p": "35+ PA",
    "yds_allow_0_100": "0–100 yards allowed",
    "yds_allow_100_199": "100–199 yards allowed",
    "yds_allow_200_299": "200–299 yards allowed",
    "pts_allow": "Points allowed",
    "0": "Pass yards",
    "1": "Pass TD",
    "2": "Pass 2-pt",
    "3": "INT",
    "4": "Pass INT TD",
    "20": "Rush yards",
    "21": "Rush TD",
    "23": "Rush 2-pt",
    "24": "Rush 1st down",
    "25": "Rush fumble",
    "42": "Rec yards",
    "43": "Rec TD",
    "53": "Reception",
    "72": "Fumble lost",
    "74": "Fumble TD",
    "201": "2-pt conversion",
}


def _scoring_label(key: Any) -> str:
    text = str(key)
    return SCORING_LABELS.get(text, text.replace("_", " "))


def _scoring_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


RECORDS_TOP = 10
_request_conn: ContextVar[psycopg.Connection | None] = ContextVar("hub_conn", default=None)

_SCORED_REGULAR = """
EXISTS (
    SELECT 1
    FROM matchups m
    WHERE m.year = w.year AND m.week = w.week
        AND m.kind = 'regular'
        AND (m.home_points <> 0 OR m.away_points <> 0)
)
"""


def connect() -> psycopg.Connection:
    try:
        return psycopg.connect(
            database_url(),
            row_factory=dict_row,
            autocommit=True,
        )
    except psycopg.OperationalError as exc:
        raise HTTPException(
            status_code=503,
            detail="Cannot reach Postgres. Start Docker Desktop, then `docker compose up -d`.",
        ) from exc


def bind_connection(conn: psycopg.Connection) -> Token:
    return _request_conn.set(conn)


def unbind_connection(token: Token) -> None:
    _request_conn.reset(token)


def fetchall(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    conn = _request_conn.get()
    try:
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())
        with connect() as owned:
            with owned.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())
    except psycopg.errors.UndefinedTable as exc:
        raise HTTPException(
            status_code=503,
            detail="Analysis views are missing. Run `uv run nu-choate-league load`.",
        ) from exc


def fetchone(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rows = fetchall(sql, params)
    return rows[0] if rows else None


def list_seasons() -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            s.year,
            s.platform,
            s.vs_median,
            s.name,
            oc.id AS champion_id,
            oc.display_name AS champion,
            oc_ts.team_name AS champion_team,
            ru.display_name AS runner_up,
            rs.display_name AS regular_season_champion,
            mp.display_name AS most_points,
            lc.id AS last_chair_id,
            lc.display_name AS last_chair,
            lc_ts.team_name AS last_chair_team
        FROM seasons s
        LEFT JOIN season_outcomes o ON o.year = s.year
        LEFT JOIN managers oc ON oc.id = o.champion
        LEFT JOIN team_seasons oc_ts
            ON oc_ts.year = s.year AND oc_ts.manager_id = o.champion
        LEFT JOIN managers ru ON ru.id = o.runner_up
        LEFT JOIN managers rs ON rs.id = o.regular_season_champion
        LEFT JOIN managers mp ON mp.id = o.most_points
        LEFT JOIN LATERAL (
            SELECT st.manager_id
            FROM v_standings_official st
            WHERE st.year = s.year
                AND st.wins + st.losses + st.ties > 0
            ORDER BY st.rank DESC, st.manager_id
            LIMIT 1
        ) last ON true
        LEFT JOIN managers lc ON lc.id = last.manager_id
        LEFT JOIN team_seasons lc_ts
            ON lc_ts.year = s.year AND lc_ts.manager_id = last.manager_id
        ORDER BY s.year DESC
        """
    )
    for row in rows:
        row["champion_hue"] = manager_hue(row.get("champion_id"))
        row["last_chair_hue"] = manager_hue(row.get("last_chair_id"))
    return rows


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
            mp.display_name AS most_points,
            lc.id AS last_chair_id,
            lc.display_name AS last_chair,
            s.scoring_settings,
            s.faab_budget
        FROM seasons s
        LEFT JOIN season_outcomes o ON o.year = s.year
        LEFT JOIN managers oc ON oc.id = o.champion
        LEFT JOIN managers ru ON ru.id = o.runner_up
        LEFT JOIN managers rs ON rs.id = o.regular_season_champion
        LEFT JOIN managers mp ON mp.id = o.most_points
        LEFT JOIN LATERAL (
            SELECT st.manager_id
            FROM v_standings_official st
            WHERE st.year = s.year
                AND st.wins + st.losses + st.ties > 0
            ORDER BY st.rank DESC, st.manager_id
            LIMIT 1
        ) last ON true
        LEFT JOIN managers lc ON lc.id = last.manager_id
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
            ap.win_pct AS all_play_win_pct,
            lk.net_luck,
            lk.wins_vs_expected,
            mg.management_pct,
            mg.left_on_bench,
            ch.first_chair,
            ch.last_chair,
            (so.champion = o.manager_id) AS champion,
            (so.runner_up = o.manager_id) AS runner_up,
            (so.regular_season_champion = o.manager_id) AS rs_champ,
            (po.manager_id IS NOT NULL) AS playoff
        FROM v_standings_official o
        LEFT JOIN season_outcomes so ON so.year = o.year
        LEFT JOIN season_playoff_managers po
            ON po.year = o.year AND po.manager_id = o.manager_id
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
        LEFT JOIN v_luck_season lk
            ON lk.year = o.year AND lk.manager_id = o.manager_id
        LEFT JOIN v_management_season mg
            ON mg.year = o.year AND mg.manager_id = o.manager_id
        LEFT JOIN v_chair_season ch
            ON ch.year = o.year AND ch.manager_id = o.manager_id
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
        row["hue"] = manager_hue(row["manager_id"])
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
    player_seasons = _player_seasons_year(year)
    through = current.get("through_week")
    draft = _season_draft(year)
    lineups = _season_lineups(year)
    trades = _season_trades(year)
    wire = _season_wire(year)
    return {
        "current": current,
        "seasons": list_seasons(),
        "standings": table,
        "teams": len(table),
        "now_week": int(through) if through else None,
        "schedule": season_schedule(year),
        "universes": _season_universes(year),
        "notables": _season_notables(year),
        "trades": trades,
        "wire": wire,
        "draft": draft,
        "lineups": lineups,
        "scoring": _season_scoring(year),
        "power": _power_board(year),
        "heat": _week_rank_heat(year),
        "race": _points_race_chart(year),
        "desk": _schedule_desk(year),
        "marks": week_marks_season(year),
        "median_tax": median_tax(year),
        "path": _playoff_path(year),
        "ranks": universe_ranks(year),
        "luck_plaques": luck_plaques(table, href=f"/seasons/{year}"),
        "all_pro": _honor_pack(
            player_seasons,
            points_key="started_points",
            tie_keys=("vorp", "starts"),
        ),
        "all_bench": _honor_pack(
            player_seasons,
            points_key="bench_points",
            tie_keys=("bench_weeks",),
            skip_empty=True,
        ),
        "highlights": _season_highlight_chips(year, draft=draft, wire=wire, trades=trades),
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
    packed = next(iter(universe_titles(year)), None)
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
    return {
        "high": high,
        "low": low,
        "blowout": blowout,
        "closest": closest,
        "lucky": _season_luck_flag(year, lucky=True),
        "unlucky": _season_luck_flag(year, lucky=False),
    }


def _stamp_if_top(
    notable: dict[str, Any] | None,
    rank: Any,
    href: str,
    kind: str,
) -> None:
    if notable is None or rank is None:
        return
    rank = int(rank)
    if rank < 1 or rank > RECORDS_TOP:
        return
    notable["alltime_rank"] = rank
    notable["alltime_label"] = f"{_ordinal(rank)}-{kind}"
    notable["records_href"] = href


def _week_alltime_rank(
    *,
    high: bool,
    year: int,
    week: int,
    manager_id: str,
    points: Any,
) -> int | None:
    cmp = ">" if high else "<"
    row = fetchone(
        f"""
        SELECT count(*) + 1 AS rank
        FROM v_record_weeks w
        WHERE {_SCORED_REGULAR}
            AND (
                w.points {cmp} %(points)s
                OR (
                    w.points = %(points)s
                    AND (w.year, w.week, w.manager_id)
                        < (%(year)s, %(week)s, %(manager_id)s)
                )
            )
        """,
        {
            "points": points,
            "year": year,
            "week": week,
            "manager_id": manager_id,
        },
    )
    return int(row["rank"]) if row else None


def _season_extreme_week(year: int, *, high: bool) -> dict[str, Any] | None:
    row = fetchone(
        f"""
        SELECT w.year, w.week, w.manager_id, w.display_name, w.points
        FROM v_record_weeks w
        WHERE w.year = %(year)s
            AND w.paired
            AND {_SCORED_REGULAR}
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
    _stamp_if_top(
        packed,
        _week_alltime_rank(
            high=high,
            year=int(row["year"]),
            week=int(row["week"]),
            manager_id=row["manager_id"],
            points=row["points"],
        ),
        "/records#high" if high else "/records#low",
        "highest" if high else "lowest",
    )
    return packed


def _season_margin_game(year: int, *, closest: bool) -> dict[str, Any] | None:
    rank_col = "closest_rank" if closest else "blowout_rank"
    row = fetchone(
        f"""
        SELECT matchup_id, year, week, {rank_col} AS alltime_rank
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
    _stamp_if_top(
        packed,
        row["alltime_rank"],
        "/records#closest" if closest else "/records#blowouts",
        "closest" if closest else "biggest",
    )
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
    row["flag"] = "H2H enjoyer" if lucky else "Median enjoyer"
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
        return {"kind": "even", "label": "FA"}
    if status == "complete":
        return {"kind": "won", "label": "won"}
    note = str(row.get("note") or "")
    lower = note.lower()
    if "claimed by another" in lower or note == "FAILED_INVALIDPLAYERSOURCE":
        return {"kind": "lost", "label": "lost on wire"}
    if "too many players" in lower or note == "FAILED_ROSTERLIMIT":
        return {"kind": "order", "label": "roster limit"}
    if row.get("type") == "free_agent":
        return {"kind": "even", "label": "FA"}
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
    for bucket in buckets.values():
        bucket["rows"] = sorted(
            bucket["claims"] + bucket["fa"],
            key=lambda row: (
                row.get("at") is None,
                row.get("at") or 0,
                row.get("player_name") or "",
            ),
        )
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
            ros_vorp, vs_vorp, ros_starts, hit, adp, times_drafted, pick_vs_adp
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
        "card": week_card(year, week),
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
    rows = fetchall(
        """
        SELECT
            c.manager_id, c.display_name, c.seasons, c.wins, c.losses, c.ties,
            c.points_for, c.win_pct, c.titles, c.runner_up,
            c.regular_season_titles, c.most_points_titles, c.playoff_appearances,
            s.result AS streak_result, s.length AS streak_length,
            ap.wins AS all_play_wins, ap.losses AS all_play_losses, ap.ties AS all_play_ties,
            ap.win_pct AS all_play_win_pct,
            po.wins AS playoff_wins, po.losses AS playoff_losses, po.ties AS playoff_ties,
            po.title_games,
            ch.first_chair, ch.last_chair, ch.benched_first_chair,
            po_last.last_playoff,
            hh.wins AS h2h_wins, hh.losses AS h2h_losses, hh.ties AS h2h_ties,
            hh.win_pct AS h2h_win_pct,
            md.wins AS median_wins, md.losses AS median_losses, md.ties AS median_ties,
            md.win_pct AS median_win_pct,
            lk.net_luck, lk.wins_vs_expected, lk.lucky_wins, lk.unlucky_losses,
            (SELECT max(year) FROM seasons) AS latest_year
        FROM v_career c
        LEFT JOIN LATERAL (
            SELECT result, length
            FROM v_streaks
            WHERE manager_id = c.manager_id AND is_current
            LIMIT 1
        ) s ON true
        LEFT JOIN v_all_play_career ap ON ap.manager_id = c.manager_id
        LEFT JOIN v_playoff_career po ON po.manager_id = c.manager_id
        LEFT JOIN v_chair_career ch ON ch.manager_id = c.manager_id
        LEFT JOIN (
            SELECT manager_id, max(year) AS last_playoff
            FROM season_playoff_managers
            GROUP BY manager_id
        ) po_last ON po_last.manager_id = c.manager_id
        LEFT JOIN v_career_h2h hh ON hh.manager_id = c.manager_id
        LEFT JOIN v_career_median md ON md.manager_id = c.manager_id
        LEFT JOIN v_luck_career lk ON lk.manager_id = c.manager_id
        ORDER BY c.titles DESC, c.win_pct DESC NULLS LAST, c.points_for DESC, c.manager_id
        """
    )
    for row in rows:
        games = int(row["wins"] or 0) + int(row["losses"] or 0) + int(row["ties"] or 0)
        row["pf_per_game"] = float(row["points_for"]) / games if games else None
        row["all_play"] = _maybe_record(
            row.get("all_play_wins"), row.get("all_play_losses"), row.get("all_play_ties")
        )
        row["playoff"] = _maybe_record(
            row.get("playoff_wins"), row.get("playoff_losses"), row.get("playoff_ties")
        )
        row["h2h"] = _maybe_record(row.get("h2h_wins"), row.get("h2h_losses"), row.get("h2h_ties"))
        row["median"] = _maybe_record(
            row.get("median_wins"), row.get("median_losses"), row.get("median_ties")
        )
        row["hue"] = manager_hue(row["manager_id"])
        latest = row.get("latest_year")
        last_po = row.get("last_playoff")
        if latest is None:
            row["playoff_drought"] = None
        elif last_po is None:
            row["playoff_drought"] = int(row["seasons"] or 0)
        else:
            row["playoff_drought"] = int(latest) - int(last_po)
    return rows


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
        "chairs": fetchone(
            """
            SELECT first_chair, last_chair, benched_first_chair
            FROM v_chair_career
            WHERE manager_id = %(manager_id)s
            """,
            {"manager_id": manager_id},
        ),
        "all_play": fetchone(
            """
            SELECT wins, losses, ties, win_pct
            FROM v_all_play_career
            WHERE manager_id = %(manager_id)s
            """,
            {"manager_id": manager_id},
        ),
        "platform": _member_platform_split(manager_id),
        "marks": _member_marks(manager_id, person["display_name"]),
        "kind_order": list(MARK_KIND_ORDER),
        "labels": MARK_LABELS,
        "meta": MARK_META,
    }


def _member_marks(manager_id: str, display_name: str | None = None) -> dict[str, Any] | None:
    rows = fetchall(
        """
        SELECT kind, weeks
        FROM v_marks_holders
        WHERE manager_id = %(manager_id)s
        """,
        {"manager_id": manager_id},
    )
    if not rows:
        return None
    packed: dict[str, Any] = {
        "manager_id": manager_id,
        "display_name": display_name or "",
        "total": 0,
        "hue": manager_hue(manager_id),
    }
    for row in rows:
        packed[row["kind"]] = int(row["weeks"])
        packed["total"] += int(row["weeks"])
    return packed


def _member_finishes(manager_id: str) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            s.manager_id, s.year, s.rank, s.team_name, s.wins, s.losses, s.ties,
            s.points_for, s.win_pct,
            (o.champion = s.manager_id) AS champion,
            (o.runner_up = s.manager_id) AS runner_up,
            (o.regular_season_champion = s.manager_id) AS rs_champ,
            (o.most_points = s.manager_id) AS most_points,
            (p.manager_id IS NOT NULL) AS playoff,
            lk.net_luck, lk.wins_vs_expected,
            ch.first_chair, ch.last_chair
        FROM v_standings_official s
        LEFT JOIN season_outcomes o ON o.year = s.year
        LEFT JOIN season_playoff_managers p
            ON p.year = s.year AND p.manager_id = s.manager_id
        LEFT JOIN v_luck_season lk
            ON lk.year = s.year AND lk.manager_id = s.manager_id
        LEFT JOIN v_chair_season ch
            ON ch.year = s.year AND ch.manager_id = s.manager_id
        WHERE s.manager_id = %(manager_id)s
        ORDER BY s.year
        """,
        {"manager_id": manager_id},
    )
    for row in rows:
        row["hue"] = manager_hue(row["manager_id"])
        row["record"] = _record(int(row["wins"] or 0), int(row["losses"] or 0), int(row["ties"] or 0))
    return rows


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
                "href": f"/versus/{manager_id}/{row['left_id'] if flipped else row['right_id']}",
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
    return {
        "high": _member_extreme_week(manager_id, high=True),
        "low": _member_extreme_week(manager_id, high=False),
        "blowout": _member_margin_game(manager_id, closest=False),
        "closest": _member_margin_game(manager_id, closest=True),
        "win_streak": _member_longest_streak(manager_id, "win"),
        "loss_streak": _member_longest_streak(manager_id, "loss"),
    }


def _member_extreme_week(manager_id: str, *, high: bool) -> dict[str, Any] | None:
    row = fetchone(
        f"""
        SELECT w.year, w.week, w.manager_id, w.display_name, w.points
        FROM v_record_weeks w
        WHERE w.manager_id = %(manager_id)s
            AND w.paired
            AND {_SCORED_REGULAR}
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
    _stamp_if_top(
        packed,
        _week_alltime_rank(
            high=high,
            year=int(row["year"]),
            week=int(row["week"]),
            manager_id=manager_id,
            points=row["points"],
        ),
        "/records#high" if high else "/records#low",
        "highest" if high else "lowest",
    )
    return packed


def _member_margin_game(manager_id: str, *, closest: bool) -> dict[str, Any] | None:
    rank_col = "closest_rank" if closest else "blowout_rank"
    row = fetchone(
        f"""
        SELECT matchup_id, year, week, {rank_col} AS alltime_rank
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
    _stamp_if_top(
        packed,
        row["alltime_rank"],
        "/records#closest" if closest else "/records#blowouts",
        "closest" if closest else "biggest",
    )
    return packed


def _member_longest_streak(manager_id: str, result: str) -> dict[str, Any] | None:
    row = fetchone(
        """
        SELECT manager_id, length, start_year, start_week, end_year, end_week,
               is_current, streak_rank
        FROM (
            SELECT
                manager_id, length, start_year, start_week, end_year, end_week,
                is_current, result,
                row_number() OVER (
                    PARTITION BY result
                    ORDER BY length DESC, start_year, start_week, manager_id
                ) AS streak_rank
            FROM v_streaks
        ) ranked
        WHERE manager_id = %(manager_id)s AND result = %(result)s
        ORDER BY length DESC, start_year, start_week
        LIMIT 1
        """,
        {"manager_id": manager_id, "result": result},
    )
    if row is None:
        return None
    _stamp_if_top(
        row,
        row["streak_rank"],
        "/records#wins" if result == "win" else "/records#losses",
        "longest",
    )
    return row


def high_weeks(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        f"""
        SELECT w.year, w.week, w.manager_id, w.display_name, w.points
        FROM v_record_weeks w
        WHERE {_SCORED_REGULAR}
        ORDER BY w.points DESC, w.year, w.week, w.manager_id
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def low_weeks(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        f"""
        SELECT w.year, w.week, w.manager_id, w.display_name, w.points
        FROM v_record_weeks w
        WHERE {_SCORED_REGULAR}
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
        row["flag"] = "H2H enjoyer" if row["lucky_win"] else "Median enjoyer"
    return rows


def universe_titles(year: int | None = None) -> list[dict[str, Any]]:
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
        WHERE (%(year)s::integer IS NULL OR o.year = %(year)s)
        ORDER BY o.year DESC,
            CASE o.universe WHEN 'never_median' THEN 0 ELSE 1 END
        """,
        {"year": year},
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


def universe_ranks(year: int | None = None) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            o.year,
            o.manager_id,
            o.display_name,
            o.rank AS official_rank,
            h.rank AS h2h_rank,
            med.rank AS median_rank
        FROM v_standings_official o
        LEFT JOIN v_universe_standings h
            ON h.year = o.year AND h.manager_id = o.manager_id AND h.universe = 'never_median'
        LEFT JOIN v_universe_standings med
            ON med.year = o.year AND med.manager_id = o.manager_id AND med.universe = 'always_median'
        WHERE (%(year)s::integer IS NULL OR o.year = %(year)s)
            AND (o.wins + o.losses + o.ties > 0 OR o.points_for > 0)
        ORDER BY o.year DESC, o.rank, o.manager_id
        """,
        {"year": year},
    )
    counts: dict[int, int] = {}
    for row in rows:
        row["hue"] = manager_hue(row["manager_id"])
        counts[row["year"]] = counts.get(row["year"], 0) + 1
    for row in rows:
        teams = counts.get(row["year"]) or 1
        row["official_heat"] = _rank_heat(row.get("official_rank"), teams)
        row["h2h_heat"] = _rank_heat(row.get("h2h_rank"), teams)
        row["median_heat"] = _rank_heat(row.get("median_rank"), teams)
    return rows


def _rank_heat(rank: Any, teams: int) -> float | None:
    if rank is None or teams <= 1:
        return None
    return (int(rank) - 1) / (teams - 1)


def luck_plaques(rows: list[dict[str, Any]], *, href: str | None = None) -> list[dict[str, Any]]:
    scored = [row for row in rows if row.get("net_luck") is not None]
    if not scored:
        return []
    lucky = max(
        scored,
        key=lambda row: (int(row["net_luck"]), float(row.get("wins_vs_expected") or 0)),
    )
    unlucky = min(
        scored,
        key=lambda row: (int(row["net_luck"]), float(row.get("wins_vs_expected") or 0)),
    )
    chips = [_luck_plaque(lucky, "Luckiest", "high", href)]
    if unlucky["manager_id"] != lucky["manager_id"]:
        chips.append(_luck_plaque(unlucky, "Unluckiest", "low", href))
    return chips


def _luck_plaque(
    row: dict[str, Any], kicker: str, polarity: str, href: str | None
) -> dict[str, Any]:
    vs_exp = row.get("wins_vs_expected")
    return {
        "kicker": kicker,
        "who": row.get("display_name") or row.get("manager_name"),
        "who_id": row["manager_id"],
        "figure": f"{int(row['net_luck']):+d}",
        "meta": f"{float(vs_exp):+.1f} vsExp" if vs_exp is not None else None,
        "href": href,
        "polarity": polarity,
        "hue": manager_hue(row["manager_id"]),
    }


def management_career(limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
            m.manager_id, m.manager_name AS display_name, m.seasons, m.weeks,
            m.actual_points, m.optimal_points, m.left_on_bench, m.management_pct,
            s.sat_starter
        FROM v_management_career m
        LEFT JOIN (
            SELECT manager_id, count(*) AS sat_starter
            FROM v_start_sit
            WHERE call = 'should_start' AND kind = 'regular'
            GROUP BY manager_id
        ) s ON s.manager_id = m.manager_id
        ORDER BY m.management_pct DESC NULLS LAST, m.manager_name
    """
    if limit is not None:
        sql += " LIMIT %(limit)s"
        rows = fetchall(sql, {"limit": limit})
    else:
        rows = fetchall(sql)
    for row in rows:
        row["hue"] = manager_hue(row["manager_id"])
    return rows


def moves_log(year: int) -> dict[str, Any] | None:
    current = season_row(year)
    if current is None:
        return None
    rows = fetchall(
        """
        SELECT
            transaction_id, year, week, type, status, at, direction,
            manager_id, manager_name, player_id, player_name, position,
            bid, priority, seq
        FROM v_moves
        WHERE year = %(year)s
            AND type IN ('trade', 'waiver', 'free_agent')
        ORDER BY
            week,
            coalesce(at, 0),
            transaction_id,
            CASE direction WHEN 'add' THEN 0 ELSE 1 END,
            manager_name,
            player_name
        """,
        {"year": year},
    )
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        key = row["transaction_id"]
        packed = grouped.get(key)
        if packed is None:
            packed = {
                "id": key,
                "year": year,
                "week": row["week"],
                "type": row["type"],
                "status": row["status"],
                "at": row["at"],
                "adds": [],
                "drops": [],
                "href": _move_href(year, row["type"], key),
            }
            grouped[key] = packed
            order.append(key)
        bag = packed["adds"] if row["direction"] == "add" else packed["drops"]
        bag.append(row)
    return {
        "current": current,
        "seasons": list_seasons(),
        "moves": [grouped[key] for key in order],
    }


def _move_href(year: int, kind: str, transaction_id: str) -> str | None:
    if kind == "trade":
        return f"/seasons/{year}/trades/{transaction_id}"
    if kind in {"waiver", "free_agent"}:
        return f"/seasons/{year}/wire/{transaction_id}"
    return None


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
    }


def _per_start(points: Any, starts: Any) -> float | None:
    n = int(starts or 0)
    if n == 0 or points is None:
        return None
    return float(points) / n


def _honor_teams(
    seasons: list[dict[str, Any]],
    *,
    points_key: str,
    tie_keys: tuple[str, ...],
    skip_empty: bool = False,
) -> list[dict[str, Any]]:
    """1st/2nd team at each position. All-pro is starter PF; all-bench is bench PF."""
    positions = ("QB", "RB", "WR", "TE", "K", "DEF")
    by_year: dict[int, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in seasons:
        pos = row["position"]
        if pos not in positions:
            continue
        if skip_empty and float(row.get(points_key) or 0) <= 0:
            continue
        by_year[int(row["year"])][pos].append(row)
    packed: list[dict[str, Any]] = []
    for year in sorted(by_year, reverse=True):
        for team, index in (("1st", 0), ("2nd", 1)):
            for pos in positions:
                group = sorted(
                    by_year[year][pos],
                    key=lambda row: tuple(
                        float(row.get(key) or 0) for key in (points_key, *tie_keys)
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
                        "started_points": pick.get("started_points"),
                        "bench_weeks": pick.get("bench_weeks"),
                        "bench_points": pick.get("bench_points"),
                        "avg": pick.get("avg"),
                    }
                )
    return packed


def _honor_years(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    years: list[dict[str, Any]] = []
    for row in rows:
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


def _honor_pack(
    seasons: list[dict[str, Any]],
    *,
    points_key: str,
    tie_keys: tuple[str, ...],
    skip_empty: bool = False,
) -> dict[str, Any] | None:
    packed = _honor_years(
        _honor_teams(seasons, points_key=points_key, tie_keys=tie_keys, skip_empty=skip_empty)
    )
    return packed[0] if packed else None


def _player_seasons_year(year: int) -> list[dict[str, Any]]:
    seasons = fetchall(
        """
        SELECT
            year, player_id, player_name, position, rostered_weeks, starts,
            fa_weeks, points, started_points, bench_weeks, bench_points, vorp,
            own_pct, manager_id, owner_name, owned_weeks
        FROM v_player_season
        WHERE year = %(year)s
        ORDER BY started_points DESC, vorp DESC, player_name
        """,
        {"year": year},
    )
    for row in seasons:
        row["avg"] = _per_start(row.get("started_points"), row.get("starts"))
    return seasons


def all_pro_for_year(year: int) -> dict[str, Any] | None:
    return _honor_pack(
        _player_seasons_year(year),
        points_key="started_points",
        tie_keys=("vorp", "starts"),
    )


def all_bench_for_year(year: int) -> dict[str, Any] | None:
    return _honor_pack(
        _player_seasons_year(year),
        points_key="bench_points",
        tie_keys=("bench_weeks",),
        skip_empty=True,
    )


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
    lines = _player_stat_lines(player_id)
    by_line = {(row["year"], row["week"]): row for row in lines}
    for row in weeks:
        row["line"] = by_line.get((row["year"], row["week"]))
    return {
        "player": identity,
        "seasons": seasons,
        "weeks": weeks,
        "stints": _ownership_stints(weeks),
        "draft": draft,
        "owners": owners,
        "bio": _player_bio(player_id),
        "chairs": _player_chairs(player_id),
        "rings": _player_title_weeks(player_id),
        "lines": lines,
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


MARK_KIND_ORDER = (
    "high_water",
    "cellar",
    "inch",
    "rout",
    "stolen",
    "punched",
    "pine",
    "stream",
    "add",
    "miss",
    "dodge",
)

MARK_META = {
    "high_water": {
        "label": "WTF IS A MEDIAN???",
        "unit": "PF",
        "polarity": "high",
        "definition": "Highest points scored this week.",
    },
    "cellar": {
        "label": "At least we don't use all-play",
        "unit": "PF",
        "polarity": "low",
        "definition": "Lowest points scored this week.",
    },
    "inch": {
        "label": "The inch",
        "unit": "margin",
        "polarity": "high",
        "definition": "Closest head-to-head finish, if the margin is 5 or less.",
    },
    "rout": {
        "label": "The rout",
        "unit": "margin",
        "polarity": "high",
        "definition": "Largest head-to-head margin, if it is 40 or more.",
    },
    "stolen": {
        "label": "H2H enjoyer",
        "unit": "PF",
        "polarity": "high",
        "definition": "Won while scoring in the bottom half.",
    },
    "punched": {
        "label": "Median enjoyer",
        "unit": "PF",
        "polarity": "low",
        "definition": "Lost while scoring in the top half.",
    },
    "pine": {
        "label": "Bench Waste",
        "unit": "bench",
        "polarity": "low",
        "definition": "Most points left on the bench.",
    },
    "stream": {
        "label": "My time is now",
        "unit": "PF",
        "polarity": "high",
        "definition": "Highest starter PF this week among waiver or FA players whose first start of 15 or more this season is this week.",
    },
    "add": {
        "label": "Best add",
        "unit": "VORP",
        "polarity": "high",
        "definition": "Highest rest-of-season VORP waiver or FA add, if VORP is 10 or more.",
    },
    "miss": {
        "label": "Costliest miss",
        "unit": "VORP",
        "polarity": "low",
        "definition": "Largest rest-of-season VORP gap on a lost waiver, if the gap is 10 or more.",
    },
    "dodge": {
        "label": "Lucky dodge",
        "unit": "VORP",
        "polarity": "high",
        "definition": "Largest rest-of-season VORP gap on a fallback add after a lost waiver, if the gap is 10 or more.",
    },
}

MARK_LABELS = {kind: spec["label"] for kind, spec in MARK_META.items()}

CHAIR_KIND = {
    "all_league": "Varsity Letters",
    "busch": "Varsity Farmers",
    "benched_all_star": "Beat the Freeze",
}


def home_desk() -> dict[str, Any]:
    seasons = list_seasons()
    year = latest_scored_year()
    current = season_row(year) if year is not None else None
    table = standings(year) if year is not None else []
    weeks = scored_weeks(year) if year is not None else []
    now = int(weeks[-1]) if weeks else None
    slate = None
    if year is not None and now is not None:
        games = week_slate(year, now)
        if games:
            slate = {
                "year": year,
                "week": now,
                "groups": games["groups"],
            }
    preview = week_card(year, now) if year is not None and now is not None else None
    universes = _season_universes(year) if year is not None else None
    career_rows = career()
    return {
        "seasons": seasons,
        "year": year,
        "current": current,
        "standings": table,
        "slate": slate,
        "preview": preview,
        "universes": universes,
        "career": career_rows,
        "league_records": _home_league_records(career_rows),
        "highlights": _home_highlights(year),
        "rivalries": (versus_grid().get("notes") or [])[:3],
        "luck_plaques": luck_plaques(career_rows, href="/members"),
    }


def _home_league_records(career_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chips: list[dict[str, Any]] = []
    high = next(iter(high_weeks(1)), None)
    if high:
        chips.append(
            {
                "kicker": "Highest score",
                "who": high["display_name"],
                "who_id": high["manager_id"],
                "figure": f"{float(high['points']):.1f}",
                "meta": f"{high['year']} W{high['week']}",
                "href": f"/seasons/{high['year']}/week/{high['week']}",
                "polarity": "high",
                "hue": manager_hue(high["manager_id"]),
            }
        )
    close = next(iter(closest_games(1)), None)
    if close:
        chips.append(
            {
                "kicker": "Closest game",
                "who": f"{close['manager_name']} vs {close['opponent_name']}",
                "who_id": None,
                "figure": f"{float(close['abs_margin']):.2f}",
                "meta": f"{close['year']} W{close['week']}",
                "href": f"/seasons/{close['year']}/week/{close['week']}/{close['matchup_id']}",
                "polarity": "",
                "hue": None,
            }
        )
    blow = next(iter(blowouts(1)), None)
    if blow:
        chips.append(
            {
                "kicker": "Biggest blowout",
                "who": f"{blow['manager_name']} def {blow['opponent_name']}",
                "who_id": blow["manager_id"],
                "figure": f"{float(blow['abs_margin']):.1f}",
                "meta": f"{blow['year']} W{blow['week']}",
                "href": f"/seasons/{blow['year']}/week/{blow['week']}/{blow['matchup_id']}",
                "polarity": "high",
                "hue": manager_hue(blow["manager_id"]),
            }
        )
    titled = [row for row in career_rows if int(row.get("titles") or 0) > 0]
    if titled:
        top = max(titled, key=lambda row: (int(row["titles"] or 0), float(row.get("win_pct") or 0)))
        chips.append(
            {
                "kicker": "Most championships",
                "who": top["display_name"],
                "who_id": top["manager_id"],
                "figure": str(int(top["titles"] or 0)),
                "meta": "titles",
                "href": f"/members/{top['manager_id']}",
                "polarity": "high",
                "hue": manager_hue(top["manager_id"]),
            }
        )
    return chips


def _home_highlights(year: int | None) -> dict[str, list[dict[str, Any]]]:
    season = _season_highlight_chips(year) if year is not None else []
    career_chips: list[dict[str, Any]] = []
    hits = _record_draft_picks(worst=False, limit=1)
    misses = _record_draft_picks(worst=True, limit=1)
    if hits:
        career_chips.append(_draft_chip(hits[0], "Best vs round", "high"))
    if misses:
        career_chips.append(_draft_chip(misses[0], "Worst vs round", "low"))
    adds = _record_wire_adds(1)
    misses_w = _record_wire_misses(1)
    if adds:
        career_chips.append(_add_chip(adds[0], "Best add", "high"))
    if misses_w:
        career_chips.append(_miss_chip(misses_w[0], "Costliest miss", "low"))
    trades = lopsided_trades(1)
    if trades:
        career_chips.append(_trade_chip(trades[0], "Most lopsided trade"))
    return {"season": season, "career": [chip for chip in career_chips if chip]}


def _season_highlight_chips(
    year: int,
    *,
    draft: dict[str, Any] | None = None,
    wire: dict[str, Any] | None = None,
    trades: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if draft is None:
        draft = _season_draft(year)
    if wire is None:
        wire = _season_wire(year)
    if trades is None:
        trades = _season_trades(year)
    chips: list[dict[str, Any]] = []
    hits = draft.get("hits") or []
    misses = draft.get("misses") or []
    if hits:
        chips.append(_draft_chip(hits[0], "Best vs round", "high", year))
    if misses:
        chips.append(_draft_chip(misses[0], "Worst vs round", "low", year))
    adds = wire.get("adds") or []
    misses_w = wire.get("misses") or []
    if adds:
        chips.append(_add_chip(adds[0], "Best add", "high"))
    if misses_w:
        chips.append(_miss_chip(misses_w[0], "Costliest miss", "low"))
    if trades:
        top = max(trades, key=lambda row: float((row.get("verdict") or {}).get("gap") or 0))
        chips.append(_trade_chip(top, "Most lopsided trade"))
    return [chip for chip in chips if chip]


def _draft_chip(
    row: dict[str, Any], kicker: str, polarity: str, year: int | None = None
) -> dict[str, Any]:
    year = year if year is not None else row.get("year")
    overall = row.get("overall")
    return {
        "kicker": kicker,
        "player_id": row.get("player_id"),
        "player_name": row.get("player_name"),
        "manager_id": row.get("manager_id"),
        "manager_name": row.get("manager_name"),
        "figure": f"{float(row['vs_vorp']):+.1f}" if row.get("vs_vorp") is not None else None,
        "meta": f"{year} · pick {overall}" if year and overall else None,
        "href": f"/seasons/{year}/draft#p{overall}" if year and overall else None,
        "polarity": polarity,
        "hue": manager_hue(row.get("manager_id")),
    }


def _add_chip(row: dict[str, Any], kicker: str, polarity: str) -> dict[str, Any]:
    year = row.get("year")
    week = row.get("week")
    txn = row.get("transaction_id")
    href = f"/seasons/{year}/wire/{txn}" if year and txn else (f"/seasons/{year}/week/{week}" if year and week else None)
    vorp = row.get("ros_vorp")
    return {
        "kicker": kicker,
        "player_id": row.get("player_id"),
        "player_name": row.get("player_name"),
        "manager_id": row.get("manager_id"),
        "manager_name": row.get("manager_name"),
        "figure": f"{float(vorp):+.1f}" if vorp is not None else None,
        "meta": f"{year} W{week}" if year and week else None,
        "href": href,
        "polarity": polarity,
        "hue": manager_hue(row.get("manager_id")),
    }


def _miss_chip(row: dict[str, Any], kicker: str, polarity: str) -> dict[str, Any]:
    year = row.get("year")
    week = row.get("week")
    txn = row.get("missed_transaction_id")
    href = f"/seasons/{year}/wire/{txn}" if year and txn else (f"/seasons/{year}/week/{week}" if year and week else None)
    gap = row.get("vorp_gap")
    return {
        "kicker": kicker,
        "player_id": row.get("missed_player_id"),
        "player_name": row.get("missed_player"),
        "manager_id": row.get("manager_id"),
        "manager_name": row.get("manager_name"),
        "figure": f"{float(gap):+.1f}" if gap is not None else None,
        "meta": f"{year} W{week}" if year and week else None,
        "href": href,
        "polarity": polarity,
        "hue": manager_hue(row.get("manager_id")),
    }


def _trade_chip(row: dict[str, Any], kicker: str) -> dict[str, Any]:
    home = row.get("home") or {}
    away = row.get("away") or {}
    year = row.get("year")
    week = row.get("week")
    txn = row.get("transaction_id")
    gap = (row.get("verdict") or {}).get("gap")
    return {
        "kicker": kicker,
        "player_id": None,
        "player_name": None,
        "manager_id": home.get("id"),
        "manager_name": f"{home.get('name')} / {away.get('name')}",
        "figure": f"{float(gap):.0f}" if gap is not None else None,
        "meta": f"{year} W{week}" if year and week else None,
        "href": f"/seasons/{year}/trades/{txn}" if year and txn else None,
        "polarity": "",
        "hue": manager_hue(home.get("id")),
    }


def _decorate_mark(row: dict[str, Any], year: int | None = None) -> dict[str, Any]:
    spec = MARK_META.get(row.get("kind") or "", {})
    row["label"] = spec.get("label", row.get("kind"))
    row["unit"] = spec.get("unit", "")
    row["polarity"] = spec.get("polarity", "")
    row["definition"] = spec.get("definition", "")
    row["hue"] = manager_hue(row.get("manager_id"))
    if not row.get("manager_name"):
        row["manager_name"] = row.get("display_name")
    kind = row.get("kind")
    year = year if year is not None else row.get("year")
    week = row.get("week")
    matchup_id = row.get("matchup_id")
    if kind in {"add", "miss", "dodge"} and year is not None and matchup_id:
        row["href"] = f"/seasons/{year}/wire/{matchup_id}"
    elif year is not None and week is not None and matchup_id:
        row["href"] = f"/seasons/{year}/week/{week}/{matchup_id}"
    elif year is not None and week is not None:
        row["href"] = f"/seasons/{year}/week/{week}"
    else:
        row["href"] = None
    points = row.get("points")
    opp = row.get("opp_points")
    value = row.get("value")
    row["score"] = None
    row["figure"] = None
    row["aside_label"] = None
    row["aside_name"] = None
    row["aside_id"] = None
    if kind == "miss" and row.get("opponent_name"):
        row["aside_label"] = "got"
        row["aside_name"] = row["opponent_name"]
        row["aside_id"] = row.get("opponent_id")
    elif kind == "dodge" and row.get("opponent_name"):
        row["aside_label"] = "dodged"
        row["aside_name"] = row["opponent_name"]
        row["aside_id"] = row.get("opponent_id")
    if kind == "pine" and value is not None:
        row["figure"] = f"{float(value):.1f}"
    elif kind in {"add", "miss", "dodge"} and value is not None:
        row["figure"] = f"{float(value):+.1f}"
    elif kind in {"inch", "rout"} and value is not None:
        row["figure"] = f"{float(value):.1f}"
        if points is not None and opp is not None:
            row["score"] = f"{float(points):.1f}–{float(opp):.1f}"
    elif kind in {"stolen", "punched"} and points is not None and opp is not None:
        row["figure"] = f"{float(points):.1f}–{float(opp):.1f}"
    elif points is not None:
        row["figure"] = f"{float(points):.1f}"
    elif value is not None:
        row["figure"] = f"{float(value):.1f}"
    return row


def _decorate_chair(row: dict[str, Any]) -> dict[str, Any]:
    row["label"] = CHAIR_KIND.get(row["kind"], row["kind"])
    row["polarity"] = "high" if row["kind"] == "all_league" else "low"
    row["unit"] = "PF"
    row["hue"] = manager_hue(row.get("manager_id"))
    row["href"] = f"/players/{row['player_id']}" if row.get("player_id") else None
    row["figure"] = f"{float(row['points']):.1f}" if row.get("points") is not None else None
    row["score"] = None
    return row


def week_marks(year: int, week: int) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            year, week, kind, manager_id, display_name, opponent_id, opponent_name,
            matchup_id, points, opp_points, value, player_id, player_name, position
        FROM v_marks_weeks
        WHERE year = %(year)s AND week = %(week)s
        ORDER BY
            CASE kind
                WHEN 'high_water' THEN 0
                WHEN 'cellar' THEN 1
                WHEN 'inch' THEN 2
                WHEN 'rout' THEN 3
                WHEN 'stolen' THEN 4
                WHEN 'punched' THEN 5
                WHEN 'pine' THEN 6
                WHEN 'stream' THEN 7
                WHEN 'add' THEN 8
                WHEN 'miss' THEN 9
                WHEN 'dodge' THEN 10
                ELSE 11
            END,
            manager_id
        """,
        {"year": year, "week": week},
    )
    for row in rows:
        _decorate_mark(row, year)
    return rows


def week_chairs(year: int, week: int) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT year, week, position, kind, player_id, player_name,
               manager_id, manager_name, points
        FROM v_all_league
        WHERE year = %(year)s AND week = %(week)s
        ORDER BY
            CASE kind WHEN 'all_league' THEN 0 WHEN 'busch' THEN 1 ELSE 2 END,
            CASE position
                WHEN 'QB' THEN 0 WHEN 'RB' THEN 1 WHEN 'WR' THEN 2
                WHEN 'TE' THEN 3 WHEN 'K' THEN 4 ELSE 5
            END,
            player_name
        """,
        {"year": year, "week": week},
    )
    for row in rows:
        _decorate_chair(row)
    return rows


def week_card(year: int, week: int) -> dict[str, Any] | None:
    marks = week_marks(year, week)
    chairs = week_chairs(year, week)
    by_kind = {row["kind"]: row for row in marks}
    first = [row for row in chairs if row["kind"] == "all_league"]
    last = [row for row in chairs if row["kind"] == "busch"]
    freeze = [row for row in chairs if row["kind"] == "benched_all_star"]
    if not marks and not first and not last and not freeze:
        return None
    return {
        "year": year,
        "week": week,
        "marks": marks,
        "by_kind": by_kind,
        "first_chairs": first,
        "last_chairs": last,
        "freeze": freeze,
    }


def week_marks_season(year: int) -> dict[str, Any]:
    rows = fetchall(
        """
        SELECT year, week, kind, manager_id, display_name, opponent_id, opponent_name,
               matchup_id, points, opp_points, value, player_id, player_name, position
        FROM v_marks_weeks
        WHERE year = %(year)s
        ORDER BY week, kind, manager_id
        """,
        {"year": year},
    )
    for row in rows:
        _decorate_mark(row, year)
    holders = fetchall(
        """
        SELECT manager_id, display_name, kind, count(*) AS weeks
        FROM v_marks_weeks
        WHERE year = %(year)s
        GROUP BY manager_id, display_name, kind
        ORDER BY weeks DESC, display_name
        """,
        {"year": year},
    )
    counts: dict[str, dict[str, Any]] = {}
    for row in holders:
        packed = counts.setdefault(
            row["manager_id"],
            {
                "manager_id": row["manager_id"],
                "display_name": row["display_name"],
                "total": 0,
                "hue": manager_hue(row["manager_id"]),
            },
        )
        packed[row["kind"]] = int(row["weeks"])
        packed["total"] += int(row["weeks"])
    chapters = []
    for kind in MARK_KIND_ORDER:
        spec = MARK_META[kind]
        chapter_weeks = [row for row in rows if row["kind"] == kind]
        if not chapter_weeks:
            continue
        chapters.append(
            {
                "kind": kind,
                "label": spec["label"],
                "unit": spec["unit"],
                "polarity": spec["polarity"],
                "definition": spec["definition"],
                "weeks": chapter_weeks,
            }
        )
    latest_week = max((int(row["week"]) for row in rows), default=None)
    return {
        "weeks": rows,
        "holders": sorted(counts.values(), key=lambda row: (-row["total"], row["display_name"])),
        "by_kind": chapters,
        "latest_week": latest_week,
        "latest_card": week_card(year, latest_week) if latest_week is not None else None,
        "kind_order": list(MARK_KIND_ORDER),
        "labels": MARK_LABELS,
        "meta": MARK_META,
    }


def marks_page() -> dict[str, Any]:
    holders = fetchall(
        """
        SELECT manager_id, display_name, kind, weeks
        FROM v_marks_holders
        ORDER BY weeks DESC, display_name
        """
    )
    counts: dict[str, dict[str, Any]] = {}
    for row in holders:
        packed = counts.setdefault(
            row["manager_id"],
            {"manager_id": row["manager_id"], "display_name": row["display_name"], "total": 0, "hue": manager_hue(row["manager_id"])},
        )
        packed[row["kind"]] = int(row["weeks"])
        packed["total"] += int(row["weeks"])
    return {
        "holders": sorted(counts.values(), key=lambda row: (-row["total"], row["display_name"])),
        "labels": MARK_LABELS,
        "kind_order": list(MARK_KIND_ORDER),
        "meta": MARK_META,
    }


def versus_grid() -> dict[str, Any]:
    managers = fetchall(
        """
        SELECT manager_id, display_name
        FROM v_career
        ORDER BY display_name
        """
    )
    pairs = fetchall(
        """
        SELECT
            left_id, left_name, right_id, right_name,
            regular_games, regular_wins, regular_losses, regular_ties,
            regular_points_for, regular_points_against,
            playoff_games, playoff_wins, playoff_losses, playoff_ties,
            regular_avg_margin, regular_biggest_blowout, regular_closest
        FROM v_h2h
        """
    )
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for row in pairs:
        left = row["left_id"]
        right = row["right_id"]
        cells[(left, right)] = {
            "games": int(row["regular_games"] or 0),
            "wins": int(row["regular_wins"] or 0),
            "losses": int(row["regular_losses"] or 0),
            "ties": int(row["regular_ties"] or 0),
            "win_pct": (
                (int(row["regular_wins"] or 0) + 0.5 * int(row["regular_ties"] or 0))
                / int(row["regular_games"])
                if row["regular_games"]
                else None
            ),
            "record": _maybe_record(row["regular_wins"], row["regular_losses"], row["regular_ties"]),
        }
        cells[(right, left)] = {
            "games": int(row["regular_games"] or 0),
            "wins": int(row["regular_losses"] or 0),
            "losses": int(row["regular_wins"] or 0),
            "ties": int(row["regular_ties"] or 0),
            "win_pct": (
                (int(row["regular_losses"] or 0) + 0.5 * int(row["regular_ties"] or 0))
                / int(row["regular_games"])
                if row["regular_games"]
                else None
            ),
            "record": _maybe_record(row["regular_losses"], row["regular_wins"], row["regular_ties"]),
        }
    ids = [row["manager_id"] for row in managers]
    grid = []
    for left in managers:
        cells_row = []
        for right in managers:
            if left["manager_id"] == right["manager_id"]:
                cells_row.append({"self": True})
                continue
            cell = cells.get((left["manager_id"], right["manager_id"]), {"games": 0, "record": None, "win_pct": None})
            cell = dict(cell)
            cell["href"] = f"/versus/{left['manager_id']}/{right['manager_id']}"
            cells_row.append(cell)
        grid.append({"manager": left, "cells": cells_row, "hue": manager_hue(left["manager_id"])})
    return {"managers": managers, "grid": grid, "ids": ids, "notes": _versus_notes(pairs)}


def _versus_notes(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not pairs:
        return []
    notes: list[dict[str, Any]] = []

    def pack(kind: str, label: str, row: dict[str, Any], detail: str) -> dict[str, Any]:
        return {
            "kind": kind,
            "label": label,
            "left_id": row["left_id"],
            "left_name": row["left_name"],
            "right_id": row["right_id"],
            "right_name": row["right_name"],
            "detail": detail,
            "href": f"/versus/{row['left_id']}/{row['right_id']}",
        }

    long = [row for row in pairs if int(row["regular_games"] or 0) >= 4]
    if long:
        closest_series = min(
            long,
            key=lambda row: (
                abs((int(row["regular_wins"] or 0) - int(row["regular_losses"] or 0))),
                -int(row["regular_games"] or 0),
            ),
        )
        notes.append(
            pack(
                "series",
                "Closest long series",
                closest_series,
                _maybe_record(
                    closest_series["regular_wins"],
                    closest_series["regular_losses"],
                    closest_series["regular_ties"],
                )
                or "",
            )
        )
        lopsided = max(
            long,
            key=lambda row: (
                abs(
                    ((int(row["regular_wins"] or 0) + 0.5 * int(row["regular_ties"] or 0)) / int(row["regular_games"]))
                    - 0.5
                ),
                int(row["regular_games"] or 0),
            ),
        )
        notes.append(
            pack(
                "lopsided",
                "Most lopsided",
                lopsided,
                _maybe_record(lopsided["regular_wins"], lopsided["regular_losses"], lopsided["regular_ties"]) or "",
            )
        )
    most_meetings = max(pairs, key=lambda row: int(row["regular_games"] or 0) + int(row["playoff_games"] or 0))
    notes.append(
        pack(
            "meetings",
            "Most meetings",
            most_meetings,
            f"{int(most_meetings['regular_games'] or 0) + int(most_meetings['playoff_games'] or 0)} games",
        )
    )
    blow = fetchone(
        """
        SELECT
            least(manager_id, opponent_id) AS left_id,
            greatest(manager_id, opponent_id) AS right_id
        FROM v_games
        WHERE kind = 'regular' AND opponent_id IS NOT NULL
        ORDER BY abs(margin) DESC, year, week
        LIMIT 1
        """
    )
    if blow:
        names = {row["left_id"]: row["left_name"] for row in pairs}
        names.update({row["right_id"]: row["right_name"] for row in pairs})
        notes.append(
            {
                "kind": "rout",
                "label": "Biggest rout",
                "left_id": blow["left_id"],
                "left_name": names.get(blow["left_id"], blow["left_id"]),
                "right_id": blow["right_id"],
                "right_name": names.get(blow["right_id"], blow["right_id"]),
                "detail": "",
                "href": f"/versus/{blow['left_id']}/{blow['right_id']}",
            }
        )
    return [note for note in notes if note.get("href")]


def versus_pair(left_id: str, right_id: str) -> dict[str, Any] | None:
    if left_id == right_id:
        return None
    left = career_one(left_id)
    right = career_one(right_id)
    if left is None or right is None:
        return None
    series = next((row for row in h2h_for(left_id) if row["opponent_id"] == right_id), None)
    games = fetchall(
        """
        SELECT
            g.matchup_id, g.year, g.week, g.kind, g.result,
            g.points, g.opp_points, g.margin
        FROM v_games g
        WHERE g.manager_id = %(left)s AND g.opponent_id = %(right)s
            AND g.kind IN ('regular', 'playoff')
        ORDER BY g.year, g.week
        """,
        {"left": left_id, "right": right_id},
    )
    streak = _pair_streak(games)
    for game in games:
        game["kind_label"] = KIND_LABELS.get(game["kind"], game["kind"])
        game["href"] = f"/seasons/{game['year']}/week/{game['week']}/{game['matchup_id']}"
    closest = min(
        (row for row in games if row.get("margin") is not None),
        key=lambda row: abs(float(row["margin"])),
        default=None,
    )
    blowout = max(
        (row for row in games if row.get("margin") is not None),
        key=lambda row: abs(float(row["margin"])),
        default=None,
    )
    if closest is not None:
        closest["abs_margin"] = abs(float(closest["margin"]))
    if blowout is not None:
        blowout["abs_margin"] = abs(float(blowout["margin"]))
    return {
        "left": left,
        "right": right,
        "series": series,
        "games": games,
        "streak": streak,
        "closest": closest,
        "blowout": blowout,
        "hue_left": manager_hue(left_id),
        "hue_right": manager_hue(right_id),
    }


def _pair_streak(games: list[dict[str, Any]]) -> dict[str, Any] | None:
    regular = [row for row in games if row["kind"] == "regular"]
    if not regular:
        return None
    last = regular[-1]["result"]
    length = 0
    for row in reversed(regular):
        if row["result"] != last or row["result"] == "tie":
            break
        length += 1
    if last == "tie" or length == 0:
        return None
    start = regular[-length]
    return {
        "result": last,
        "length": length,
        "start_year": start["year"],
        "start_week": start["week"],
    }


def _power_board(year: int) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT year, week, manager_id, display_name, wins, losses, ties,
               win_pct, power_rank, prev_rank
        FROM v_power_board
        WHERE year = %(year)s
        ORDER BY week, power_rank, manager_id
        """,
        {"year": year},
    )
    if not rows:
        return []
    latest = max(int(row["week"]) for row in rows)
    board = [row for row in rows if int(row["week"]) == latest]
    for row in board:
        prev = row.get("prev_rank")
        row["move"] = (int(prev) - int(row["power_rank"])) if prev is not None else 0
        row["record"] = _maybe_record(row["wins"], row["losses"], row["ties"])
        row["hue"] = manager_hue(row["manager_id"])
    return board


def _week_rank_heat(year: int) -> dict[str, Any] | None:
    rows = fetchall(
        """
        SELECT year, week, manager_id, display_name, points, pf_rank, teams
        FROM v_week_scores_ranked
        WHERE year = %(year)s
        ORDER BY display_name, week
        """,
        {"year": year},
    )
    if not rows:
        return None
    weeks = sorted({int(row["week"]) for row in rows})
    by_mgr: dict[str, dict[str, Any]] = {}
    teams = int(rows[0]["teams"] or 1)
    for row in rows:
        packed = by_mgr.setdefault(
            row["manager_id"],
            {
                "manager_id": row["manager_id"],
                "display_name": row["display_name"],
                "hue": manager_hue(row["manager_id"]),
                "cells": {},
            },
        )
        packed["cells"][int(row["week"])] = {
            "week": int(row["week"]),
            "rank": int(row["pf_rank"]),
            "points": float(row["points"]),
            "heat": (int(row["pf_rank"]) - 1) / max(teams - 1, 1),
        }
    managers = []
    for packed in by_mgr.values():
        packed["cells"] = [packed["cells"].get(week) for week in weeks]
        managers.append(packed)
    managers.sort(key=lambda row: row["display_name"])
    return {"weeks": weeks, "managers": managers, "teams": teams}


def _points_race_chart(year: int) -> dict[str, Any] | None:
    rows = fetchall(
        """
        SELECT week, manager_id, display_name, cumulative
        FROM v_points_race
        WHERE year = %(year)s
        ORDER BY week, manager_id
        """,
        {"year": year},
    )
    if not rows:
        return None
    weeks = sorted({int(row["week"]) for row in rows})
    by_mgr: dict[str, list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, str] = {}
    y_min = min(float(row["cumulative"]) for row in rows)
    y_max = max(float(row["cumulative"]) for row in rows)
    pad = (y_max - y_min) * 0.08 if y_max > y_min else 1
    y_min -= pad
    y_max += pad
    y_span = y_max - y_min or 1
    w_min, w_max = min(weeks), max(weeks)
    w_span = w_max - w_min or 1
    width, height = 720, 220
    left, right, top, bottom = 44, 10, 8, 22
    plot_w = width - left - right
    plot_h = height - top - bottom

    def sx(week: int) -> float:
        return left + (week - w_min) / w_span * plot_w

    def sy(value: float) -> float:
        return top + (1 - (value - y_min) / y_span) * plot_h

    for row in rows:
        by_mgr[row["manager_id"]].append(row)
        names[row["manager_id"]] = row["display_name"]
    series = []
    for manager_id, points in by_mgr.items():
        pts = [
            {"week": int(row["week"]), "value": float(row["cumulative"]), "x": sx(int(row["week"])), "y": sy(float(row["cumulative"]))}
            for row in points
        ]
        path = "M " + " L ".join(f"{pt['x']:.1f},{pt['y']:.1f}" for pt in pts)
        series.append(
            {
                "manager_id": manager_id,
                "display_name": names[manager_id],
                "hue": manager_hue(manager_id),
                "path": path,
                "points": pts,
            }
        )
    series.sort(key=lambda row: row["display_name"])
    y_ticks = [y_min + y_span * i / 2 for i in (0, 1, 2)]
    return {
        "width": width,
        "height": height,
        "left": left,
        "plot_w": plot_w,
        "plot_h": plot_h,
        "series": series,
        "x_ticks": [{"week": week, "x": sx(week)} for week in weeks],
        "y_ticks": [{"value": tick, "y": sy(tick)} for tick in y_ticks],
    }


def _schedule_desk(year: int) -> dict[str, Any] | None:
    rows = fetchall(
        """
        SELECT
            manager_id, manager_name, schedule_id, schedule_name,
            games, wins, losses, ties, win_pct
        FROM v_schedule_desk
        WHERE year = %(year)s
        ORDER BY manager_name, schedule_name
        """,
        {"year": year},
    )
    if not rows:
        return None
    managers: dict[str, dict[str, Any]] = {}
    for row in rows:
        packed = managers.setdefault(
            row["manager_id"],
            {
                "manager_id": row["manager_id"],
                "display_name": row["manager_name"],
                "hue": manager_hue(row["manager_id"]),
                "cells": {},
            },
        )
        packed["cells"][row["schedule_id"]] = {
            "schedule_id": row["schedule_id"],
            "record": _maybe_record(row["wins"], row["losses"], row["ties"]),
            "win_pct": row["win_pct"],
        }
    order = sorted(managers.values(), key=lambda row: row["display_name"])
    ids = [row["manager_id"] for row in order]
    for packed in order:
        packed["cells"] = [
            packed["cells"].get(other["manager_id"])
            if other["manager_id"] != packed["manager_id"]
            else {"self": True}
            for other in order
        ]
    return {"managers": order, "ids": ids}


def schedule_desk_page(year: int) -> dict[str, Any] | None:
    current = season_row(year)
    if current is None:
        return None
    return {"current": current, "desk": _schedule_desk(year), "seasons": list_seasons()}


def median_tax(year: int | None = None) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            year, manager_id, display_name,
            h2h_wins, h2h_losses, h2h_ties,
            official_wins, official_losses, official_ties,
            median_wins, median_losses, median_ties,
            extra_wins, official_playoff, h2h_playoff, playoff_flip, champion
        FROM v_median_tax
        WHERE (%(year)s::integer IS NULL OR year = %(year)s)
        ORDER BY year DESC, extra_wins DESC, display_name
        """,
        {"year": year},
    )


def _playoff_path(year: int) -> list[dict[str, Any]]:
    rows = fetchall(
        """
        SELECT
            o.rank,
            o.manager_id,
            o.display_name,
            o.wins, o.losses, o.ties, o.points_for,
            lk.wins_vs_expected, lk.net_luck,
            mg.left_on_bench,
            med.wins AS median_wins
        FROM v_standings_official o
        JOIN season_playoff_managers p
            ON p.year = o.year AND p.manager_id = o.manager_id
        LEFT JOIN v_luck_season lk
            ON lk.year = o.year AND lk.manager_id = o.manager_id
        LEFT JOIN v_management_season mg
            ON mg.year = o.year AND mg.manager_id = o.manager_id
        LEFT JOIN (
            SELECT year, manager_id, count(*) FILTER (WHERE result = 'win') AS wins
            FROM v_games
            WHERE kind = 'vs_median'
            GROUP BY year, manager_id
        ) med ON med.year = o.year AND med.manager_id = o.manager_id
        WHERE o.year = %(year)s
        ORDER BY o.rank, o.manager_id
        """,
        {"year": year},
    )
    for row in rows:
        row["record"] = _maybe_record(row["wins"], row["losses"], row["ties"])
        row["hue"] = manager_hue(row["manager_id"])
    return rows


def _member_platform_split(manager_id: str) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            s.platform,
            count(*) AS seasons,
            sum(r.wins) AS wins,
            sum(r.losses) AS losses,
            sum(r.ties) AS ties,
            sum(r.points_for) AS points_for,
            count(*) FILTER (WHERE o.champion = r.manager_id) AS titles
        FROM official_records r
        JOIN seasons s ON s.year = r.year
        LEFT JOIN season_outcomes o ON o.year = r.year
        WHERE r.manager_id = %(manager_id)s
            AND (r.wins + r.losses + r.ties > 0 OR r.points_for > 0)
        GROUP BY s.platform
        ORDER BY s.platform
        """,
        {"manager_id": manager_id},
    )


def _player_bio(player_id: str) -> dict[str, Any] | None:
    return fetchone(
        """
        SELECT nfl_team, college, years_exp, jersey_number, position, display_name
        FROM players
        WHERE id = %(player_id)s
        """,
        {"player_id": player_id},
    )


def _player_chairs(player_id: str) -> dict[str, Any]:
    row = fetchone(
        """
        SELECT
            count(*) FILTER (WHERE kind = 'all_league') AS first_chair,
            count(*) FILTER (WHERE kind = 'busch') AS last_chair,
            count(*) FILTER (WHERE kind = 'benched_all_star') AS benched_first_chair,
            count(DISTINCT manager_id) AS owners
        FROM v_all_league
        WHERE player_id = %(player_id)s
        """,
        {"player_id": player_id},
    ) or {}
    owners = fetchone(
        """
        SELECT count(DISTINCT manager_id) AS owners
        FROM v_ownership_season
        WHERE player_id = %(player_id)s AND manager_id IS NOT NULL
        """,
        {"player_id": player_id},
    )
    row["owners"] = int((owners or {}).get("owners") or row.get("owners") or 0)
    row["journeyman"] = row["owners"] >= 3
    return row


def _player_title_weeks(player_id: str) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            pw.year, pw.week, pw.manager_id, pw.manager_name, pw.points, pw.started
        FROM v_player_weeks pw
        JOIN season_outcomes o ON o.year = pw.year AND o.champion = pw.manager_id
        JOIN seasons s ON s.year = pw.year
        LEFT JOIN season_outcomes so ON so.year = pw.year
        WHERE pw.player_id = %(player_id)s
            AND pw.started
            AND pw.kind = 'playoff'
            AND (so.playoff_start_week IS NULL OR pw.week >= so.playoff_start_week)
        ORDER BY pw.year, pw.week
        """,
        {"player_id": player_id},
    )


def _player_stat_lines(player_id: str) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT year, week, pass_points, rush_points, rec_points, misc_points
        FROM player_week_stat_lines
        WHERE player_id = %(player_id)s
        ORDER BY year, week
        """,
        {"player_id": player_id},
    )


def scoring_sheet(year: int) -> dict[str, Any] | None:
    current = season_row(year)
    if current is None:
        return None
    settings = current.get("scoring_settings")
    rows: list[dict[str, Any]] = []
    if isinstance(settings, dict):
        for key, value in sorted(settings.items(), key=lambda item: str(item[0])):
            if value in (0, 0.0, None, "", False):
                continue
            rows.append({"key": key, "label": _scoring_label(key), "value": _scoring_value(value)})
    elif isinstance(settings, list):
        for item in settings:
            if not isinstance(item, dict):
                continue
            key = str(item.get("statId") or item.get("id") or "")
            points = item.get("points")
            if points in (0, 0.0, None, ""):
                continue
            rows.append({"key": key, "label": _scoring_label(key), "value": _scoring_value(points)})
    spent = []
    if current.get("faab_budget"):
        spent = fetchall(
            """
            SELECT
                ts.manager_id,
                m.display_name,
                coalesce((
                    SELECT sum(t.bid)
                    FROM transactions t
                    JOIN transaction_moves mv ON mv.transaction_id = t.id
                    WHERE t.year = ts.year
                        AND t.type = 'waiver'
                        AND t.status = 'complete'
                        AND t.bid IS NOT NULL
                        AND mv.manager_id = ts.manager_id
                        AND mv.direction = 'add'
                ), 0) AS spent
            FROM team_seasons ts
            JOIN managers m ON m.id = ts.manager_id
            WHERE ts.year = %(year)s
            ORDER BY m.display_name
            """,
            {"year": year},
        )
        budget = int(current["faab_budget"])
        for row in spent:
            row["remaining"] = budget - int(row["spent"] or 0)
            row["budget"] = budget
    return {
        "current": current,
        "seasons": list_seasons(),
        "rows": rows,
        "faab": spent,
    }


def records_page() -> dict[str, Any]:
    packed = marks_page()
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
        "season_pf": _record_season_pf(),
        "season_all_play": _record_season_all_play(),
        "season_luck": _record_season_luck(),
        "season_pine": _record_bench_seasons(),
        "playoff_weeks": _record_playoff_weeks(),
        "playoff_wins": _record_playoff_career(),
        "chairs": _record_chairs(),
        "holders": packed["holders"],
        "labels": packed["labels"],
        "kind_order": packed["kind_order"],
        "meta": packed["meta"],
        "median_tax": median_tax(),
        "platform": _platform_split_table(),
        "title_droughts": _title_droughts(),
        "season_pct": _record_season_pct(),
        "title_games": _record_title_games(),
        "fa_adds": _record_fa_adds(),
        "wire_eras": _wire_eras(),
        "coaches": management_career(),
    }


def _record_season_pf(limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    high = fetchall(
        """
        SELECT year, manager_id, display_name, points_for, win_pct, wins, losses, ties
        FROM v_standings_official
        ORDER BY points_for DESC, year, manager_id
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    low = fetchall(
        """
        SELECT year, manager_id, display_name, points_for, win_pct, wins, losses, ties
        FROM v_standings_official
        WHERE wins + losses + ties > 0
        ORDER BY points_for ASC, year, manager_id
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    return {"high": high, "low": low}


def _record_season_all_play(limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    high = fetchall(
        """
        SELECT year, manager_id, display_name, wins, losses, ties, win_pct
        FROM v_all_play_season
        ORDER BY win_pct DESC NULLS LAST, wins DESC, year
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    low = fetchall(
        """
        SELECT year, manager_id, display_name, wins, losses, ties, win_pct
        FROM v_all_play_season
        ORDER BY win_pct ASC NULLS LAST, wins ASC, year
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    return {"high": high, "low": low}


def _record_season_luck(limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    lucky = fetchall(
        """
        SELECT year, manager_id, display_name, net_luck, wins_vs_expected
        FROM v_luck_season
        ORDER BY net_luck DESC, wins_vs_expected DESC NULLS LAST
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    unlucky = fetchall(
        """
        SELECT year, manager_id, display_name, net_luck, wins_vs_expected
        FROM v_luck_season
        ORDER BY net_luck ASC, wins_vs_expected ASC NULLS LAST
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    return {"lucky": lucky, "unlucky": unlucky}


def _record_playoff_weeks(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT g.year, g.week, g.matchup_id, g.manager_id, m.display_name, g.points
        FROM v_games g
        JOIN managers m ON m.id = g.manager_id
        WHERE g.kind = 'playoff'
        ORDER BY g.points DESC, g.year, g.week
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def _record_playoff_career(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT manager_id, display_name, games, wins, losses, ties, title_games
        FROM v_playoff_career
        ORDER BY wins DESC, title_games DESC, display_name
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def _record_chairs(limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    first = fetchall(
        """
        SELECT manager_id, manager_name AS display_name, first_chair, last_chair, benched_first_chair
        FROM v_chair_career
        ORDER BY first_chair DESC, manager_name
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    last = fetchall(
        """
        SELECT manager_id, manager_name AS display_name, first_chair, last_chair, benched_first_chair
        FROM v_chair_career
        ORDER BY last_chair DESC, manager_name
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    sat = fetchall(
        """
        SELECT manager_id, manager_name AS display_name, first_chair, last_chair, benched_first_chair
        FROM v_chair_career
        ORDER BY benched_first_chair DESC, manager_name
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    return {"first": first, "last": last, "sat": sat}


def _platform_split_table() -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            s.platform,
            r.manager_id,
            m.display_name,
            count(*) AS seasons,
            sum(r.wins) AS wins,
            sum(r.losses) AS losses,
            sum(r.ties) AS ties,
            sum(r.points_for) AS points_for,
            count(*) FILTER (WHERE o.champion = r.manager_id) AS titles
        FROM official_records r
        JOIN seasons s ON s.year = r.year
        JOIN managers m ON m.id = r.manager_id
        LEFT JOIN season_outcomes o ON o.year = r.year
        WHERE r.wins + r.losses + r.ties > 0 OR r.points_for > 0
        GROUP BY s.platform, r.manager_id, m.display_name
        ORDER BY s.platform, titles DESC, points_for DESC
        """
    )


def _title_droughts() -> list[dict[str, Any]]:
    latest = fetchone("SELECT max(year) AS year FROM seasons")
    now = int(latest["year"]) if latest and latest["year"] is not None else None
    rows = fetchall(
        """
        SELECT
            c.manager_id,
            c.display_name,
            c.titles,
            (
                SELECT max(o.year)
                FROM season_outcomes o
                WHERE o.champion = c.manager_id
            ) AS last_title,
            (
                SELECT max(p.year)
                FROM season_playoff_managers p
                WHERE p.manager_id = c.manager_id
            ) AS last_playoff
        FROM v_career c
        ORDER BY c.display_name
        """
    )
    for row in rows:
        last = row.get("last_title")
        last_po = row.get("last_playoff")
        row["title_drought"] = (now - int(last)) if now is not None and last is not None else now
        row["playoff_drought"] = (now - int(last_po)) if now is not None and last_po is not None else now
    rows.sort(key=lambda row: (-(row["title_drought"] or 0), row["display_name"]))
    return rows


def _record_season_pct(limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    high = fetchall(
        """
        SELECT year, manager_id, display_name, win_pct, wins, losses, ties
        FROM v_standings_official
        WHERE wins + losses + ties > 0
        ORDER BY win_pct DESC NULLS LAST, wins DESC, year
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    low = fetchall(
        """
        SELECT year, manager_id, display_name, win_pct, wins, losses, ties
        FROM v_standings_official
        WHERE wins + losses + ties > 0
        ORDER BY win_pct ASC NULLS LAST, wins ASC, year
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    return {"high": high, "low": low}


def _record_title_games(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            g.year,
            g.week,
            g.matchup_id,
            g.manager_id,
            m.display_name,
            g.opponent_id,
            om.display_name AS opponent_name,
            g.points,
            g.opp_points,
            abs(g.margin) AS abs_margin
        FROM v_games g
        JOIN season_outcomes o ON o.year = g.year
        JOIN managers m ON m.id = g.manager_id
        JOIN managers om ON om.id = g.opponent_id
        WHERE g.kind = 'playoff'
            AND g.manager_id < g.opponent_id
            AND o.champion IS NOT NULL
            AND o.runner_up IS NOT NULL
            AND (
                (g.manager_id = o.champion AND g.opponent_id = o.runner_up)
                OR (g.manager_id = o.runner_up AND g.opponent_id = o.champion)
            )
        ORDER BY abs(g.margin) DESC, g.year, g.week
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def _record_fa_adds(limit: int = 10) -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT year, manager_id, manager_name AS display_name, adds, waivers, free_agents
        FROM v_add_season
        ORDER BY adds DESC, free_agents DESC, year, manager_name
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def _wire_eras() -> list[dict[str, Any]]:
    return fetchall(
        """
        SELECT
            CASE WHEN s.faab_budget IS NOT NULL THEN 'FAAB' ELSE 'priority' END AS era,
            min(s.year) AS first_year,
            max(s.year) AS last_year,
            count(*) FILTER (WHERE t.type = 'waiver' AND t.status = 'complete') AS claims,
            count(*) FILTER (WHERE t.type = 'free_agent' AND t.status = 'complete') AS free_agents,
            avg(t.bid) FILTER (
                WHERE t.type = 'waiver' AND t.status = 'complete' AND t.bid IS NOT NULL
            ) AS avg_bid,
            avg(t.priority) FILTER (
                WHERE t.type = 'waiver' AND t.priority IS NOT NULL
            ) AS avg_priority
        FROM seasons s
        LEFT JOIN transactions t ON t.year = s.year
        GROUP BY CASE WHEN s.faab_budget IS NOT NULL THEN 'FAAB' ELSE 'priority' END
        ORDER BY min(s.year)
        """
    )


