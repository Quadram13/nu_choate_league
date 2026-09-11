from __future__ import annotations

import sys
from collections import defaultdict
from collections.abc import Sequence
from time import perf_counter

from .db import connect

QUERIES: dict[str, str] = {
    "career": """
        SELECT display_name, seasons, wins, losses, ties, points_for,
               titles, regular_season_titles, playoff_appearances
        FROM v_career
        ORDER BY titles DESC, win_pct DESC NULLS LAST, points_for DESC, manager_id
    """,
    "h2h": """
        SELECT left_id, left_name, right_id, right_name,
               regular_wins, regular_losses, regular_ties,
               regular_points_for, regular_points_against,
               playoff_wins, playoff_losses, playoff_ties, playoff_games,
               playoff_points_for, playoff_points_against
        FROM v_h2h
        WHERE (%(manager)s::text IS NULL
            OR left_id = %(manager)s
            OR right_id = %(manager)s)
        ORDER BY regular_games + playoff_games DESC, left_id, right_id
    """,
    "record-weeks": """
        SELECT year, week, display_name, points, high_rank, low_rank
        FROM v_record_weeks
        WHERE high_rank <= 10 OR low_rank <= 10
        ORDER BY high_rank, year, week
    """,
    "draft": """
        SELECT year, round, overall, manager_name, player_name, position, keeper
        FROM v_draft
        WHERE %(year)s::integer IS NULL OR year = %(year)s
        ORDER BY year, overall
    """,
    "moves": """
        SELECT year, week, type, status, direction, manager_name, player_name, position
        FROM v_moves
        WHERE (%(year)s::integer IS NULL OR year = %(year)s)
            AND status = 'complete'
        ORDER BY year, week, at NULLS LAST, transaction_id
        LIMIT 200
    """,
    "universes": """
        SELECT
            u.year,
            u.universe,
            u.rank,
            s.seed,
            u.display_name,
            u.wins,
            u.losses,
            u.ties,
            u.points_for,
            o.regular_season_champion,
            rs.display_name AS rs_name,
            o.champion,
            ch.display_name AS champ_name,
            o.runner_up,
            ru.display_name AS runner_name,
            o.matches_official,
            oc.champion AS official_champion,
            och.display_name AS official_champ_name,
            oc.regular_season_champion AS official_rs,
            ors.display_name AS official_rs_name
        FROM v_universe_standings u
        LEFT JOIN v_universe_seeds s
            ON s.universe = u.universe AND s.year = u.year AND s.manager_id = u.manager_id
        LEFT JOIN v_universe_outcomes o
            ON o.universe = u.universe AND o.year = u.year
        LEFT JOIN managers rs ON rs.id = o.regular_season_champion
        LEFT JOIN managers ch ON ch.id = o.champion
        LEFT JOIN managers ru ON ru.id = o.runner_up
        LEFT JOIN season_outcomes oc ON oc.year = u.year
        LEFT JOIN managers och ON och.id = oc.champion
        LEFT JOIN managers ors ON ors.id = oc.regular_season_champion
        WHERE %(year)s::integer IS NULL OR u.year = %(year)s
        ORDER BY
            u.year,
            CASE u.universe WHEN 'always_median' THEN 0 ELSE 1 END,
            u.rank,
            u.manager_id
    """,
    "luck": """
        SELECT
            year, display_name, wins, losses, ties,
            lucky_wins, unlucky_losses, net_luck,
            underdog_wins, favorite_losses,
            expected_wins, wins_vs_expected
        FROM v_luck_season
        WHERE (%(year)s::integer IS NULL OR year = %(year)s)
            AND (%(manager)s::text IS NULL OR manager_id = %(manager)s)
        ORDER BY year, net_luck DESC, wins_vs_expected DESC, display_name
    """,
    "trades": """
        SELECT
            year, week, left_id, left_name, left_ros, left_vorp, left_tenure, left_received,
            right_id, right_name, right_ros, right_vorp, right_tenure, right_received,
            vorp_gap, winner_id, winner_name
        FROM v_trade_grades
        WHERE (%(year)s::integer IS NULL OR year = %(year)s)
            AND (
                %(manager)s::text IS NULL
                OR left_id = %(manager)s
                OR right_id = %(manager)s
            )
        ORDER BY vorp_gap DESC, year, week
    """,
    "draft-value": """
        SELECT
            year, round, overall, manager_id, manager_name, player_name, position,
            ros_starter, ros_vorp, ros_starts, vs_vorp, adp, times_drafted, pick_vs_adp, hit
        FROM v_draft_grades
        WHERE (%(year)s::integer IS NULL OR year = %(year)s)
            AND (%(manager)s::text IS NULL OR manager_id = %(manager)s)
        ORDER BY year, vs_vorp DESC, overall
    """,
    "waivers": """
        SELECT
            year, week, type, manager_id, manager_name, player_name, position,
            ros_starter, ros_vorp, ros_starts
        FROM v_add_value
        WHERE (%(year)s::integer IS NULL OR year = %(year)s)
            AND (%(manager)s::text IS NULL OR manager_id = %(manager)s)
        ORDER BY ros_vorp DESC, year, week
    """,
    "vorp": """
        SELECT
            year, player_name, position, weeks, rostered_weeks, starts, fa_weeks,
            points, vorp, started_vorp, fa_vorp
        FROM v_vorp_season
        WHERE %(year)s::integer IS NULL OR year = %(year)s
        ORDER BY year, vorp DESC, points DESC, player_name
        LIMIT 80
    """,
}

