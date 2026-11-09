"""The three spike pages. Each call site is a pane catalog plus slots.

Loaders close over the request's year or the already-fetched rows and run
only for the active pane. Column sets, the tie glyph, and leader marks are
decided here, once. Shells never see them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import HTMLResponse

from . import queries
from .themes import Pane, Slot, render_panes

TOP_N = 10
CAREER_N = 50

# Existing season.html pane order. Not an ESPN 2010 tab order; none was captured.
_SEASON_LABELS: tuple[tuple[str, str], ...] = (
    ("standings", "Standings"),
    ("weeks", "Weeks"),
    ("playoffs", "Playoffs"),
    ("moves", "Moves"),
    ("draft", "Draft"),
    ("lineups", "Lineups"),
    ("stacks", "Stacks"),
)

_RANK_NOTE = (
    "PF is points scored on starts. Avg is PF per start. "
    "Bold marks the first row. Gold marks the top points."
)
_STANDINGS_NOTE = (
    "W, L, and T are wins, losses, and ties. A zero tie is shown as -. "
    "PF is points for. PA is points against. "
    "Bold marks the champion. Gold marks the high points-for."
)
_SCORING_NOTE = (
    "Low, avg, and high are team totals on posted weeks. "
    "Bold and gold mark the highest week."
)


def players_response(request: Request) -> HTMLResponse:
    rows = _career_rows(CAREER_N)

    def top() -> dict[str, object]:
        return {"board": _rankings_board(rows[:TOP_N], f"Top {min(TOP_N, len(rows))}")}

    def career() -> dict[str, object]:
        return {"board": _rankings_board(rows, f"Career top {len(rows)}")}

    return render_panes(
        request,
        title="Players",
        nav="players",
        pager="Rankings",
        panes=(
            Pane("top", f"Top {TOP_N}", "fragments/board.html", top),
            Pane("career", "Career", "fragments/board.html", career),
        ),
        slots=(
            Slot("lead", "fragments/players_lead.html"),
            Slot("aside", "fragments/players_aside.html"),
        ),
    )


def season_response(request: Request, year: int, current: Mapping[str, object]) -> HTMLResponse:
    def standings() -> dict[str, object]:
        return {"board": _standings_board(year)}

    def weeks() -> dict[str, object]:
        return {"week_groups": _games(year, ("regular",))}

    def playoffs() -> dict[str, object]:
        return {"week_groups": _games(year, ("playoff", "consolation"))}

    def moves() -> dict[str, object]:
        return {"board": _moves_board(year)}

    def draft() -> dict[str, object]:
        return {"board": _draft_board(year)}

    def lineups() -> dict[str, object]:
        return {"board": _lineups_board(year)}

    def stacks() -> dict[str, object]:
        return {"board": _stacks_board(year)}

    loaders = {
        "standings": standings,
        "weeks": weeks,
        "playoffs": playoffs,
        "moves": moves,
        "draft": draft,
        "lineups": lineups,
        "stacks": stacks,
    }
    panes = tuple(
        Pane(name, label, "fragments/board.html" if name not in ("weeks", "playoffs") else "fragments/games.html", loaders[name])
        for name, label in _SEASON_LABELS
    )
    return render_panes(
        request,
        title=f"{year} season",
        nav="seasons",
        pager="Season",
        panes=panes,
        slots=(
            Slot("lead", "fragments/season_lead.html"),
            Slot("aside", "fragments/season_aside.html"),
        ),
        context={"year": year, "current": current},
    )


def scoring_response(request: Request, year: int, current: Mapping[str, object]) -> HTMLResponse:
    def sheet() -> dict[str, object]:
        return {"board": _scoring_board(year)}

    return render_panes(
        request,
        title=f"{year} scoring",
        nav="seasons",
        pager="Sheet",
        panes=(Pane("sheet", "Scoring", "fragments/board.html", sheet),),
        slots=(
            Slot("lead", "fragments/scoring_lead.html"),
            Slot("aside", "fragments/scoring_aside.html"),
        ),
        context={"year": year, "current": current},
    )


def _career_rows(limit: int) -> list[dict[str, object]]:
    return queries.fetchall(
        """
        SELECT player_id, player_name, position, seasons, starts, starter_points
        FROM v_players_index_career
        ORDER BY starter_points DESC NULLS LAST, started_vorp DESC NULLS LAST, player_name
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )


