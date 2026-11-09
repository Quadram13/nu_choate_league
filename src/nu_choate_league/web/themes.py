"""Theme machinery for the hub.

A page author lists panes and slots and calls ``render_panes``. They do not
read the theme, name a shell, or write a second table. ``render_panes`` is the
era path only. Modern stays on the legacy ``page()`` helper so those documents
remain byte-near.

Resolution is ``?theme=``, then the ``theme`` cookie, then modern. An unknown
value is modern. A request that carries ``?theme=`` sets the cookie.

The boot gate in ``install`` refuses to serve when the registry, shell files,
stylesheets, season pane ids, and fragment rules disagree, or when a fixture
render does not echo the board registry with the same raw values across eras.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates

from ..paths import project_root
from . import queries

THEMES: tuple[str, ...] = ("modern", "era90", "era2010")
ERA_THEMES: tuple[str, ...] = ("era90", "era2010")
THEME_COOKIE = "theme"
THEME_MAX_AGE = 60 * 60 * 24 * 365

THEME_LABELS: dict[str, str] = {
    "modern": "Modern",
    "era90": "1998",
    "era2010": "2010",
}

# Mast order. Era2010 reuses it: no reached source captured an ESPN 2010 tab order.
_SITE_NAV: tuple[str, ...] = ("home", "seasons", "members", "versus", "records", "players")

# Eagle league-task order: home, seasons, record book, top 10, rules, then the rest.
_ERA90_NAV: tuple[str, ...] = (
    "home",
    "seasons",
    "records",
    "players",
    "scoring",
    "members",
    "versus",
)

NAV_ORDER: dict[str, tuple[str, ...]] = {
    "modern": _SITE_NAV,
    "era2010": _SITE_NAV,
    "era90": _ERA90_NAV,
}

# A None path is the season scoring sheet, filled when the page has a year.
NAV: dict[str, tuple[str | None, str]] = {
    "home": ("/", "Home"),
    "seasons": ("/seasons", "Seasons"),
    "members": ("/members", "Members"),
    "versus": ("/versus", "Versus"),
    "records": ("/records", "Records"),
    "players": ("/players", "Players"),
    "scoring": (None, "Scoring"),
}

# Dead off-site names stay text when one is still declared. C1a leaves this
# empty: Nando, SportsZone, CNN/SI and the rest of the Eagle farm are dead,
# and a dead farm is not the right rail. Live NFL.com and ESPN NFL anchors
# are written in the era90 shell. The gate still requires any label that
# remains here to render as text, never as an invented href.
ERA90_DEAD_LABELS: tuple[str, ...] = ()

# Existing season.html pane order. Not an ESPN 2010 tab order.
SEASON_PANES: tuple[tuple[str, str, str], ...] = (
    ("standings", "Standings", "fragments/board.html"),
    ("weeks", "Weeks", "fragments/games.html"),
    ("playoffs", "Playoffs", "fragments/games.html"),
    ("moves", "Moves", "fragments/board.html"),
    ("draft", "Draft", "fragments/board.html"),
    ("lineups", "Lineups", "fragments/board.html"),
    ("stacks", "Stacks", "fragments/board.html"),
)

REQUIRED_SLOTS: tuple[str, ...] = ("lead", "aside")
MARKS = frozenset({"", "is-leader", "is-record", "is-active-leader"})
_FOOTNOTE = "Bold marks a leader. Gold marks a record. Italic marks the active leader."

_ERA90_STANDINGS: tuple[str, ...] = (
    "manager",
    "wins",
    "losses",
    "ties",
    "points_for",
    "points_against",
)
_ERA2010_STANDINGS: tuple[str, ...] = (
    "manager",
    "record",
    "win_pct",
    "points_for",
    "points_against",
)
_DRAFT_KEYS: tuple[str, ...] = ("overall", "round", "manager", "player", "position")
_MOVES_KEYS: tuple[str, ...] = ("week", "left", "right", "gap")
_LINEUP_KEYS: tuple[str, ...] = ("manager", "weeks", "actual", "optimal", "bench")
_STACK_KEYS: tuple[str, ...] = (
    "manager",
    "stack_weeks",
    "combined",
    "points_for",
    "stack_share",
)

_FRAGMENT_FORBIDDEN: tuple[str, ...] = (
    "frame.",
    "{% extends",
    "{%extends",
    "theme=",
    "?theme",
    "bgcolor",
    "border=",
    "style=",
    "era90",
    "era2010",
    "data-theme",
    "<script",
    "javascript:",
    "onclick=",
)

_SHELL_FACT_TOKENS: tuple[str, ...] = (
    "points_for",
    "points_against",
    "display_name",
    "player_name",
    "starter_points",
    "manager_id",
    "transaction_id",
    "win_pct",
    "stack_share",
    "vorp_gap",
    "actual_points",
    "optimal_points",
    "left_on_bench",
)

_SHORT_NAMES: tuple[tuple[str, str], ...] = (
    ("Aaron Rodgers", "A. Rodgers"),
    ("Amon-Ra St. Brown", "A. St. Brown"),
    ("Ken Griffey Jr", "K. Griffey"),
    ("Odell Beckham Jr.", "O. Beckham"),
    ("Cher", "Cher"),
)

_templates: Jinja2Templates | None = None


class ThemeContractError(RuntimeError):
    """The process must not serve. ``install`` raises this and nothing else."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        detail = "\n".join(f"- {problem}" for problem in problems)
        super().__init__(f"theme contract failed:\n{detail}")


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    numeric: bool
    formatter: str


@dataclass(frozen=True)
class BoardSpec:
    note: str
    columns: tuple[Column, ...]
    projections: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class FragmentView:
    name: str
    label: str
    template: str


@dataclass(frozen=True)
class Pane:
    """One addressable section. ``load`` runs only when the pane is active."""

    name: str
    label: str
    template: str
    load: Callable[[], Mapping[str, object]]


@dataclass(frozen=True)
class Slot:
    name: str
    template: str


@dataclass(frozen=True)
class NavLink:
    key: str
    href: str
    label: str


@dataclass(frozen=True)
class ThemeChoice:
    theme_id: str
    label: str


@dataclass(frozen=True)
class WeekLink:
    week: int
    href: str


@dataclass(frozen=True)
class Frame:
    theme: str
    title: str
    nav: str
    pager: str
    fragments: tuple[FragmentView, ...]
    active: FragmentView
    slots: tuple[tuple[str, str], ...]
    path: str
    nav_links: tuple[NavLink, ...]
    theme_choices: tuple[ThemeChoice, ...]
    week_nav: tuple[WeekLink, ...]
    dead_labels: tuple[str, ...]

    @property
    def paged(self) -> bool:
        return len(self.fragments) > 1

    def slot(self, name: str) -> str | None:
        for key, template in self.slots:
            if key == name:
                return template
        return None

    def pane_href(self, name: str) -> str:
        return self.path + "?" + urlencode((("pane", name), ("theme", self.theme)))

    def theme_href(self, theme: str) -> str:
        chosen = theme if theme in THEMES else "modern"
        return self.path + "?" + urlencode((("pane", self.active.name), ("theme", chosen)))

    def carry(self, href: str) -> str:
        """Append the theme to a shell link. Fragments do not call this."""
        if not href.startswith("/") or href.startswith("//"):
            return href
        parts = urlsplit(href)
        pairs = [
            (key, value)
            for key, value in _query_pairs(parts.query)
            if key != "theme"
        ]
        pairs.append(("theme", self.theme))
        return urlunsplit(("", "", parts.path, urlencode(pairs), parts.fragment))


def _query_pairs(query: str) -> list[tuple[str, str]]:
    from urllib.parse import parse_qsl

    return parse_qsl(query, keep_blank_values=True)


def resolve_theme(request: Request) -> str:
    """``?theme=`` wins, including an unknown value (that becomes modern)."""
    asked = request.query_params.get("theme")
    if asked is not None:
        return asked if asked in THEMES else "modern"
    cooked = request.cookies.get(THEME_COOKIE)
    if cooked in THEMES:
        return cooked
    return "modern"


def persist_theme(request: Request, response: Response) -> Response:
    """Set the cookie only when the request itself chose a theme."""
    if request.url.path.startswith("/static"):
        return response
    if "theme" not in request.query_params:
        return response
    response.set_cookie(
        THEME_COOKIE,
        resolve_theme(request),
        max_age=THEME_MAX_AGE,
        path="/",
        samesite="lax",
        httponly=True,
    )
    return response


def rows_all_href(path: str, pane: str) -> str:
    """Theme-free View All link. The cookie keeps the theme."""
    return path + "?" + urlencode((("pane", pane), ("rows", "all")))


def numeral_hrefs(path: str, weeks: Sequence[int], *, theme: str) -> tuple[WeekLink, ...]:
    """Shell week numerals. The theme is chrome, so these links may carry it."""
    chosen = theme if theme in THEMES else "modern"
    links: list[WeekLink] = []
    for week in weeks:
        number = int(week)
        href = f"{path}/week/{number}?" + urlencode((("theme", chosen),))
        links.append(WeekLink(number, href))
    return tuple(links)


def tie_dash(value: object, theme: str) -> str:
    """Zero ties render as ``-`` in era themes. Modern keeps the digit."""
    ties = 0 if value is None or value == "" else int(value)
    if theme != "modern" and ties == 0:
        return "-"
    return str(ties)