QUERY_NAMES = tuple(QUERIES)

WAIVER_MISSES_SQL = """
    SELECT
        year, week, manager_id, manager_name, reason,
        missed_seq, missed_player, missed_position, missed_ros, missed_vorp, missed_starts,
        won_seq, won_player, won_ros, won_vorp, vorp_gap, note
    FROM v_waiver_misses
    WHERE (%(year)s::integer IS NULL OR year = %(year)s)
        AND (%(manager)s::text IS NULL OR manager_id = %(manager)s)
        AND reason IN ('own_claim_order', 'lost_on_wire')
    ORDER BY year, vorp_gap DESC, week
"""

WAIVER_DODGES_SQL = """
    SELECT
        year, week, manager_id, manager_name,
        lost_seq, lost_player, lost_position, lost_vorp,
        won_seq, won_player, won_vorp, vorp_gap
    FROM v_waiver_dodges
    WHERE (%(year)s::integer IS NULL OR year = %(year)s)
        AND (%(manager)s::text IS NULL OR manager_id = %(manager)s)
    ORDER BY year, vorp_gap DESC, week
"""


def run_query(name: str, *, year: int | None = None, manager: str | None = None) -> str:
    sql = QUERIES.get(name)
    if sql is None:
        raise SystemExit(f"Unknown query {name}. Choose one of: {', '.join(QUERY_NAMES)}")
    with connect() as conn:
        with conn.cursor() as cur:
            params = {}
            if "%(year)s" in sql:
                params["year"] = year
            if "%(manager)s" in sql:
                params["manager"] = manager
            start = perf_counter()
            cur.execute(sql, params or None)
            rows = cur.fetchall()
            columns = [column.name for column in cur.description or []]
            misses: list[tuple] = []
            dodges: list[tuple] = []
            if name == "waivers":
                cur.execute(WAIVER_MISSES_SQL, params)
                misses = cur.fetchall()
                cur.execute(WAIVER_DODGES_SQL, params)
                dodges = cur.fetchall()
            elapsed = perf_counter() - start
    extra = f" (+{len(misses)} misses, +{len(dodges)} dodges)" if name == "waivers" else ""
    print(f"[timing] {name}: {elapsed:.3f}s, {len(rows)} rows{extra}", file=sys.stderr)
    if not rows:
        return "(no rows)\n"
    if name == "career":
        return _format_career(rows)
    if name == "h2h":
        return _format_h2h(rows, manager)
    if name == "universes":
        return _format_universes(rows)
    if name == "luck":
        return _format_luck(rows)
    if name == "trades":
        return _format_trades(rows)
    if name == "draft-value":
        return _format_draft_value(rows)
    if name == "waivers":
        return _format_waivers(rows, misses, dodges)
    if name == "vorp":
        return _format_vorp(rows)
    return _format_table(columns, rows)