def _games(year: int, kinds: tuple[str, ...]) -> list[dict[str, object]]:
    rows = queries.fetchall(
        """
        SELECT
            m.week,
            m.kind,
            m.home_manager_id,
            m.away_manager_id,
            hm.display_name AS home_name,
            am.display_name AS away_name,
            m.home_points,
            m.away_points
        FROM matchups m
        LEFT JOIN managers hm ON hm.id = m.home_manager_id
        LEFT JOIN managers am ON am.id = m.away_manager_id
        WHERE m.year = %(year)s
          AND m.kind = ANY(%(kinds)s)
          AND (m.home_points <> 0 OR m.away_points <> 0)
        ORDER BY m.week, m.kind, m.id
        """,
        {"year": year, "kinds": list(kinds)},
    )
    groups: list[dict[str, object]] = []
    index: dict[int, dict[str, object]] = {}
    for row in rows:
        week = int(row["week"])
        group = index.get(week)
        if group is None:
            group = {"week": week, "games": []}
            index[week] = group
            groups.append(group)
        home_text, home_n = _pts(row.get("home_points"))
        away_text, away_n = _pts(row.get("away_points"))
        games = group["games"]
        assert isinstance(games, list)
        games.append(
            {
                "home": _name(row.get("home_name")),
                "home_href": _path("/members", row.get("home_manager_id")),
                "home_pts": home_text,
                "home_mark": _higher(home_n, away_n, "home"),
                "away": _name(row.get("away_name")),
                "away_href": _path("/members", row.get("away_manager_id")),
                "away_pts": away_text,
                "away_mark": _higher(home_n, away_n, "away"),
                "kind_label": _KIND_LABEL.get(str(row.get("kind") or ""), ""),
            }
        )
    return groups


def _standings_board(year: int) -> dict[str, object]:
    rows = queries.standings(year)
    high = _max_number(row.get("points_for") for row in rows)
    body = []
    for row in rows:
        pf = row.get("points_for")
        body.append(
            (
                _cell(_int(row.get("rank")), numeric=True),
                _cell(
                    _name(row.get("display_name")),
                    href=_path("/members", row.get("manager_id")),
                    mark="is-leader" if row.get("champion") else "",
                ),
                _cell(_int(row.get("wins")), numeric=True),
                _cell(_int(row.get("losses")), numeric=True),
                _cell(_tie(row.get("ties")), numeric=True),
                _cell(_num(pf, 2), numeric=True, mark="is-record" if _same(pf, high) else ""),
                _cell(_num(row.get("points_against"), 2), numeric=True),
            )
        )
    return _board(
        f"{year} standings",
        (("#", True), ("Manager", False), ("W", True), ("L", True), ("T", True), ("PF", True), ("PA", True)),
        body,
        _STANDINGS_NOTE if body else "None posted.",
    )


def _rankings_board(rows: Sequence[Mapping[str, object]], caption: str) -> dict[str, object]:
    high = _max_number(row.get("starter_points") for row in rows)
    body = []
    for index, row in enumerate(rows, start=1):
        points = row.get("starter_points")
        starts = int(row.get("starts") or 0)
        average = None if starts == 0 or points is None else float(points) / starts
        body.append(
            (
                _cell(str(index), numeric=True),
                _cell(
                    _name(row.get("player_name")),
                    href=_path("/players", row.get("player_id")),
                    mark="is-leader" if index == 1 else "",
                ),
                _cell(_name(row.get("position"))),
                _cell(_int(row.get("seasons")), numeric=True),
                _cell(_int(row.get("starts")), numeric=True),
                _cell(_num(points, 1), numeric=True, mark="is-record" if _same(points, high) else ""),
                _cell(_num(average, 1), numeric=True),
            )
        )
    return _board(
        caption,
        (("Rk", True), ("Player", False), ("Pos", False), ("Yrs", True), ("Starts", True), ("PF", True), ("Avg", True)),
        body,
        _RANK_NOTE if body else "None posted.",
    )


