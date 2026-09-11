from __future__ import annotations

from collections.abc import Sequence

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
}

QUERY_NAMES = tuple(QUERIES)


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
            cur.execute(sql, params or None)
            rows = cur.fetchall()
            columns = [column.name for column in cur.description or []]
    if not rows:
        return "(no rows)\n"
    if name == "career":
        return _format_career(rows)
    if name == "h2h":
        return _format_h2h(rows, manager)
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