def _format_career(rows: Sequence[tuple]) -> str:
    lines = ["Manager              Yrs  W-L-T       PF       Titles  RS  PO"]
    for name, seasons, wins, losses, ties, points_for, titles, rs, playoff in rows:
        record = f"{int(wins)}-{int(losses)}-{int(ties)}"
        lines.append(
            f"{name:20} {int(seasons):3}  {record:10} {float(points_for):8.2f}  "
            f"{int(titles):6} {int(rs):3} {int(playoff):3}"
        )
    return "\n".join(lines) + "\n"


def _format_h2h(rows: Sequence[tuple], manager: str | None = None) -> str:
    lines = ["Matchup                              Reg W-L     PF-PA           Playoff"]
    for (
        left_id,
        left,
        right_id,
        right,
        r_w,
        r_l,
        r_t,
        r_pf,
        r_pa,
        p_w,
        p_l,
        p_t,
        p_games,
        p_pf,
        p_pa,
    ) in rows:
        if manager and manager == right_id:
            left, right = right, left
            r_w, r_l = r_l, r_w
            r_pf, r_pa = r_pa, r_pf
            p_w, p_l = p_l, p_w
            p_pf, p_pa = p_pa, p_pf
        reg = f"{int(r_w)}-{int(r_l)}-{int(r_t)}  {float(r_pf or 0):.1f}-{float(r_pa or 0):.1f}"
        if int(p_games or 0):
            po = f"{int(p_w)}-{int(p_l)}-{int(p_t)}  {float(p_pf or 0):.1f}-{float(p_pa or 0):.1f}"
        else:
            po = "-"
        lines.append(f"{left:18} vs {right:18} {reg:28} {po}")
    return "\n".join(lines) + "\n"


def _format_universes(rows: Sequence[tuple]) -> str:
    lines: list[str] = []
    current_year: int | None = None
    current_universe: str | None = None
    for row in rows:
        (
            year,
            universe,
            rank,
            seed,
            name,
            wins,
            losses,
            ties,
            points_for,
            _rs_id,
            rs_name,
            _champ_id,
            champ_name,
            _runner_id,
            runner_name,
            matches_official,
            _off_champ_id,
            official_champ_name,
            _off_rs_id,
            official_rs_name,
        ) = row
        if year != current_year:
            if lines:
                lines.append("")
            lines.append(
                f"{year} official champ {official_champ_name or '-'}  "
                f"RS {official_rs_name or '-'}"
            )
            current_year = year
            current_universe = None
        if universe != current_universe:
            flag = " = official" if matches_official else ""
            lines.append(f"  {universe}{flag}:")
            lines.append(
                f"    RS {rs_name or '-'}  champ {champ_name or '-'}  "
                f"runner-up {runner_name or '-'}"
            )
            current_universe = universe
        seed_txt = f"s{int(seed)}" if seed is not None else "  "
        record = f"{int(wins)}-{int(losses)}-{int(ties)}"
        lines.append(
            f"    {int(rank):2} {seed_txt:>2} {name:20} {record:8} {float(points_for):7.2f}"
        )
    return "\n".join(lines) + "\n"