def _scoring_board(year: int) -> dict[str, object]:
    rows = queries.fetchall(
        """
        SELECT
            w.week,
            min(w.points) AS low,
            max(w.points) AS high,
            avg(w.points) AS avg
        FROM week_scores w
        JOIN v_posted_weeks pw ON pw.year = w.year AND pw.week = w.week
        WHERE w.year = %(year)s
          AND w.paired
        GROUP BY w.week
        ORDER BY w.week
        """,
        {"year": year},
    )
    peak = _max_number(row.get("high") for row in rows)
    body = []
    for row in rows:
        high = row.get("high")
        mark = "is-record" if _same(high, peak) else ""
        week = int(row["week"])
        body.append(
            (
                _cell(str(week), numeric=True, href=f"/seasons/{year}/week/{week}", mark="is-leader" if mark else ""),
                _cell(_num(row.get("low"), 2), numeric=True),
                _cell(_num(row.get("avg"), 2), numeric=True),
                _cell(_num(high, 2), numeric=True, mark=mark),
            )
        )
    return _board(
        f"{year} week totals",
        (("Week", True), ("Low", True), ("Avg", True), ("High", True)),
        body,
        _SCORING_NOTE if body else "None posted.",
    )


def _moves_board(year: int) -> dict[str, object]:
    rows = queries._season_trades(year)
    body = []
    for row in rows:
        verdict = row.get("verdict") or {}
        ahead = verdict.get("kind") not in (None, "even")
        winner = row.get("winner_id")
        body.append(
            (
                _cell(_int(row.get("week")), numeric=True),
                _cell(
                    _name(row.get("left_name")),
                    href=_path("/members", row.get("left_id")),
                    mark="is-leader" if ahead and winner == row.get("left_id") else "",
                ),
                _cell(
                    _name(row.get("right_name")),
                    href=_path("/members", row.get("right_id")),
                    mark="is-leader" if ahead and winner == row.get("right_id") else "",
                ),
                _cell(_num(row.get("vorp_gap"), 1), numeric=True),
            )
        )
    return _board(
        f"{year} trades",
        (("Week", True), ("Left", False), ("Right", False), ("Gap", True)),
        body,
        "Gap is the VORP difference. Bold marks the side ahead when the trade is not even."
        if body
        else "None posted.",
    )


def _draft_board(year: int) -> dict[str, object]:
    page = queries.draft_page(year)
    picks = [] if not page else page["picks"]
    body = []
    for row in picks:
        overall = int(row.get("overall") or 0)
        body.append(
            (
                _cell(str(overall), numeric=True),
                _cell(_int(row.get("round")), numeric=True),
                _cell(_name(row.get("manager_name")), href=_path("/members", row.get("manager_id"))),
                _cell(
                    _name(row.get("player_name")),
                    href=_path("/players", row.get("player_id")),
                    mark="is-leader" if overall == 1 else "",
                ),
                _cell(_name(row.get("position"))),
            )
        )
    return _board(
        f"{year} draft",
        (("Pick", True), ("Round", True), ("Manager", False), ("Player", False), ("Pos", False)),
        body,
        "Bold marks the first overall pick." if body else "None posted.",
    )