def _short_name(name: str) -> str:
    """CBS 17 Sep 2009 grammar: ``A. Rodgers``.

    A particle stays with the surname (``Amon-Ra St. Brown`` → ``A. St. Brown``).
    Jr/III is dropped. The full name stays the cell's raw value.
    """
    parts = name.split()
    suffixes = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}
    particles = {"st", "st.", "de", "da", "van", "von", "del", "la", "le", "di"}
    while len(parts) > 2 and parts[-1].lower() in suffixes:
        parts.pop()
    if len(parts) < 2 or not parts[0]:
        return name
    start = len(parts) - 1
    while start > 1 and parts[start - 1].lower() in particles:
        start -= 1
    return f"{parts[0][0]}. {' '.join(parts[start:])}"


def _raw_text(value: object) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    try:
        decimal_value = Decimal(str(value))
    except Exception:
        return str(value)
    text = format(decimal_value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _cell_raw(column: Column, value: object) -> str:
    """Theme-independent raw value. Formatters must not change this."""
    if column.formatter == "tie":
        ties = 0 if value is None or value == "" else int(value)
        return str(ties)
    if column.formatter == "player":
        return "" if value is None else str(value).strip()
    return _raw_text(value)


def _format_text(value: object, theme: str) -> str:
    del theme
    if value is None:
        return "—"
    text = str(value).strip()
    return text or "—"


def _format_int(value: object, theme: str) -> str:
    del theme
    if value is None or value == "":
        return "0"
    return str(int(value))


def _format_places(places: int) -> Callable[[object, str], str]:
    def _format(value: object, theme: str) -> str:
        del theme
        if value is None or value == "":
            return "—"
        return f"{Decimal(str(value)):.{places}f}"

    return _format


def _format_share(value: object, theme: str) -> str:
    del theme
    if value is None or value == "":
        return "—"
    number = Decimal(str(value))
    if Decimal("0") <= number <= Decimal("1"):
        return f"{number * 100:.1f}%"
    return f"{number:.1f}%"


def _format_player(value: object, theme: str) -> str:
    name = "" if value is None else str(value).strip()
    if not name:
        return "—"
    if theme == "era2010":
        return _short_name(name)
    return name


FORMATTERS: dict[str, Callable[[object, str], str]] = {
    "text": _format_text,
    "int": _format_int,
    "num1": _format_places(1),
    "num2": _format_places(2),
    "num3": _format_places(3),
    "tie": tie_dash,
    "share": _format_share,
    "player": _format_player,
}


def _column(key: str, label: str, numeric: bool, formatter: str) -> Column:
    return Column(key, label, numeric, formatter)


def _all(*keys: str) -> dict[str, tuple[str, ...]]:
    return {theme: keys for theme in THEMES}


BOARDS: dict[str, BoardSpec] = {
    "standings": BoardSpec(
        note="W, L, and T are wins, losses, and ties. PF is points for. PA is points against.",
        columns=(
            _column("rank", "#", True, "int"),
            _column("manager", "Manager", False, "text"),
            _column("wins", "W", True, "int"),
            _column("losses", "L", True, "int"),
            _column("ties", "T", True, "tie"),
            _column("points_for", "PF", True, "num2"),
            _column("points_against", "PA", True, "num2"),
            _column("win_pct", "Pct", True, "num3"),
            _column("record", "W-L-T", True, "text"),
        ),
        projections={
            "modern": (
                "rank",
                "manager",
                "wins",
                "losses",
                "ties",
                "points_for",
                "points_against",
                "win_pct",
                "record",
            ),
            "era90": _ERA90_STANDINGS,
            "era2010": _ERA2010_STANDINGS,
        },
    ),
    "moves": BoardSpec(
        note="Gap is the VORP difference. Bold marks the side ahead when the trade is not even.",
        columns=(
            _column("week", "Week", True, "int"),
            _column("left", "Left", False, "text"),
            _column("right", "Right", False, "text"),
            _column("gap", "Gap", True, "num1"),
        ),
        projections=_all(*_MOVES_KEYS),
    ),
    "draft": BoardSpec(
        note="Bold marks the first overall pick.",
        columns=(
            _column("overall", "Pick", True, "int"),
            _column("round", "Round", True, "int"),
            _column("manager", "Manager", False, "text"),
            _column("player", "Player", False, "player"),
            _column("position", "Pos", False, "text"),
        ),
        projections=_all(*_DRAFT_KEYS),
    ),
    "lineups": BoardSpec(
        note="Actual and optimal are starter points. Bench is points left on the bench.",
        columns=(
            _column("manager", "Manager", False, "text"),
            _column("weeks", "Weeks", True, "int"),
            _column("actual", "Actual", True, "num1"),
            _column("optimal", "Optimal", True, "num1"),
            _column("bench", "Bench", True, "num1"),
        ),
        projections=_all(*_LINEUP_KEYS),
    ),
    "stacks": BoardSpec(
        note="Weeks are weeks a quarterback started with a teammate catcher. Share is combined points divided by points for.",
        columns=(
            _column("manager", "Manager", False, "text"),
            _column("stack_weeks", "Weeks", True, "int"),
            _column("combined", "Combined", True, "num2"),
            _column("points_for", "PF", True, "num2"),
            _column("stack_share", "Share", True, "share"),
        ),
        projections=_all(*_STACK_KEYS),
    ),
}


def _projection_keys(spec: BoardSpec, theme: str) -> tuple[str, ...]:
    if theme not in spec.projections:
        raise KeyError(f"{theme} has no projection")
    return spec.projections[theme]


def _note(spec: BoardSpec, theme: str, row_count: int) -> str:
    parts: list[str] = []
    if row_count == 0:
        parts.append("None posted.")
    keys = _projection_keys(spec, theme)
    # era90 standings glossary is one sentence under the grid. The shared
    # gold footnote stays on every other board so era2010 and modern notes
    # do not move.
    if theme == "era90" and "ties" in keys:
        parts.append(
            "W, L, and T are wins, losses, and ties; "
            "PF is points for and PA is points against, and a zero tie is shown as -."
        )
        return " ".join(part for part in parts if part)
    parts.append(spec.note)
    if "ties" in keys:
        parts.append("A zero tie is shown as -.")
    parts.append(_FOOTNOTE)
    return " ".join(part for part in parts if part)


def _mapped_cells(spec: BoardSpec, row: Mapping[str, object], theme: str) -> dict[str, dict[str, object]]:
    hrefs = row.get("_href") or {}
    marks = row.get("_mark") or {}
    if not isinstance(hrefs, Mapping) or not isinstance(marks, Mapping):
        raise ValueError("row _href and _mark must be mappings")
    cells: dict[str, dict[str, object]] = {}
    for column in spec.columns:
        href = hrefs.get(column.key) or ""
        mark = marks.get(column.key) or ""
        if not isinstance(href, str) or not isinstance(mark, str):
            raise ValueError(f"{column.key} href and mark must be strings")
        if mark not in MARKS:
            raise ValueError(f"unknown leader mark {mark}")
        if "theme=" in href:
            raise ValueError("cell href carries a theme token")
        if href and (not href.startswith("/") or href.startswith("//")):
            raise ValueError("cell href must be a root-relative path")
        value = row.get(column.key)
        cells[column.key] = {
            "key": column.key,
            "text": FORMATTERS[column.formatter](value, theme),
            "raw": _cell_raw(column, value),
            "numeric": column.numeric,
            "href": href,
            "mark": mark,
        }
    return cells


def present(
    board_id: str,
    rows: Sequence[Mapping[str, object]],
    theme: str,
    *,
    caption: str,
) -> dict[str, object]:
    """Project ``rows`` for one theme. Does not sort and does not query."""
    spec = BOARDS[board_id]
    chosen = theme if theme in THEMES else "modern"
    keys = _projection_keys(spec, chosen)
    by_key = {column.key: column for column in spec.columns}
    columns = [by_key[key] for key in keys]
    body: list[dict[str, object]] = []
    for row in rows:
        mapped = _mapped_cells(spec, row, chosen)
        body.append({"cells": [mapped[key] for key in keys]})
    return {
        "caption": caption,
        "columns": [
            {"key": column.key, "label": column.label, "numeric": column.numeric}
            for column in columns
        ],
        "rows": body,
        "note": _note(spec, chosen, len(rows)),
    }


def _nav_links(theme: str, year: int | None) -> tuple[NavLink, ...]:
    items: list[NavLink] = []
    for key in NAV_ORDER[theme]:
        path, label = NAV[key]
        if path is None:
            if year is None:
                continue
            path = f"/seasons/{year}/scoring"
        items.append(NavLink(key, path, label))
    return tuple(items)


def _frame(
    *,
    theme: str,
    title: str,
    nav: str,
    pager: str,
    fragments: tuple[FragmentView, ...],
    active: FragmentView,
    slots: Mapping[str, str],
    path: str,
    year: int | None,
    week_nav: Sequence[int],
) -> Frame:
    return Frame(
        theme=theme,
        title=title,
        nav=nav,
        pager=pager,
        fragments=fragments,
        active=active,
        slots=tuple(slots.items()),
        path=path,
        nav_links=_nav_links(theme, year),
        theme_choices=tuple(
            ThemeChoice(theme_id, THEME_LABELS[theme_id]) for theme_id in THEMES
        ),
        week_nav=numeral_hrefs(path, week_nav, theme=theme),
        dead_labels=ERA90_DEAD_LABELS if theme == "era90" else (),
    )


def render_panes(
    request: Request,
    *,
    title: str,
    nav: str,
    panes: Sequence[Pane],
    slots: Sequence[Slot] = (),
    context: Mapping[str, object] | None = None,
    pager: str = "",
) -> HTMLResponse:
    """Render one era shell. Only the active pane's loader runs."""
    if _templates is None:
        raise RuntimeError("themes.install() was not called")
    theme = resolve_theme(request)
    if theme not in ERA_THEMES:
        raise RuntimeError("render_panes serves era shells; modern stays on page()")
    if not panes:
        raise ValueError("a themed page needs at least one pane")
    names = [pane.name for pane in panes]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate pane name on {title!r}")
    for pane in panes:
        if re.fullmatch(r"[a-z][a-z0-9]*", pane.name) is None:
            raise ValueError(f"pane name must be a slug: {pane.name}")
    slot_map: dict[str, str] = {}
    for slot in slots:
        if slot.name not in REQUIRED_SLOTS:
            raise ValueError(f"unknown slot {slot.name}")
        if slot.name in slot_map:
            raise ValueError(f"duplicate slot {slot.name}")
        slot_map[slot.name] = slot.template
    missing = [name for name in REQUIRED_SLOTS if name not in slot_map]
    if missing:
        raise ValueError(f"missing slots: {missing}")
    env = _templates.env
    for pane in panes:
        env.get_template(pane.template)
    for template in slot_map.values():
        env.get_template(template)

    base = dict(context or {})
    if "frame" in base:
        raise ValueError("context cannot include frame")
    year = base.get("year")
    if year is not None and not isinstance(year, int):
        raise ValueError("year must be int")

    requested = request.query_params.get("pane")
    active_name = requested if isinstance(requested, str) and requested in names else names[0]
    active_pane = next(pane for pane in panes if pane.name == active_name)
    if os.environ.get("NU_CHOATE_PERF") == "1":
        print(f"NU_CHOATE_PERF pane {active_pane.name}", file=sys.stderr, flush=True)
    loaded = dict(active_pane.load())
    week_values = loaded.pop("week_nav", ())
    overlap = set(base) & set(loaded)
    if overlap:
        raise ValueError(f"loader overwrites context keys: {sorted(overlap)}")
    base.update(loaded)
    weeks = tuple(int(week) for week in (week_values or ()))

    fragments = tuple(FragmentView(pane.name, pane.label, pane.template) for pane in panes)
    active = FragmentView(active_pane.name, active_pane.label, active_pane.template)
    frame = _frame(
        theme=theme,
        title=title,
        nav=nav,
        pager=pager,
        fragments=fragments,
        active=active,
        slots=slot_map,
        path=request.url.path,
        year=year if isinstance(year, int) else None,
        week_nav=weeks,
    )
    payload: dict[str, object] = {**base, "frame": frame, "title": title, "nav": nav}
    return _templates.TemplateResponse(request, f"shells/{theme}.html", payload)


def _same(value: object, high: float | None) -> bool:
    if value is None or high is None:
        return False
    return round(float(value), 4) == round(high, 4)


def _max_number(values: object) -> float | None:
    found = [float(value) for value in values if value is not None]  # type: ignore[union-attr]
    return max(found) if found else None


def _path(prefix: str, identifier: object) -> str:
    if identifier is None or str(identifier).strip() == "":
        return ""
    return f"{prefix}/{quote(str(identifier), safe='')}"


def _points(value: object) -> str:
    if value is None:
        return "—"
    return f"{Decimal(str(value)):.2f}"


def _higher(home: float | None, away: float | None, side: str) -> str:
    if home is None or away is None or round(home, 4) == round(away, 4):
        return ""
    if (side == "home" and home > away) or (side == "away" and away > home):
        return "is-leader"
    return ""


def _game_view(row: Mapping[str, object]) -> dict[str, object]:
    if "home_manager_id" in row or "away_manager_id" in row:
        home_id = row.get("home_manager_id")
        away_id = row.get("away_manager_id")
    else:
        home_id = row.get("home_id")
        away_id = row.get("away_id")
    home_pts = row.get("home_points")
    away_pts = row.get("away_points")
    home_n = None if home_pts is None else float(home_pts)  # type: ignore[arg-type]
    away_n = None if away_pts is None else float(away_pts)  # type: ignore[arg-type]
    home_name = row.get("home_name") or "—"
    away_name = row.get("away_name") or "—"
    return {
        "home": str(home_name),
        "home_href": _path("/members", home_id),
        "home_pts": _points(home_pts),
        "home_mark": _higher(home_n, away_n, "home"),
        "away": str(away_name),
        "away_href": _path("/members", away_id),
        "away_pts": _points(away_pts),
        "away_mark": _higher(home_n, away_n, "away"),
        "kind_label": "",
    }


def _tree_groups(tree: Mapping[str, object] | None, fallback: str) -> list[dict[str, object]]:
    if not tree:
        return []
    groups: list[dict[str, object]] = []
    for round_ in tree.get("rounds") or []:  # type: ignore[union-attr]
        label = str(round_.get("label") or fallback)
        matches = round_.get("matches") or []
        groups.append(
            {
                "week": int(round_["week"]),
                "label": label,
                "games": [_game_view(match) for match in matches],
            }
        )
    by_week: dict[int, dict[str, object]] = {}
    for match in tree.get("placements") or []:  # type: ignore[union-attr]
        week = int(match.get("week") or 0)
        label = str(match.get("place_label") or fallback)
        group = by_week.get(week)
        if group is None:
            group = {"week": week, "label": label, "games": []}
            by_week[week] = group
        games = group["games"]
        assert isinstance(games, list)
        games.append(_game_view(match))
    groups.extend(by_week[key] for key in sorted(by_week))
    return groups


def _standings_board(year: int, theme: str) -> dict[str, object]:
    rows = queries.standings(year)
    high = _max_number(row.get("points_for") for row in rows)
    body: list[dict[str, object]] = []
    for row in rows:
        wins = int(row.get("wins") or 0)
        losses = int(row.get("losses") or 0)
        ties = int(row.get("ties") or 0)
        marks: dict[str, str] = {}
        if row.get("champion"):
            marks["manager"] = "is-leader"
        elif int(row.get("rank") or 0) == 1:
            marks["manager"] = "is-active-leader"
        if _same(row.get("points_for"), high):
            marks["points_for"] = "is-record"
        body.append(
            {
                "rank": row.get("rank"),
                "manager": row.get("display_name") or "",
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "points_for": row.get("points_for"),
                "points_against": row.get("points_against"),
                "win_pct": row.get("win_pct"),
                "record": f"{wins}-{losses}-{ties}",
                "_href": {"manager": _path("/members", row.get("manager_id"))},
                "_mark": marks,
            }
        )
    return present("standings", body, theme, caption=f"{year} standings")


def _moves_board(year: int, theme: str) -> dict[str, object]:
    rows = queries._season_trades(year)
    body: list[dict[str, object]] = []
    for row in rows:
        verdict = row.get("verdict") or {}
        ahead = verdict.get("kind") not in (None, "even")
        winner = row.get("winner_id")
        marks = {}
        if ahead and winner == row.get("left_id"):
            marks["left"] = "is-leader"
        if ahead and winner == row.get("right_id"):
            marks["right"] = "is-leader"
        body.append(
            {
                "week": row.get("week"),
                "left": row.get("left_name") or "",
                "right": row.get("right_name") or "",
                "gap": row.get("vorp_gap"),
                "_href": {
                    "week": f"/seasons/{year}/trades/{quote(str(row.get('transaction_id') or ''), safe='')}",
                    "left": _path("/members", row.get("left_id")),
                    "right": _path("/members", row.get("right_id")),
                },
                "_mark": marks,
            }
        )
    return present("moves", body, theme, caption=f"{year} trades")


def _draft_board(year: int, theme: str) -> dict[str, object]:
    page = queries.draft_page(year)
    picks = [] if not page else list(page["picks"])
    high = _max_number(row.get("ros_vorp") for row in picks)
    body: list[dict[str, object]] = []
    for row in picks:
        overall = int(row.get("overall") or 0)
        mark = ""
        if overall == 1:
            mark = "is-leader"
        elif _same(row.get("ros_vorp"), high):
            mark = "is-record"
        body.append(
            {
                "overall": overall,
                "round": row.get("round"),
                "manager": row.get("manager_name") or "",
                "player": row.get("player_name") or "",
                "position": row.get("position") or "",
                "_href": {
                    "manager": _path("/members", row.get("manager_id")),
                    "player": _path("/players", row.get("player_id")),
                },
                "_mark": {"player": mark} if mark else {},
            }
        )
    return present("draft", body, theme, caption=f"{year} draft")


def _lineups_board(year: int, theme: str) -> dict[str, object]:
    packed = queries._season_lineups(year)
    coaches = list(packed.get("coaches") or [])
    high = _max_number(row.get("actual_points") for row in coaches)
    body: list[dict[str, object]] = []
    for row in coaches:
        marks = {}
        if _same(row.get("actual_points"), high):
            marks["manager"] = "is-leader"
            marks["actual"] = "is-record"
        body.append(
            {
                "manager": row.get("manager_name") or "",
                "weeks": row.get("weeks"),
                "actual": row.get("actual_points"),
                "optimal": row.get("optimal_points"),
                "bench": row.get("left_on_bench"),
                "_href": {"manager": _path("/members", row.get("manager_id"))},
                "_mark": marks,
            }
        )
    return present("lineups", body, theme, caption=f"{year} lineups")


def _stacks_board(year: int, theme: str) -> dict[str, object]:
    packed = queries._season_stacks(year)
    managers = list(packed.get("managers") or [])
    high = _max_number(row.get("stack_weeks") for row in managers)
    body: list[dict[str, object]] = []
    for row in managers:
        marks = {}
        if _same(row.get("stack_weeks"), high):
            marks["manager"] = "is-leader"
            marks["stack_weeks"] = "is-record"
        body.append(
            {
                "manager": row.get("manager_name") or "",
                "stack_weeks": row.get("stack_weeks"),
                "combined": row.get("combined_points"),
                "points_for": row.get("points_for"),
                "stack_share": row.get("stack_share"),
                "_href": {"manager": _path("/members", row.get("manager_id"))},
                "_mark": marks,
            }
        )
    return present("stacks", body, theme, caption=f"{year} stacks")


def _week_groups(year: int) -> tuple[list[dict[str, object]], list[int]]:
    schedule = queries.season_schedule(year)
    groups: list[dict[str, object]] = []
    weeks: list[int] = []
    for week, games in schedule["regular"]:
        weeks.append(int(week))
        groups.append(
            {
                "week": int(week),
                "label": "",
                "games": [_game_view(game) for game in games],
            }
        )
    return groups, weeks


def _playoff_groups(year: int) -> tuple[list[dict[str, object]], list[int]]:
    schedule = queries.season_schedule(year)
    groups: list[dict[str, object]] = []
    groups.extend(_tree_groups(schedule.get("winners_tree"), "Playoff"))
    groups.extend(_tree_groups(schedule.get("consolation_tree"), "Consolation"))
    if not groups:
        # Bracket JSON is optional. Posted playoff games still belong on the pane.
        groups = _posted_playoff_groups(year)
    weeks = sorted({int(group["week"]) for group in groups})
    return groups, weeks


def _posted_playoff_groups(year: int) -> list[dict[str, object]]:
    rows = queries.fetchall(
        """
        SELECT
            m.id,
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
          AND m.kind IN ('playoff', 'consolation')
          AND (m.home_points <> 0 OR m.away_points <> 0)
        ORDER BY m.week, m.kind, m.id
        """,
        {"year": year},
    )
    labels = {"playoff": "Playoff", "consolation": "Consolation"}
    by_week: dict[int, dict[str, object]] = {}
    for row in rows:
        week = int(row["week"])
        group = by_week.get(week)
        if group is None:
            group = {
                "week": week,
                "label": labels.get(str(row.get("kind") or ""), ""),
                "games": [],
            }
            by_week[week] = group
        games = group["games"]
        assert isinstance(games, list)
        games.append(_game_view(row))
    return [by_week[week] for week in sorted(by_week)]


def season_document(request: Request, year: int) -> HTMLResponse:
    """Era season page. Modern never reaches this function."""
    theme = resolve_theme(request)
    if theme == "modern":
        raise RuntimeError("modern season documents stay on page()")
    current = queries.season_row(year)
    if current is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")

    def standings() -> dict[str, object]:
        return {"board": _standings_board(year, theme)}

    def weeks() -> dict[str, object]:
        groups, week_nums = _week_groups(year)
        return {"week_groups": groups, "week_nav": week_nums}

    def playoffs() -> dict[str, object]:
        groups, week_nums = _playoff_groups(year)
        return {"week_groups": groups, "week_nav": week_nums}

    def moves() -> dict[str, object]:
        return {"board": _moves_board(year, theme)}

    def draft() -> dict[str, object]:
        return {"board": _draft_board(year, theme)}

    def lineups() -> dict[str, object]:
        return {"board": _lineups_board(year, theme)}

    def stacks() -> dict[str, object]:
        return {"board": _stacks_board(year, theme)}

    loaders: dict[str, Callable[[], Mapping[str, object]]] = {
        "standings": standings,
        "weeks": weeks,
        "playoffs": playoffs,
        "moves": moves,
        "draft": draft,
        "lineups": lineups,
        "stacks": stacks,
    }
    if set(loaders) != {name for name, _, _ in SEASON_PANES}:
        raise RuntimeError("season loader map drifted from the pane catalog")
    if theme == "era90":
        # Numeral week nav is era90 grammar on every season pane, not only
        # the weeks list. Weeks and playoffs already return the numbers.
        def _with_week_nav(load: Callable[[], Mapping[str, object]]) -> Callable[[], Mapping[str, object]]:
            def wrapped() -> Mapping[str, object]:
                payload = dict(load())
                if not payload.get("week_nav"):
                    payload["week_nav"] = queries.scored_weeks(year)
                return payload

            return wrapped

        loaders = {name: _with_week_nav(fn) for name, fn in loaders.items()}
    panes = tuple(Pane(name, label, template, loaders[name]) for name, label, template in SEASON_PANES)
    context: dict[str, object] = {"year": year, "current": current}
    if theme == "era90":
        context["last_updated"] = queries.era90_last_updated()
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
        context=context,
    )