def _format_luck(rows: Sequence[tuple]) -> str:
    lines = [
        "Year  Manager              H2H        Lucky  Unluck  Net  Undog  FavL   ExpW   vsExp"
    ]
    for (
        year,
        name,
        wins,
        losses,
        ties,
        lucky,
        unlucky,
        net,
        underdog,
        favorite,
        expected,
        delta,
    ) in rows:
        record = f"{int(wins)}-{int(losses)}-{int(ties)}"
        lines.append(
            f"{int(year):4}  {name:20} {record:10} "
            f"{int(lucky):5}  {int(unlucky):6}  {int(net):3}  "
            f"{int(underdog):5}  {int(favorite):4}  "
            f"{float(expected):5.1f}  {float(delta):+5.1f}"
        )
    return "\n".join(lines) + "\n"


def _format_trades(rows: Sequence[tuple]) -> str:
    lines = ["Year Wk  Winner              VORP     ROS vs ROS    Loser"]
    for (
        year,
        week,
        left_id,
        left_name,
        left_ros,
        _left_vorp,
        _left_tenure,
        left_received,
        right_id,
        right_name,
        right_ros,
        _right_vorp,
        _right_tenure,
        right_received,
        gap,
        winner_id,
        _winner_name,
    ) in rows:
        left_ros_f = float(left_ros or 0)
        right_ros_f = float(right_ros or 0)
        if winner_id == left_id:
            winner, loser = left_name, right_name
            won, lost = left_ros_f, right_ros_f
            won_got, lost_got = left_received, right_received
        elif winner_id == right_id:
            winner, loser = right_name, left_name
            won, lost = right_ros_f, left_ros_f
            won_got, lost_got = right_received, left_received
        else:
            winner, loser = left_name, right_name
            won, lost = left_ros_f, right_ros_f
            won_got, lost_got = left_received, right_received
        edge = float(gap or 0)
        lines.append(
            f"{int(year):4} {int(week):2}  {winner:18} {edge:+7.1f}  "
            f"{won:6.1f}-{lost:<6.1f}  {loser}"
        )
        lines.append(f"         won:  {won_got or '-'}")
        lines.append(f"         lost: {lost_got or '-'}")
    return "\n".join(lines) + "\n"


def _format_draft_value(rows: Sequence[tuple]) -> str:
    by_mgr: dict[tuple[int, str, str], dict] = defaultdict(
        lambda: {
            "picks": 0,
            "starter": 0.0,
            "vorp": 0.0,
            "vs_vorp": 0.0,
            "hits": 0,
            "best": 0.0,
            "best_name": "",
        }
    )
    for (
        year,
        _round,
        _overall,
        manager_id,
        manager_name,
        player_name,
        _position,
        ros_starter,
        ros_vorp,
        _ros_starts,
        vs_vorp,
        _adp,
        _times,
        _pick_vs_adp,
        hit,
    ) in rows:
        row = by_mgr[(int(year), manager_id, manager_name)]
        vorp = float(ros_vorp or 0)
        row["picks"] += 1
        row["starter"] += float(ros_starter or 0)
        row["vorp"] += vorp
        row["vs_vorp"] += float(vs_vorp or 0)
        row["hits"] += 1 if hit else 0
        if vorp > row["best"]:
            row["best"] = vorp
            row["best_name"] = player_name
    lines = [
        "Year  Manager              Picks  Starter    VORP  vsRndV  Hits  Best",
    ]
    for (year, _mid, name), row in sorted(
        by_mgr.items(),
        key=lambda item: (item[0][0], -item[1]["vs_vorp"], item[0][2]),
    ):
        lines.append(
            f"{year:4}  {name:20} {row['picks']:5}  {row['starter']:7.1f}  "
            f"{row['vorp']:+7.1f}  {row['vs_vorp']:+6.1f}  {row['hits']:4}  "
            f"{row['best_name']} {row['best']:+.1f}"
        )
    ranked = sorted(rows, key=lambda r: float(r[10] or 0), reverse=True)
    lines.append("")
    lines.append("Best picks vs that round's average ROS VORP")
    for row in ranked[:12]:
        lines.append(_draft_pick_line(row))
    lines.append("")
    lines.append("Worst picks vs that round's average ROS VORP")
    for row in reversed(ranked[-8:]):
        lines.append(_draft_pick_line(row))
    return "\n".join(lines) + "\n"