def _lineups_board(year: int) -> dict[str, object]:
    packed = queries._season_lineups(year)
    coaches = list(packed.get("coaches") or [])
    high = _max_number(row.get("actual_points") for row in coaches)
    body = []
    for row in coaches:
        actual = row.get("actual_points")
        mark = "is-record" if _same(actual, high) else ""
        body.append(
            (
                _cell(
                    _name(row.get("manager_name")),
                    href=_path("/members", row.get("manager_id")),
                    mark="is-leader" if mark else "",
                ),
                _cell(_int(row.get("weeks")), numeric=True),
                _cell(_num(actual, 2), numeric=True, mark=mark),
                _cell(_num(row.get("optimal_points"), 2), numeric=True),
                _cell(_num(row.get("left_on_bench"), 2), numeric=True),
            )
        )
    return _board(
        f"{year} lineups",
        (("Manager", False), ("Weeks", True), ("Actual", True), ("Optimal", True), ("Bench", True)),
        body,
        "Actual and optimal are starter points. Bench is points left on the bench. Bold and gold mark the top actual."
        if body
        else "None posted.",
    )


def _stacks_board(year: int) -> dict[str, object]:
    rows = queries.fetchall(
        """
        SELECT manager_id, manager_name, stack_weeks, combined_points, stack_share
        FROM v_manager_season_stacks
        WHERE year = %(year)s
        ORDER BY stack_weeks DESC, combined_points DESC, manager_name, manager_id
        """,
        {"year": year},
    )
    high = _max_number(row.get("stack_weeks") for row in rows)
    body = []
    for row in rows:
        weeks = row.get("stack_weeks")
        mark = "is-record" if _same(weeks, high) else ""
        body.append(
            (
                _cell(
                    _name(row.get("manager_name")),
                    href=_path("/members", row.get("manager_id")),
                    mark="is-leader" if mark else "",
                ),
                _cell(_int(weeks), numeric=True, mark=mark),
                _cell(_num(row.get("combined_points"), 1), numeric=True),
                _cell(_share(row.get("stack_share")), numeric=True),
            )
        )
    return _board(
        f"{year} stacks",
        (("Manager", False), ("Weeks", True), ("Combined", True), ("Share", True)),
        body,
        "Weeks are weeks a quarterback started with a teammate catcher. Bold and gold mark the most."
        if body
        else "None posted.",
    )


_KIND_LABEL = {"playoff": "Playoff", "consolation": "Consolation"}


def _board(
    caption: str,
    columns: Sequence[tuple[str, bool]],
    rows: Sequence[Sequence[Mapping[str, object]]],
    note: str,
) -> dict[str, object]:
    return {
        "caption": caption,
        "columns": [{"label": label, "numeric": numeric} for label, numeric in columns],
        "rows": [{"cells": list(cells)} for cells in rows],
        "note": note,
    }


def _cell(text: str, *, numeric: bool = False, href: str = "", mark: str = "") -> dict[str, object]:
    return {"text": text, "numeric": numeric, "href": href, "mark": mark}


def _name(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return text or "—"


def _int(value: object) -> str:
    return str(int(value or 0))


def _tie(value: object) -> str:
    if value is None or int(value) == 0:
        return "-"
    return str(int(value))


def _num(value: object, places: int) -> str:
    if value is None:
        return "—"
    number = float(value)
    if places <= 0:
        return str(int(round(number)))
    return f"{number:.{places}f}"


def _pts(value: object) -> tuple[str, float | None]:
    if value is None:
        return "—", None
    number = float(value)
    return f"{number:.2f}", number


def _share(value: object) -> str:
    if value is None:
        return "—"
    number = float(value)
    if 0 <= number <= 1:
        return f"{number * 100:.1f}%"
    return f"{number:.1f}"


def _same(value: object, high: float | None) -> bool:
    if value is None or high is None:
        return False
    return round(float(value), 4) == round(high, 4)


def _max_number(values: Iterable[object]) -> float | None:
    found = [float(value) for value in values if value is not None]
    return max(found) if found else None


def _higher(home: float | None, away: float | None, side: str) -> str:
    if home is None or away is None or round(home, 4) == round(away, 4):
        return ""
    if side == "home" and home > away:
        return "is-leader"
    if side == "away" and away > home:
        return "is-leader"
    return ""


def _path(prefix: str, identifier: object) -> str:
    if identifier is None or str(identifier).strip() == "":
        return ""
    return f"{prefix}/{quote(str(identifier), safe='')}"