_FIXTURE_CURRENT: dict[str, object] = {
    "platform": "sleeper",
    "champion": "Alex Coletti",
    "champion_id": "alex-coletti",
    "runner_up": "Jamie Active",
}

_FIXTURES: dict[str, list[dict[str, object]]] = {
    "standings": [
        {
            "rank": 1,
            "manager": "Alex Coletti",
            "wins": 10,
            "losses": 4,
            "ties": 0,
            "points_for": Decimal("1600.50"),
            "points_against": Decimal("1400.25"),
            "win_pct": Decimal("0.714"),
            "record": "10-4-0",
            "_href": {"manager": "/members/alex-coletti"},
            "_mark": {"manager": "is-leader", "points_for": "is-record"},
        },
        {
            "rank": 2,
            "manager": "Jamie Active",
            "wins": 9,
            "losses": 5,
            "ties": 1,
            "points_for": Decimal("1500"),
            "points_against": Decimal("1499.50"),
            "win_pct": Decimal("0.633"),
            "record": "9-5-1",
            "_href": {"manager": "/members/jamie-active"},
            "_mark": {"manager": "is-active-leader"},
        },
    ],
    "moves": [
        {
            "week": 4,
            "left": "Alex Coletti",
            "right": "Jamie Active",
            "gap": Decimal("12.5"),
            "_href": {
                "week": "/seasons/2025/trades/abc",
                "left": "/members/alex-coletti",
                "right": "/members/jamie-active",
            },
            "_mark": {"left": "is-leader"},
        }
    ],
    "draft": [
        {
            "overall": 1,
            "round": 1,
            "manager": "Alex Coletti",
            "player": "Aaron Rodgers",
            "position": "QB",
            "_href": {"manager": "/members/alex-coletti", "player": "/players/100"},
            "_mark": {"player": "is-leader"},
        },
        {
            "overall": 12,
            "round": 2,
            "manager": "Jamie Active",
            "player": "Amon-Ra St. Brown",
            "position": "WR",
            "_href": {"manager": "/members/jamie-active", "player": "/players/200"},
            "_mark": {},
        },
    ],
    "lineups": [
        {
            "manager": "Alex Coletti",
            "weeks": 14,
            "actual": Decimal("150.5"),
            "optimal": Decimal("160.0"),
            "bench": Decimal("9.5"),
            "_href": {"manager": "/members/alex-coletti"},
            "_mark": {"manager": "is-leader", "actual": "is-record"},
        }
    ],
    "stacks": [
        {
            "manager": "Alex Coletti",
            "stack_weeks": 8,
            "combined": Decimal("320.25"),
            "points_for": Decimal("1281"),
            "stack_share": Decimal("0.25"),
            "_href": {"manager": "/members/alex-coletti"},
            "_mark": {"manager": "is-leader", "stack_weeks": "is-record"},
        }
    ],
}