def _draft_pick_line(row: tuple) -> str:
    (
        year,
        rnd,
        overall,
        _mid,
        manager_name,
        player_name,
        position,
        ros_starter,
        ros_vorp,
        ros_starts,
        vs_vorp,
        adp,
        times,
        pick_vs_adp,
        _hit,
    ) = row
    adp_txt = f"ADP {float(adp):5.1f}" if adp is not None and int(times or 0) >= 2 else "ADP     -"
    steal = ""
    if pick_vs_adp is not None and int(times or 0) >= 2:
        delta = float(pick_vs_adp)
        steal = f"  {'later' if delta > 0 else 'earlier'} {abs(delta):.1f}"
    return (
        f"  {int(year)} r{int(rnd):02d} p{int(overall):3}  {manager_name:18} "
        f"{player_name:22} {(position or '?'):3}  "
        f"VORP {float(ros_vorp):+6.1f}  PF {float(ros_starter):6.1f} in {int(ros_starts):2}  "
        f"vsRnd {float(vs_vorp):+6.1f}  {adp_txt}{steal}"
    )


def _format_waivers(
    rows: Sequence[tuple],
    misses: Sequence[tuple] | None = None,
    dodges: Sequence[tuple] | None = None,
) -> str:
    by_mgr: dict[tuple[int, str, str], dict] = defaultdict(
        lambda: {
            "adds": 0,
            "waivers": 0,
            "fa": 0,
            "starter": 0.0,
            "vorp": 0.0,
            "waiver_starter": 0.0,
            "waiver_vorp": 0.0,
            "fa_starter": 0.0,
            "fa_vorp": 0.0,
            "best": 0.0,
            "best_name": "",
        }
    )
    for (
        year,
        _week,
        kind,
        manager_id,
        manager_name,
        player_name,
        _position,
        ros_starter,
        ros_vorp,
        _ros_starts,
    ) in rows:
        row = by_mgr[(int(year), manager_id, manager_name)]
        starter = float(ros_starter or 0)
        vorp = float(ros_vorp or 0)
        row["adds"] += 1
        row["starter"] += starter
        row["vorp"] += vorp
        if kind == "waiver":
            row["waivers"] += 1
            row["waiver_starter"] += starter
            row["waiver_vorp"] += vorp
        else:
            row["fa"] += 1
            row["fa_starter"] += starter
            row["fa_vorp"] += vorp
        if vorp > row["best"]:
            row["best"] = vorp
            row["best_name"] = player_name
    lines = [
        "Year  Manager              Adds  Wav  FA     VORP  WavV     FAV   Best",
    ]
    for (year, _mid, name), row in sorted(
        by_mgr.items(),
        key=lambda item: (item[0][0], -item[1]["vorp"], item[0][2]),
    ):
        lines.append(
            f"{year:4}  {name:20} {row['adds']:4}  {row['waivers']:3}  {row['fa']:3}  "
            f"{row['vorp']:+7.1f}  {row['waiver_vorp']:+6.1f}  {row['fa_vorp']:+6.1f}  "
            f"{row['best_name']} {row['best']:+.1f}"
        )
    lines.append("")
    lines.append("Best waiver / FA adds (rest-of-season starter VORP)")
    for year, week, kind, _mid, manager_name, player_name, position, ros_starter, ros_vorp, ros_starts in rows[:15]:
        label = "wav" if kind == "waiver" else "FA "
        lines.append(
            f"  {int(year)} w{int(week):02d} {label}  {manager_name:18} "
            f"{player_name:22} {(position or '?'):3}  "
            f"VORP {float(ros_vorp):+6.1f}  PF {float(ros_starter):6.1f} in {int(ros_starts):2}"
        )
    own = [row for row in (misses or []) if row[4] == "own_claim_order"]
    lost = [row for row in (misses or []) if row[4] == "lost_on_wire"]
    if own:
        lines.append("")
        lines.append("Missed a better player: lower claim on your own wire (seq)")
        for row in own[:12]:
            lines.append(_miss_line(row, "claim"))
    if lost:
        lines.append("")
        lines.append("Missed a better player: lost on the waiver wire")
        for row in lost[:12]:
            lines.append(_miss_line(row, "lost"))
    if dodges:
        lines.append("")
        lines.append("Lucky dodge: higher claim taken on the wire")
        for row in dodges[:12]:
            lines.append(_dodge_line(row))
    return "\n".join(lines) + "\n"


def _miss_line(row: tuple, kind: str) -> str:
    (
        year,
        week,
        _mid,
        manager_name,
        _reason,
        missed_seq,
        missed_player,
        missed_position,
        _missed_ros,
        missed_vorp,
        _missed_starts,
        won_seq,
        won_player,
        _won_ros,
        won_vorp,
        gap,
        _note,
    ) = row
    got = won_player or "(nobody)"
    missed_n = f"#{int(missed_seq)}" if missed_seq is not None else "?"
    won_n = f"#{int(won_seq)}" if won_seq is not None else "nobody"
    if kind == "claim":
        order = f"got {won_n} vs claim {missed_n}"
    else:
        order = f"lost {missed_n}, got {won_n}"
    return (
        f"  {int(year)} w{int(week):02d}  {manager_name:18} "
        f"{missed_player:20} {(missed_position or '?'):3} VORP {float(missed_vorp):+6.1f} "
        f"vs {got:20} {float(won_vorp or 0):+6.1f}  {order}  gap {float(gap):+.1f}"
    )


def _dodge_line(row: tuple) -> str:
    (
        year,
        week,
        _mid,
        manager_name,
        lost_seq,
        lost_player,
        lost_position,
        lost_vorp,
        won_seq,
        won_player,
        won_vorp,
        gap,
    ) = row
    lost_n = f"#{int(lost_seq)}" if lost_seq is not None else "?"
    won_n = f"#{int(won_seq)}" if won_seq is not None else "?"
    return (
        f"  {int(year)} w{int(week):02d}  {manager_name:18} "
        f"lost {lost_n} {lost_player:20} {(lost_position or '?'):3} VORP {float(lost_vorp):+6.1f} "
        f"got {won_n} {won_player:20} {float(won_vorp):+6.1f}  gap {float(gap):+.1f}"
    )


def _format_vorp(rows: Sequence[tuple]) -> str:
    lines = [
        "Year  Player                    Pos  Wks  Rost  St  FA     Pts    VORP  StartV    FAV"
    ]
    for (
        year,
        player_name,
        position,
        weeks,
        rostered,
        starts,
        fa_weeks,
        points,
        vorp,
        started_vorp,
        fa_vorp,
    ) in rows:
        lines.append(
            f"{int(year):4}  {player_name:24} {(position or '?'):3}  "
            f"{int(weeks):3}  {int(rostered):4}  {int(starts):2}  {int(fa_weeks):2}  "
            f"{float(points or 0):6.1f}  {float(vorp or 0):+6.1f}  {float(started_vorp or 0):+6.1f}  "
            f"{float(fa_vorp or 0):+6.1f}"
        )
    return "\n".join(lines) + "\n"


def _format_table(columns: list[str], rows: Sequence[tuple]) -> str:
    text_rows = [[_cell(value) for value in row] for row in rows]
    widths = [len(name) for name in columns]
    for row in text_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    header = "  ".join(name.ljust(widths[index]) for index, name in enumerate(columns))
    lines = [header]
    for row in text_rows:
        lines.append("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))
    return "\n".join(lines) + "\n"


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