def _request(query: str, cookie: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie is not None:
        headers.append((b"cookie", f"{THEME_COOKIE}={cookie}".encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/seasons/2025",
        "raw_path": b"/seasons/2025",
        "root_path": "",
        "query_string": query.encode(),
        "headers": headers,
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 80),
    }
    return Request(scope)


def _between(text: str, start: str, end: str) -> str | None:
    opening = text.find(start)
    if opening < 0:
        return None
    closing = text.find(end, opening + len(start))
    if closing < 0:
        return None
    return text[opening + len(start) : closing]


def _css_code(text: str) -> str:
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "".join(stripped.split()).lower()


def _labels(html: str) -> list[str]:
    return re.findall(r"<th[^>]*>([^<]*)</th>", html)


def collect_contract_problems(
    templates: Jinja2Templates,
    *,
    root: Path | None = None,
) -> list[str]:
    """Return every contract violation. Empty means the process may serve."""
    problems: list[str] = []
    root = root or project_root()
    problems.extend(_check_resolution())
    problems.extend(_check_registry())
    problems.extend(_check_files(root))
    if problems:
        return problems
    try:
        problems.extend(_check_fixture_render(templates.env))
    except Exception as exc:
        problems.append(f"fixture render failed: {exc}")
    return problems


def _check_resolution() -> list[str]:
    problems: list[str] = []
    cases = (
        ("", None, "modern"),
        ("theme=era90", None, "era90"),
        ("theme=era2010", None, "era2010"),
        ("theme=modern", None, "modern"),
        ("theme=nope", None, "modern"),
        ("theme=", None, "modern"),
        ("theme=nope", "era90", "modern"),
        ("", "era90", "era90"),
        ("", "nope", "modern"),
        ("theme=era2010", "era90", "era2010"),
    )
    for query, cookie, expected in cases:
        got = resolve_theme(_request(query, cookie))
        if got != expected:
            problems.append(f"resolve {query!r} cookie={cookie!r} -> {got}, expected {expected}")
    chosen = _request("theme=era90")
    response = HTMLResponse("ok")
    persist_theme(chosen, response)
    cookie_header = response.headers.get("set-cookie", "")
    if "theme=era90" not in cookie_header or "HttpOnly" not in cookie_header:
        problems.append(f"themed request did not set the theme cookie: {cookie_header!r}")
    if f"Max-Age={THEME_MAX_AGE}" not in cookie_header:
        problems.append("theme cookie does not persist across sessions")
    silent = HTMLResponse("ok")
    persist_theme(_request(""), silent)
    if silent.headers.get("set-cookie"):
        problems.append("a request without ?theme= rewrote the cookie")
    sample = rows_all_href("/seasons/2025", "draft")
    if sample != "/seasons/2025?pane=draft&rows=all" or "theme=" in sample:
        problems.append(f"View All href is not a theme-free link: {sample}")
    weeks = numeral_hrefs("/seasons/2025", (1, 16), theme="era90")
    if [link.week for link in weeks] != [1, 16] or any("theme=era90" not in link.href for link in weeks):
        problems.append("week numerals are not real themed shell links")
    for full, short in _SHORT_NAMES:
        if _short_name(full) != short:
            problems.append(f"player formatter {full!r} -> {_short_name(full)!r}, expected {short!r}")
    if tie_dash(0, "era90") != "-" or tie_dash(0, "era2010") != "-" or tie_dash(0, "modern") != "0":
        problems.append("tie_dash is not the shared zero-tie glyph")
    if tie_dash(1, "era90") != "1":
        problems.append("tie_dash rewrote a non-zero tie")
    return problems


def _check_registry() -> list[str]:
    problems: list[str] = []
    if set(NAV_ORDER) != set(THEMES) or set(THEME_LABELS) != set(THEMES):
        problems.append("theme labels or nav order drifted from the registry")
    if NAV_ORDER["era90"] != _ERA90_NAV or NAV_ORDER["era2010"] != _SITE_NAV:
        problems.append("era nav order drifted")
    if NAV_ORDER["modern"] != _SITE_NAV:
        problems.append("modern nav order drifted from the mast")
    for order in NAV_ORDER.values():
        missing = [key for key in order if key not in NAV]
        if missing:
            problems.append(f"nav keys missing from NAV: {missing}")
    links = _nav_links("era90", 2025)
    if tuple(link.key for link in links) != _ERA90_NAV:
        problems.append("era90 rail did not follow the league-task order")
    scoring = next(link for link in links if link.key == "scoring")
    if scoring.href != "/seasons/2025/scoring":
        problems.append("era90 scoring task is not the season scoring sheet")
    pane_names = [name for name, _, _ in SEASON_PANES]
    if pane_names != [
        "standings",
        "weeks",
        "playoffs",
        "moves",
        "draft",
        "lineups",
        "stacks",
    ]:
        problems.append(f"season pane catalog drifted: {pane_names}")
    if len(pane_names) != len(set(pane_names)):
        problems.append("duplicate season pane id")
    board_panes = {name for name, _, template in SEASON_PANES if template == "fragments/board.html"}
    if set(BOARDS) != board_panes:
        problems.append(f"board registry {sorted(BOARDS)} != table panes {sorted(board_panes)}")
    for name, _, template in SEASON_PANES:
        if name in ("weeks", "playoffs") and template != "fragments/games.html":
            problems.append(f"{name} is not the games fragment")
    for board_id, spec in BOARDS.items():
        if set(spec.projections) != set(THEMES):
            problems.append(f"{board_id} projections do not cover every theme")
        keys = [column.key for column in spec.columns]
        if len(keys) != len(set(keys)):
            problems.append(f"{board_id} has a duplicate column")
        known = set(keys)
        for column in spec.columns:
            if column.formatter not in FORMATTERS:
                problems.append(f"{board_id}.{column.key} formatter {column.formatter} is unknown")
        for theme, projection in spec.projections.items():
            if len(projection) != len(set(projection)):
                problems.append(f"{board_id} {theme} projection repeats a column")
            unknown = [key for key in projection if key not in known]
            if unknown:
                problems.append(f"{board_id} {theme} projection has unknown keys {unknown}")
        if board_id not in _FIXTURES:
            problems.append(f"{board_id} has no fixture row")
    standings = BOARDS["standings"]
    if standings.projections.get("era90") != _ERA90_STANDINGS:
        problems.append("era90 standings projection is not the small grid")
    if standings.projections.get("era2010") != _ERA2010_STANDINGS:
        problems.append("era2010 standings projection drifted")
    tie_column = next(column for column in standings.columns if column.key == "ties")
    if tie_column.formatter != "tie":
        problems.append("the ties column does not use tie_dash")
    player_column = next(column for column in BOARDS["draft"].columns if column.key == "player")
    if player_column.formatter != "player":
        problems.append("the draft player column does not use the shared name formatter")
    return problems


def _check_files(root: Path) -> list[str]:
    problems: list[str] = []
    shells = root / "hub" / "templates" / "shells"
    fragments = root / "hub" / "templates" / "fragments"
    styles = root / "hub" / "static" / "themes"
    base_path = root / "hub" / "templates" / "base.html"
    season_path = root / "hub" / "templates" / "season.html"
    if not base_path.is_file() or not season_path.is_file():
        problems.append("base.html or season.html is missing")
        return problems
    base = base_path.read_text(encoding="utf-8")
    if base.count('href="/static/hub.css"') != 1:
        problems.append("modern skin must link hub.css once from base.html")
    if 'src="/static/hub.js"' not in base:
        problems.append("modern page dropped hub.js")
    if base.count('class="theme-switch"') != 1:
        problems.append("base.html must carry exactly one theme switcher")
    found = re.findall(r'href="\?theme=([^"]+)"[^>]*>([^<]+)</a>', base)
    expected = [(theme, THEME_LABELS[theme]) for theme in THEMES]
    if found != expected:
        problems.append(f"base.html switcher drifted from the registry: {found}")
    season = season_path.read_text(encoding="utf-8")
    sections = re.findall(
        r'<section class="js-season-pane" id="([^"]+)" data-tab="([^"]+)">',
        season,
    )
    catalog = [(name, name) for name, _, _ in SEASON_PANES]
    if sections != catalog:
        problems.append(f"season sections drifted from the pane catalog: {sections}")
    if (shells / "modern.html").is_file():
        problems.append("modern has no shell; it is the legacy page() path")
    if (styles / "modern.css").is_file():
        problems.append("modern skin is hub.css via base.html, not themes/modern.css")
    for name in ("_fragment.html", "_slot.html", "_week_nav.html"):
        if not (shells / name).is_file():
            problems.append(f"missing shell mount {name}")
    mount = (shells / "_fragment.html").read_text(encoding="utf-8") if (shells / "_fragment.html").is_file() else ""
    if "<!--a2-fragment-->" not in mount or "<!--/a2-fragment-->" not in mount:
        problems.append("fragment mount lost its markers")
    if "frame.active.template" not in mount:
        problems.append("fragment mount does not include the active template")
    week_nav = (shells / "_week_nav.html").read_text(encoding="utf-8") if (shells / "_week_nav.html").is_file() else ""
    if "Results" not in week_nav or "item.href" not in week_nav:
        problems.append("week numeral row is not a shell include of real links")
    for theme in ERA_THEMES:
        path = shells / f"{theme}.html"
        css_path = styles / f"{theme}.css"
        if not path.is_file():
            problems.append(f"missing shell {path}")
            continue
        if not css_path.is_file():
            problems.append(f"missing stylesheet {css_path}")
            continue
        text = path.read_text(encoding="utf-8")
        if text.count("shells/_fragment.html") != 1:
            problems.append(f"{theme} shell must mount the fragment once")
        for snippet in (
            'slot_name="lead"',
            'slot_name="aside"',
            "shells/_week_nav.html",
            "frame.theme_choices",
            "frame.theme_href",
            "frame.nav_links",
            "frame.pane_href",
            "frame.paged",
        ):
            if snippet not in text:
                problems.append(f"{theme} shell is missing {snippet}")
        if "fragments/" in text or ".template" in text:
            problems.append(f"{theme} shell names content; use the mount")
        if text.count('rel="stylesheet"') != 1 or f"/static/themes/{theme}.css" not in text:
            problems.append(f"{theme} shell must link exactly its own stylesheet")
        if "hub.css" in text or "hub.js" in text:
            problems.append(f"{theme} shell pulls a modern asset")
        for token in _SHELL_FACT_TOKENS:
            if token in text:
                problems.append(f"{theme} shell contains stat fact {token}")
        lowered = text.lower()
        table_count = lowered.count("<table")
        if theme == "era90":
            if table_count != 1:
                problems.append("era90 shell must contain exactly one layout table")
            for snippet in (
                'class="portal"',
                'class="band"',
                'class="rail-left"',
                'class="rail-right"',
                'class="link-box"',
                'class="numeral-row"',
                "loop.index",
                "frame.dead_labels",
                "Email the COMMISSIONER",
            ):
                if snippet not in text:
                    problems.append(f"era90 shell is missing {snippet}")
            if text.count('class="link-box"') != 1:
                problems.append("era90 right rail must be exactly one link box")
        else:
            if table_count:
                problems.append("era2010 shell contains a layout table")
            if "frame.dead_labels" in text or "dead-label" in text:
                problems.append("era2010 shell took the era90 link farm")
            for snippet in ('class="tabs"', "fragment.label", 'class="shell"'):
                if snippet not in text:
                    problems.append(f"era2010 shell is missing {snippet}")
            if any(name in text for name, _, _ in SEASON_PANES):
                problems.append("era2010 shell hardcodes a pane id; loop the catalog")
        css = css_path.read_text(encoding="utf-8")
        if "hub.css" in css or "hub.js" in css:
            problems.append(f"{theme}.css imports a modern asset")
        folded = _css_code(css)
        if "background:#fff" not in folded and "background:#ffffff" not in folded:
            problems.append(f"{theme} stat surface is not light")
        for klass in (".is-leader", ".is-record", ".is-active-leader"):
            if klass not in css:
                problems.append(f"{theme}.css is missing {klass}")
        if theme == "era90":
            for token in ("display:flex", "display:inline-flex", "display:grid", "display:inline-grid"):
                if token in folded:
                    problems.append(f"era90 stylesheet used {token}")
            if "#660000" not in folded or "background:#660000" not in folded:
                problems.append("era90 stylesheet is missing the #660000 commissioner band")
            if "#0000ff" not in folded:
                problems.append("era90 links are not blue")
        if theme == "era2010":
            if "width:960px" not in folded:
                problems.append("era2010 shell is not the fixed 960 scaffold")
            if "#0645ad" not in folded:
                problems.append("era2010 links are not blue")
    if not fragments.is_dir():
        problems.append("fragments directory is missing")
        return problems
    tables: list[str] = []
    for path in sorted(fragments.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        folded = text.lower()
        if "<table" in folded:
            tables.append(path.name)
        if path.name == "stat_table.html" and folded.count("<table") != 1:
            problems.append("stat_table.html must contain exactly one table")
        for token in _FRAGMENT_FORBIDDEN:
            if token in text:
                problems.append(f"{path.name} contains {token!r}")
        if re.search(r"theme", text, re.I):
            problems.append(f"{path.name} mentions theme")
    if tables != ["stat_table.html"]:
        problems.append(f"<table is not confined to stat_table.html: {tables}")
    return problems


def _check_fixture_render(env: object) -> list[str]:
    problems: list[str] = []
    rendered: dict[str, dict[str, str]] = {}
    for board_id, rows in _FIXTURES.items():
        spec = BOARDS[board_id]
        raws: dict[str, list[list[str]]] = {}
        rendered[board_id] = {}
        for theme in THEMES:
            board = present(board_id, rows, theme, caption=f"Fixture {board_id}")
            html = env.get_template("fragments/board.html").render(board=board)  # type: ignore[attr-defined]
            rendered[board_id][theme] = html
            if "theme=" in html:
                problems.append(f"{board_id} {theme} fragment carries a theme token")
            raws[theme] = []
            for row in rows:
                mapped = _mapped_cells(spec, row, theme)
                raws[theme].append([str(mapped[column.key]["raw"]) for column in spec.columns])
                keys = _projection_keys(spec, theme)
                labels = [next(column.label for column in spec.columns if column.key == key) for key in keys]
                if _labels(html) != labels:
                    problems.append(f"{board_id} {theme} headers {_labels(html)} != {labels}")
                for key in keys:
                    text = str(mapped[key]["text"])
                    if f">{escape(text)}<" not in html:
                        problems.append(f"{board_id} {theme} did not echo {key}={text!r}")
        if raws["era90"] != raws["era2010"] or raws["era90"] != raws["modern"]:
            problems.append(f"{board_id} raw values diverged across themes")
    same = ("moves", "lineups", "stacks")
    for board_id in same:
        if rendered[board_id]["era90"] != rendered[board_id]["era2010"]:
            problems.append(f"{board_id} fragment diverged across eras without a projection change")
        if rendered[board_id]["era90"] != rendered[board_id]["modern"]:
            problems.append(f"{board_id} modern projection diverged from the era fragment")
    if rendered["standings"]["era90"] == rendered["standings"]["era2010"]:
        problems.append("era90 standings rendered the same grid as era2010")
    if rendered["draft"]["era90"] != rendered["draft"]["modern"]:
        problems.append("draft full-name projection diverged between era90 and modern")
    if rendered["draft"]["era90"] == rendered["draft"]["era2010"]:
        problems.append("era2010 draft did not apply the short player name")
    draft_era = rendered["draft"]["era2010"]
    draft_full = rendered["draft"]["era90"]
    if ">A. Rodgers<" not in draft_era or ">A. St. Brown<" not in draft_era:
        problems.append("era2010 draft did not echo the short player names")
    if ">Aaron Rodgers<" not in draft_full or ">Amon-Ra St. Brown<" not in draft_full:
        problems.append("era90 draft did not echo the full player names")
    if "Aaron Rodgers" in draft_era or "Amon-Ra St. Brown" in draft_era:
        problems.append("era2010 draft showed a full player name")
    era90_standings = rendered["standings"]["era90"]
    if ">-</td>" not in era90_standings:
        problems.append("era90 zero ties did not render as -")
    if ">0</td>" in era90_standings:
        problems.append("era90 standings still showed a zero tie digit")
    for theme in ERA_THEMES:
        for klass in ("is-leader", "is-record", "is-active-leader"):
            if klass not in rendered["standings"][theme]:
                problems.append(f"{theme} standings missing {klass}")
    games = env.get_template("fragments/games.html").render(  # type: ignore[attr-defined]
        year=2025,
        week_groups=[
            {
                "week": 1,
                "label": "",
                "games": [
                    {
                        "home": "Alex Coletti",
                        "home_href": "/members/alex-coletti",
                        "home_pts": "100.00",
                        "home_mark": "is-leader",
                        "away": "Jamie Active",
                        "away_href": "/members/jamie-active",
                        "away_pts": "90.00",
                        "away_mark": "",
                        "kind_label": "",
                    }
                ],
            }
        ],
    )
    if "theme=" in games or 'href="/seasons/2025/week/1"' not in games:
        problems.append("week content fragment is not a theme-free document link")
    view = present("draft", _FIXTURES["draft"], "era2010", caption="Fixture draft")
    view["more_href"] = rows_all_href("/seasons/2025", "draft")
    more_html = env.get_template("fragments/board.html").render(board=view)  # type: ignore[attr-defined]
    if "View all" not in more_html or "rows=all" not in more_html or "theme=" in more_html:
        problems.append("View All did not render as a theme-free link")
    fragments = tuple(FragmentView(name, label, template) for name, label, template in SEASON_PANES)
    for theme in ERA_THEMES:
        board = present("standings", _FIXTURES["standings"], theme, caption="Fixture standings")
        frame = _frame(
            theme=theme,
            title="Fixture season",
            nav="seasons",
            pager="Season",
            fragments=fragments,
            active=fragments[0],
            slots={
                "lead": "fragments/season_lead.html",
                "aside": "fragments/season_aside.html",
            },
            path="/seasons/2025",
            year=2025,
            week_nav=(1, 16),
        )
        html = env.get_template(f"shells/{theme}.html").render(  # type: ignore[attr-defined]
            frame=frame,
            year=2025,
            current=_FIXTURE_CURRENT,
            board=board,
        )
        if "/static/hub.css" in html or "/static/hub.js" in html:
            problems.append(f"{theme} shell render pulled a modern asset")
        fragment = _between(html, "<!--a2-fragment-->", "<!--/a2-fragment-->")
        direct = env.get_template("fragments/board.html").render(board=board)  # type: ignore[attr-defined]
        if fragment is None:
            problems.append(f"{theme} shell render lost the fragment markers")
        elif fragment != direct:
            problems.append(f"{theme} shell fragment bytes diverged from the fragment template")
        elif "theme=" in fragment or "1600.50" not in fragment:
            problems.append(f"{theme} fragment region failed the echo check")
        for slot_name in REQUIRED_SLOTS:
            slot_html = _between(html, f"<!--a2-slot:{slot_name}-->", f"<!--/a2-slot:{slot_name}-->")
            if slot_html is None:
                problems.append(f"{theme} shell dropped the {slot_name} slot")
            elif "theme=" in slot_html:
                problems.append(f"{theme} {slot_name} slot carries a theme token")
        for name, _, _ in SEASON_PANES:
            if f"pane={name}" not in html:
                problems.append(f"{theme} shell missing pane link {name}")
        for label in THEME_LABELS.values():
            if label not in html:
                problems.append(f"{theme} switcher missing {label}")
        if f"week/1?theme={theme}" not in html or f"week/16?theme={theme}" not in html:
            problems.append(f"{theme} week numerals are not themed links")
        if theme == "era90":
            match = re.search(
                r'class="numeral-row"><span class="numeral-label">Season</span>(.*?)</p>',
                html,
            )
            numbers = re.findall(r">(\d+)</a>", match.group(1)) if match else []
            if numbers != [str(index) for index in range(1, 8)]:
                problems.append(f"era90 pane numerals were {numbers}")
            for label in ERA90_DEAD_LABELS:
                if f'<p class="dead-label">{label}</p>' not in html:
                    problems.append(f"era90 missing text-only label {label}")
            if html.count('class="link-box"') != 1:
                problems.append("era90 render did not keep a single link box")
        else:
            if "dead-label" in html:
                problems.append("era2010 render included the era90 link farm")
            cursor = 0
            for _, label, _ in SEASON_PANES:
                at = html.find(f">{label}</a>", cursor)
                if at < 0:
                    problems.append(f"era2010 tabs missing {label}")
                    break
                cursor = at + 1
    return problems


def install(templates: Jinja2Templates) -> None:
    """Bind the environment and refuse to serve when the contract fails."""
    global _templates
    _templates = templates
    problems = collect_contract_problems(templates)
    if problems:
        _templates = None
        raise ThemeContractError(problems)


# --- C1a era90 portal and season family (#100). Append-only. ---
# Content templates live in hub/templates/era90/ and are mounted by the
# era90 shell. The shell stays the one layout table the boot gate checks.
# Interior season pages keep the A2 left rail. The portal home replaces
# that rail with the Eagle task order.

ERA90_FAMILY: dict[str, str] = {
    "week.html": "era90/week.html",
    "gamecenter.html": "era90/gamecenter.html",
    "moves.html": "era90/moves.html",
    "draft.html": "era90/draft.html",
    "marks.html": "era90/marks.html",
    "desk.html": "era90/desk.html",
    "scoring.html": "era90/scoring.html",
    "records/index.html": "era90/records.html",
}

_MOVE_LABELS = {"trade": "trade", "waiver": "waiver", "free_agent": "free agent"}


def _era90_standings_board(
    rows: Sequence[Mapping[str, object]],
    theme: str,
    caption: str,
) -> dict[str, object]:
    high = _max_number(row.get("points_for") for row in rows)
    body: list[dict[str, object]] = []
    for row in rows:
        wins = int(row.get("wins") or 0)
        losses = int(row.get("losses") or 0)
        ties = int(row.get("ties") or 0)
        marks: dict[str, str] = {}
        if row.get("champion"):
            marks["manager"] = "is-leader"
        elif int(row.get("rank") or 0) == 1:
            marks["manager"] = "is-active-leader"
        if _same(row.get("points_for"), high):
            marks["points_for"] = "is-record"
        body.append(
            {
                "rank": row.get("rank"),
                "manager": row.get("display_name") or "",
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "points_for": row.get("points_for"),
                "points_against": row.get("points_against"),
                "win_pct": row.get("win_pct"),
                "record": f"{wins}-{losses}-{ties}",
                "_href": {"manager": _path("/members", row.get("manager_id"))},
                "_mark": marks,
            }
        )
    return present("standings", body, theme, caption=caption)


def _era90_standings_boards(
    rows: Sequence[Mapping[str, object]],
    theme: str,
    caption: str,
) -> list[dict[str, object]]:
    """One shared standings grid, or one per division when the rows carry one.

    This warehouse has no division column, so the home and the week page
    render a single table. A future ``division`` value splits the same
    projection without a second fragment.
    """
    grouped: dict[str, list[Mapping[str, object]]] = {}
    order: list[str] = []
    for row in rows:
        key = str(row.get("division") or "")
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(row)
    boards: list[dict[str, object]] = []
    for key in order:
        label = key if key and len(order) > 1 else caption
        boards.append(_era90_standings_board(grouped[key], theme, label))
    return boards


def _portal_rail(seasons: Sequence[Mapping[str, object]], year: int | None) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if year is not None:
        items.append({"href": f"/seasons/{year}", "label": f"{year} season"})
    past = [row for row in seasons if year is None or int(row["year"]) != int(year)]
    if past:
        items.append({"href": "", "label": "Past seasons"})
        for row in past:
            season_year = int(row["year"])
            items.append({"href": f"/seasons/{season_year}", "label": str(season_year)})
    items.append({"href": "/records", "label": "Record book"})
    items.append({"href": "/players", "label": "Top 10"})
    if year is not None:
        items.append({"href": f"/seasons/{year}/scoring", "label": "Rules and scoring"})
    items.append({"href": "/records/awards", "label": "Champions"})
    return items


def _era_year(context: Mapping[str, object]) -> int | None:
    current = context.get("current")
    if isinstance(current, Mapping) and current.get("year") is not None:
        return int(current["year"])
    return None


def _era_weeks(context: Mapping[str, object], year: int | None) -> list[int]:
    gc = context.get("gc")
    if isinstance(gc, Mapping) and gc.get("weeks"):
        return [int(week) for week in gc["weeks"]]  # type: ignore[union-attr]
    if year is None:
        return []
    return queries.scored_weeks(year)


def _era90_frame(
    request: Request,
    *,
    title: str,
    nav: str,
    template: str,
    year: int | None,
    weeks: Sequence[int],
) -> Frame:
    active = FragmentView("page", title, template)
    week_nav = ()
    if year is not None:
        week_nav = tuple(
            WeekLink(int(week), f"/seasons/{int(year)}/week/{int(week)}?theme=era90")
            for week in weeks
        )
    return Frame(
        theme="era90",
        title=title,
        nav=nav,
        pager="",
        fragments=(active,),
        active=active,
        slots=(),
        path=request.url.path,
        nav_links=_nav_links("era90", year),
        theme_choices=tuple(ThemeChoice(theme_id, THEME_LABELS[theme_id]) for theme_id in THEMES),
        week_nav=week_nav,
        dead_labels=ERA90_DEAD_LABELS,
    )


def _era90_response(
    request: Request,
    *,
    title: str,
    nav: str,
    template: str,
    context: Mapping[str, object],
    year: int | None,
    weeks: Sequence[int],
) -> HTMLResponse:
    if _templates is None:
        raise RuntimeError("themes.install() was not called")
    frame = _era90_frame(request, title=title, nav=nav, template=template, year=year, weeks=weeks)
    payload: dict[str, object] = {**context, "frame": frame, "title": title, "nav": nav}
    return _templates.TemplateResponse(request, "shells/era90.html", payload)


def era90_home(request: Request) -> HTMLResponse:
    """Portal home. Skips the modern desk so the era page stays the small grid."""
    seasons = queries.list_seasons()
    year = queries.latest_scored_year()
    rows = queries.standings(year) if year is not None else []
    boards = _era90_standings_boards(rows, "era90", f"{year} standings") if rows else []
    weeks = queries.scored_weeks(year) if year is not None else []
    current = next(
        (row for row in seasons if year is not None and int(row["year"]) == int(year)),
        None,
    )
    cheer = None
    if current and current.get("champion") and current.get("champion_id"):
        cheer = {
            "lead": "Congratulations",
            "name": current["champion"],
            "href": f"/members/{current['champion_id']}",
        }
    elif rows:
        top = rows[0]
        cheer = {
            "lead": "Leader",
            "name": top.get("display_name") or "",
            "href": _path("/members", top.get("manager_id")),
        }
    context: dict[str, object] = {
        "year": year,
        "boards": boards,
        "ticker": queries.era90_ticker(year),
        "cheer": cheer,
        "portal_rail": _portal_rail(seasons, year),
        "last_updated": queries.era90_last_updated(),
    }
    return _era90_response(
        request,
        title="Nu Choate League",
        nav="home",
        template="era90/home.html",
        context=context,
        year=year,
        weeks=weeks,
    )


def _era90_week_view(gc: Mapping[str, object], year: int) -> dict[str, object]:
    week = int(gc["week"])  # type: ignore[arg-type]
    groups: list[dict[str, object]] = []
    boxes: list[dict[str, str]] = []
    for group in gc.get("groups") or []:  # type: ignore[union-attr]
        games: list[dict[str, object]] = []
        kind = group.get("kind")
        label = "" if kind == "regular" else str(group.get("label") or "")
        for game in group.get("games") or []:
            home = game.get("home") or {}
            away = game.get("away") or {}
            winner = game.get("winner_id")
            games.append(
                {
                    "home": home.get("name") or "—",
                    "home_href": _path("/members", home.get("id")),
                    "home_pts": _points(home.get("points")),
                    "home_mark": "is-leader" if winner and winner == home.get("id") else "",
                    "away": away.get("name") or "—",
                    "away_href": _path("/members", away.get("id")),
                    "away_pts": _points(away.get("points")),
                    "away_mark": "is-leader" if winner and winner == away.get("id") else "",
                    "kind_label": label,
                }
            )
            if game.get("id"):
                boxes.append(
                    {
                        "href": f"/seasons/{year}/week/{week}/{game['id']}",
                        "label": f"{home.get('name') or '—'} vs {away.get('name') or '—'}",
                    }
                )
        groups.append({"week": week, "label": label, "games": games})
    standings = gc.get("standings") or {}
    rows = standings.get("rows") or [] if isinstance(standings, Mapping) else []
    boards = _era90_standings_boards(rows, "era90", f"{year} week {week}") if rows else []
    cheer = None
    if rows:
        top = rows[0]
        cheer = {
            "lead": "Leader",
            "name": top.get("display_name") or "",
            "href": _path("/members", top.get("manager_id")),
        }
    median = standings.get("week_median") if isinstance(standings, Mapping) else None
    median_line = f"Scoring median {float(median):.1f}." if median is not None else None
    return {
        "year": year,
        "boards": boards,
        "week_groups": groups,
        "boxes": boxes,
        "cheer": cheer,
        "median_line": median_line,
    }


def _era90_side(side: Mapping[str, object]) -> dict[str, object]:
    players: list[dict[str, str]] = []
    for row in side.get("starters") or []:  # type: ignore[union-attr]
        players.append(
            {
                "slot": str(row.get("slot") or ""),
                "name": str(row.get("player_name") or ""),
                "href": _path("/players", row.get("player_id")),
                "points": _points(row.get("points")),
            }
        )
    return {
        "name": side.get("name") or "",
        "href": _path("/members", side.get("id")),
        "points": _points(side.get("points")),
        "players": players,
    }


def _era90_sibling(game: Mapping[str, object] | None, year: int, week: int) -> dict[str, str] | None:
    if not game or not game.get("id"):
        return None
    home = game.get("home") or {}
    away = game.get("away") or {}
    return {
        "href": f"/seasons/{year}/week/{week}/{game['id']}",
        "label": f"{home.get('name') or '—'} vs {away.get('name') or '—'}",
    }


def _era90_gamecenter(gc: Mapping[str, object], year: int) -> dict[str, object]:
    game = gc["game"]
    assert isinstance(game, Mapping)
    week = int(gc["week"])  # type: ignore[arg-type]
    home = game["home"]
    away = game["away"]
    assert isinstance(home, Mapping) and isinstance(away, Mapping)
    winner = game.get("winner_id")
    cheer = None
    if winner and winner == home.get("id"):
        cheer = {"lead": "Winner", "name": home.get("name") or "", "href": _path("/members", home.get("id"))}
    elif winner and winner == away.get("id"):
        cheer = {"lead": "Winner", "name": away.get("name") or "", "href": _path("/members", away.get("id"))}
    return {
        "kind_label": gc.get("kind_label") or "",
        "sides": [_era90_side(home), _era90_side(away)],
        "cheer": cheer,
        "prev": _era90_sibling(gc.get("prev_match") if isinstance(gc.get("prev_match"), Mapping) else None, year, week),
        "next": _era90_sibling(gc.get("next_match") if isinstance(gc.get("next_match"), Mapping) else None, year, week),
    }


def _era90_moves(moves: Sequence[Mapping[str, object]]) -> dict[str, object]:
    lines: list[dict[str, str]] = []
    for move in moves:
        names: list[str] = []
        adds = move.get("adds") or []
        drops = move.get("drops") or []
        for row in list(adds) + list(drops):  # type: ignore[operator]
            name = row.get("player_name")
            if name:
                names.append(str(name))
        kind = _MOVE_LABELS.get(str(move.get("type") or ""), str(move.get("type") or "move"))
        text = f"Week {move.get('week')} {kind}"
        if names:
            text += " " + ", ".join(names)
        lines.append({"href": str(move.get("href") or ""), "text": text})
    return {"lines": lines}


def _era90_draft_board(picks: Sequence[Mapping[str, object]], year: int) -> dict[str, object]:
    high = _max_number(row.get("ros_vorp") for row in picks)
    body: list[dict[str, object]] = []
    for row in picks:
        overall = int(row.get("overall") or 0)
        mark = ""
        if overall == 1:
            mark = "is-leader"
        elif _same(row.get("ros_vorp"), high):
            mark = "is-record"
        body.append(
            {
                "overall": overall,
                "round": row.get("round"),
                "manager": row.get("manager_name") or "",
                "player": row.get("player_name") or "",
                "position": row.get("position") or "",
                "_href": {
                    "manager": _path("/members", row.get("manager_id")),
                    "player": _path("/players", row.get("player_id")),
                },
                "_mark": {"player": mark} if mark else {},
            }
        )
    return present("draft", body, "era90", caption=f"{year} draft")


def _era90_marks(context: Mapping[str, object]) -> dict[str, object]:
    chapters: list[dict[str, object]] = []
    for chapter in context.get("by_kind") or []:  # type: ignore[union-attr]
        rows: list[dict[str, str]] = []
        for week in chapter.get("weeks") or []:
            who = week.get("display_name") or week.get("manager_name") or ""
            text = f"W{week.get('week')} {who}".strip()
            if week.get("points") is not None:
                text += f" {_points(week.get('points'))}"
            rows.append({"href": str(week.get("href") or ""), "text": text})
        chapters.append({"label": chapter.get("label") or "", "rows": rows})
    return {"chapters": chapters}


def _era90_desk(desk: Mapping[str, object] | None) -> dict[str, object]:
    if not desk:
        return {"managers": []}
    order = list(desk.get("managers") or [])
    managers: list[dict[str, object]] = []
    for manager in order:
        rows: list[dict[str, str]] = []
        cells = manager.get("cells") or []
        for index, cell in enumerate(cells):
            if not cell or cell.get("self"):
                continue
            other = order[index]
            record = cell.get("record") or ""
            rows.append(
                {
                    "href": f"/versus/{manager['manager_id']}/{other['manager_id']}",
                    "text": f"vs {other['display_name']} {record}".strip(),
                }
            )
        managers.append(
            {
                "name": manager.get("display_name") or "",
                "href": f"/members/{manager['manager_id']}",
                "rows": rows,
            }
        )
    return {"managers": managers}


def _era90_scoring(context: Mapping[str, object]) -> dict[str, object]:
    groups: list[dict[str, object]] = []
    current_label = None
    bucket: dict[str, object] | None = None
    for row in context.get("rows") or []:  # type: ignore[union-attr]
        label = str(row.get("group") or "Scoring")
        if label != current_label:
            bucket = {"label": label, "rows": []}
            groups.append(bucket)
            current_label = label
        value = row.get("value")
        if value is None:
            value = row.get("points") or ""
        assert bucket is not None
        rows = bucket["rows"]
        assert isinstance(rows, list)
        rows.append({"label": str(row.get("label") or ""), "value": str(value)})
    years: list[dict[str, str]] = []
    for row in context.get("seasons") or []:  # type: ignore[union-attr]
        season_year = int(row["year"])
        years.append({"href": f"/seasons/{season_year}/scoring", "label": str(season_year)})
    return {"groups": groups, "years": years}


def _era90_records(context: Mapping[str, object]) -> dict[str, object]:
    chapters: list[dict[str, object]] = []
    for chapter in context.get("chapters") or []:  # type: ignore[union-attr]
        chapters.append(
            {
                "href": f"/records/{chapter['slug']}",
                "title": chapter.get("title") or "",
                "taste": chapter.get("taste") or "",
                "anchors": chapter.get("anchors") or [],
            }
        )
    holders: list[dict[str, str]] = []
    for row in context.get("holders") or []:  # type: ignore[union-attr]
        text = str(row.get("display_name") or "")
        if row.get("total") is not None:
            text = f"{text} {int(row['total'])}"
        holders.append({"href": f"/members/{row['manager_id']}", "text": text})
    return {"chapters": chapters, "holders": holders}


def _era90_prepare(name: str, context: Mapping[str, object], year: int | None) -> dict[str, object]:
    if name == "week.html" and isinstance(context.get("gc"), Mapping) and year is not None:
        return _era90_week_view(context["gc"], year)  # type: ignore[arg-type]
    if name == "gamecenter.html" and isinstance(context.get("gc"), Mapping) and year is not None:
        return _era90_gamecenter(context["gc"], year)  # type: ignore[arg-type]
    if name == "moves.html":
        return _era90_moves(context.get("moves") or [])  # type: ignore[arg-type]
    if name == "draft.html" and year is not None:
        draft = context.get("draft") or {}
        picks = draft.get("picks") or [] if isinstance(draft, Mapping) else []
        years = []
        if isinstance(draft, Mapping):
            for season_year in draft.get("years") or []:
                years.append({"href": f"/seasons/{int(season_year)}/draft", "label": str(int(season_year))})
        board = _era90_draft_board(picks, year) if picks else None
        return {"board": board, "years": years}
    if name == "marks.html":
        return _era90_marks(context)
    if name == "desk.html":
        desk = context.get("desk")
        return _era90_desk(desk if isinstance(desk, Mapping) else None)
    if name == "scoring.html":
        return _era90_scoring(context)
    if name == "records/index.html":
        return _era90_records(context)
    return {}


def era90_family_document(
    request: Request,
    name: str,
    *,
    nav: str,
    title: str,
    context: Mapping[str, object],
) -> HTMLResponse:
    """Render one legacy season-family route inside the era90 shell."""
    year = _era_year(context)
    weeks = _era_weeks(context, year)
    prepared = dict(context)
    prepared.update(_era90_prepare(name, context, year))
    prepared["last_updated"] = queries.era90_last_updated()
    return _era90_response(
        request,
        title=title,
        nav=nav,
        template=ERA90_FAMILY[name],
        context=prepared,
        year=year,
        weeks=weeks,
    )
