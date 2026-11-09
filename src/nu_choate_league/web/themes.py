"""Per-theme template sets.

Loader order for the active theme is ``themes/<theme>/``, then ``themes/_shared/``,
then the legacy flat templates (modern, byte-near). Theme is request-scoped: a
contextvar set for the duration of ``render_page``. Nothing here queries the database.

Invariants:
- A board's digits, links, column keys, and leader mark come from ``present``.
  Templates walk those cells. They do not read query fields.
- Non-modern theme directories carry the same relative paths. A file added to
  one era fails startup until the other era has it too.
- The season tab list is parsed from the modern ``season.html`` tab row.
  Era shells do not keep a second copy of that list.
- Rendering a themed board must echo ``present`` (``data-cell``, ``data-raw``,
  and the visible text). Startup refuses to boot when a copy drifts.
"""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from contextvars import ContextVar, Token
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import jinja2
from markupsafe import Markup
from starlette.requests import Request
from starlette.templating import Jinja2Templates

from ..paths import project_root

THEMES: tuple[str, ...] = ("modern", "era90", "era2010")
THEME_LABELS: dict[str, str] = {
    "modern": "Modern",
    "era90": "1998",
    "era2010": "2010",
}
# One list. Era90's left rail and era2010's sport bar both read it.
LEAGUE_TASKS: tuple[tuple[str, str], ...] = (
    ("Home", "/"),
    ("Seasons", "/seasons"),
    ("Members", "/members"),
    ("Versus", "/versus"),
    ("Records", "/records"),
    ("Players", "/players"),
)
# Eagle's right-rail labels (REACHED). Only ESPN's host was in the digest.
FANTASY_LINKS: tuple[tuple[str, str | None], ...] = (
    ("NANDO", None),
    ("ESPN", "http://espnet.sportszone.com/"),
    ("USA TODAY", None),
    ("CBS SPORTSLINE", None),
    ("CNN/SI", None),
    ("INJURY REPORT", None),
)
# Spike surfaces. A non-modern theme is not shippable while any of these are absent.
# Coverage parity (below) catches a file that exists in only one era.
REQUIRED_THEME_FILES: tuple[str, ...] = (
    "base.html",
    "players.html",
    "season.html",
    "scoring.html",
    "boards/scoring_distribution.html",
    "boards/career_rankings.html",
    "boards/standings.html",
    "boards/matchups.html",
    "panes/standings.html",
    "panes/weeks.html",
)
THEMED_MACROS: frozenset[str] = frozenset({"distribution", "environment_block"})
FORBIDDEN_TEMPLATE_TOKENS: tuple[str, ...] = (
    "starter_points",
    "started_vorp",
    "points_for",
    "points_against",
    "home_points",
    "away_points",
)
MISSING = "\u2014"
CAREER_MODULE = 10
CAREER_ALL = 50

HUB_DIR = project_root() / "hub"
LEGACY_DIR = HUB_DIR / "templates"
THEME_ROOT = LEGACY_DIR / "themes"
SHARED_DIR = THEME_ROOT / "_shared"

current_theme: ContextVar[str] = ContextVar("theme", default="modern")
current_request: ContextVar[Request | None] = ContextVar("theme_request", default=None)
_ENVS: dict[str, jinja2.Environment] = {}

_PANE_NAV = re.compile(r'data-tab="([a-z]+)">([^<]+)</a>')
_MACRO_NAME = re.compile(r"\{%-?\s*macro\s+([A-Za-z_][A-Za-z0-9_]*)")
_MACRO_IMPORT = re.compile(
    r"\{%-?\s*from\s+['\"]scoring_macros.html['\"]\s+import\s+([^%]+?)\s*-?%\}",
    re.DOTALL,
)
_CELL = re.compile(
    r'data-cell="([^"]+)"([^>]*)data-raw="([^"]*)"([^>]*)>(.*?)</(?:td|div)>',
    re.DOTALL,
)


class ThemeContractError(RuntimeError):
    """A theme copy drifted from the board contract or the coverage gate."""


@dataclass(frozen=True)
class Cell:
    key: str
    text: str
    raw: str
    href: str | None = None
    emphasis: str = ""


@dataclass(frozen=True)
class Column:
    key: str
    header: str


class Row(tuple[Cell, ...]):
    """Cells in projection order, also addressable by column key."""

    def __new__(cls, cells: tuple[Cell, ...]) -> Row:
        row = super().__new__(cls, cells)
        row._by_key = {cell.key: cell for cell in cells}  # type: ignore[attr-defined]
        return row

    def __getitem__(self, key: int | str) -> Cell:  # type: ignore[override]
        if isinstance(key, str):
            return self._by_key[key]  # type: ignore[attr-defined]
        return tuple.__getitem__(self, key)


@dataclass(frozen=True)
class Board:
    id: str
    columns: tuple[Column, ...]
    rows: tuple[Row, ...]
    glossary: str = ""
    more_href: str | None = None
    shown: int = 0
    total: int = 0


@dataclass(frozen=True)
class Pane:
    id: str
    label: str
    href: str


def resolve_theme(raw: str | None) -> str:
    if raw in THEMES:
        return raw
    return "modern"


def theme_name() -> str:
    return current_theme.get()


def theme_href(theme: str) -> str:
    """Same path and query, with ``theme`` replaced. Always a plain link."""
    chosen = theme if theme in THEMES else "modern"
    request = current_request.get()
    if request is None:
        return f"/?theme={chosen}"
    pairs = [(key, value) for key, value in request.query_params.multi_items() if key != "theme"]
    pairs.append(("theme", chosen))
    return f"{request.url.path}?{urlencode(pairs)}"


def theme_choices() -> list[dict[str, str]]:
    return [
        {"id": theme, "label": THEME_LABELS[theme], "href": theme_href(theme)}
        for theme in THEMES
    ]


def qhref(path: str, **extra: object) -> str:
    """Internal link that keeps the active theme. Modern omits the query."""
    query: list[tuple[str, str]] = []
    theme = current_theme.get()
    if theme != "modern":
        query.append(("theme", theme))
    for key, value in extra.items():
        if value is None:
            continue
        query.append((key, str(value)))
    if not query:
        return path
    return f"{path}?{urlencode(query)}"


def league_tasks() -> list[dict[str, str]]:
    return [{"label": label, "href": qhref(path)} for label, path in LEAGUE_TASKS]


def fantasy_links() -> list[dict[str, str | None]]:
    return [{"label": label, "href": href} for label, href in FANTASY_LINKS]


def modern_pane_names() -> tuple[tuple[str, str], ...]:
    """Pane ids and labels, in the modern season tab-row order.

    The modern template is the list. Era shells call ``season_panes`` and do
    not restate it. All-pro and all-bench are in-page anchors, not panes: they
    have no ``data-tab``.
    """
    text = (LEGACY_DIR / "season.html").read_text(encoding="utf-8")
    marker = 'class="jump js-season-tabs"'
    if marker not in text:
        raise ThemeContractError("season.html is missing the js-season-tabs row")
    nav = text.split(marker, 1)[1].split("</p>", 1)[0]
    found = tuple((pane_id, label.strip()) for pane_id, label in _PANE_NAV.findall(nav))
    if not found:
        raise ThemeContractError("season.html tab row has no data-tab panes")
    return found


def season_panes(year: int) -> list[Pane]:
    year_number = int(year)
    return [
        Pane(pane_id, label, qhref(f"/seasons/{year_number}", pane=pane_id))
        for pane_id, label in modern_pane_names()
    ]


def active_pane(panes: Sequence[Pane]) -> str:
    ids = [pane.id for pane in panes]
    request = current_request.get()
    raw = request.query_params.get("pane") if request is not None else None
    if raw in ids:
        return str(raw)
    return ids[0]


def theme_include(name: str, **extra: Any) -> Markup:
    """Render a theme template from a shared macro.

    Jinja includes inside a macro do not see the macro's arguments, so the
    shared ``distribution`` macro calls this instead of pasting era markup.
    The active theme's ``boards/`` file wins; ``_shared`` is the fallback.
    """
    template = _ENVS[current_theme.get()].get_template(name)
    return Markup(template.render(**extra))


def week_slice(
    schedule: Mapping[str, Any] | None,
    now_week: int | None,
    year: int,
) -> dict[str, Any]:
    """Regular-season weeks and the games for the requested week.

    Numeral links are ``?pane=weeks&week=N``. The default week is the season's
    current week, else the last scored regular week.
    """
    schedule = schedule or {}
    regular = list(schedule.get("regular") or [])
    weeks = [int(week) for week, _games in regular]
    if not weeks:
        weeks = [int(week) for week in (schedule.get("weeks") or [])]
    selected: int | None = None
    request = current_request.get()
    if request is not None and request.query_params.get("week"):
        try:
            selected = int(request.query_params.get("week") or "")
        except (TypeError, ValueError):
            selected = None
    if selected not in weeks:
        if now_week is not None and int(now_week) in weeks:
            selected = int(now_week)
        elif weeks:
            selected = weeks[-1]
        else:
            selected = None
    games: list[dict[str, Any]] = []
    for week, rows in regular:
        if int(week) != selected:
            continue
        for row in rows:
            item = dict(row)
            item.setdefault("year", int(year))
            games.append(item)
        break
    return {"weeks": weeks, "selected": selected, "games": games}


def render_page(
    templates: Jinja2Templates,
    request: Request,
    name: str,
    context: dict[str, Any],
    status_code: int = 200,
):
    """Bind the request theme, then render. The var lives only for this call.

    Set here, not in HTTP middleware: Starlette renders the template inside the
    route task, and ``TemplateResponse`` renders before it returns.
    """
    theme_token = current_theme.set(resolve_theme(request.query_params.get("theme")))
    request_token = current_request.set(request)
    try:
        return templates.TemplateResponse(request, name, context, status_code=status_code)
    finally:
        current_theme.reset(theme_token)
        current_request.reset(request_token)


def install(templates: Jinja2Templates) -> None:
    """One environment per theme. ``templates.get_template`` dispatches on the contextvar."""
    for theme in THEMES:
        _ENVS[theme] = _environment(templates, theme)

    def get_template(name: str) -> jinja2.Template:
        theme = current_theme.get()
        if theme not in _ENVS:
            theme = "modern"
        return _ENVS[theme].get_template(name)

    templates.get_template = get_template  # type: ignore[method-assign]
    problems = collect_contract_problems()
    if problems:
        joined = "\n".join(f"- {problem}" for problem in problems)
        raise ThemeContractError(f"theme contract failed:\n{joined}")


def present(board_id: str, rows: Sequence[Mapping[str, Any]] | None) -> Board:
    """Project ``rows`` for the active theme.

    Does not sort and does not query. Callers pass rows in the order the
    query already chose. The first career row is the points leader because
    ``players_index`` orders by starter points descending.
    """
    source = list(rows or [])
    theme = current_theme.get()
    projection = PROJECTIONS[board_id][theme]
    more_href: str | None = None
    total = len(source)
    if board_id == "career_rankings":
        source, more_href = _limit_career(source, theme)
    built: list[Row] = []
    for index, row in enumerate(source):
        cell_map = _CELL_MAPS[board_id](row, index)
        built.append(Row(tuple(cell_map[key] for key in projection)))
    columns = tuple(Column(key, _header(key, theme)) for key in projection)
    glossary = GLOSSARIES[board_id].get(theme, GLOSSARIES[board_id]["*"])
    return Board(
        id=board_id,
        columns=columns,
        rows=tuple(built),
        glossary=glossary,
        more_href=more_href,
        shown=len(built),
        total=total,
    )


# --- catalog -----------------------------------------------------------------

PROJECTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "career_rankings": {
        "modern": ("player", "pos", "yrs", "starts", "pf", "avg", "vorp"),
        "era90": ("player", "pos", "pf", "avg", "starts"),
        "era2010": ("player", "pos", "pf", "avg"),
    },
    "standings": {
        "modern": ("team", "record", "pf", "pa"),
        "era90": ("team", "w", "l", "t", "pf", "pa"),
        "era2010": ("team", "record", "pct", "pf", "pa"),
    },
    "scoring_distribution": {
        "modern": (
            "manager_weeks",
            "teams",
            "avg",
            "median",
            "stddev",
            "min",
            "max",
            "league_pf",
        ),
        "era90": (
            "manager_weeks",
            "teams",
            "avg",
            "median",
            "stddev",
            "min",
            "max",
            "league_pf",
        ),
        "era2010": (
            "manager_weeks",
            "teams",
            "avg",
            "median",
            "stddev",
            "min",
            "max",
            "league_pf",
        ),
    },
    "matchups": {
        theme: ("home", "home_pts", "away", "away_pts", "lineups") for theme in THEMES
    },
    "playoff_path": {theme: ("rank", "manager", "pf") for theme in THEMES},
}

_HEADERS: dict[str, dict[str, str]] = {
    "player": {"*": "Player"},
    "pos": {"*": "Pos"},
    "yrs": {"*": "Yrs"},
    "starts": {"*": "Starts"},
    "pf": {"*": "PF"},
    "avg": {"*": "Avg"},
    "vorp": {"*": "VORP"},
    "team": {"era90": "", "era2010": "Franchise", "*": "Manager"},
    "w": {"*": "W"},
    "l": {"*": "L"},
    "t": {"*": "T"},
    "record": {"era2010": "W-L-T", "*": "Record"},
    "pct": {"*": "Pct"},
    "pa": {"*": "PA"},
    "manager_weeks": {"*": "Mgr-weeks"},
    "teams": {"*": "Teams"},
    "median": {"*": "Median"},
    "stddev": {"*": "Std dev"},
    "min": {"*": "Min"},
    "max": {"*": "Max"},
    "league_pf": {"*": "League PF"},
    "home": {"*": "Home"},
    "home_pts": {"*": "Pts"},
    "away": {"*": "Away"},
    "away_pts": {"*": "Pts"},
    "lineups": {"*": ""},
    "rank": {"*": "#"},
    "manager": {"*": "Manager"},
}

GLOSSARIES: dict[str, dict[str, str]] = {
    "career_rankings": {
        "*": "PF is starter points. Avg is points per start. Bold marks the career points leader.",
    },
    "standings": {
        "era90": (
            "W, L, and T are the official record. A zero in the tie column is -. "
            "PF is points for. PA is points against. Bold marks first place."
        ),
        "*": (
            "W-L-T is the official record. Pct counts a tie as half a win. "
            "PF is points for. PA is points against. Bold marks first place."
        ),
    },
    "scoring_distribution": {
        "*": (
            "Mgr-weeks, average, median, min, and max are posted regular-season "
            "manager totals. League PF is their sum."
        ),
    },
    "matchups": {"*": "Bold marks the higher score."},
    "playoff_path": {"*": "Playoff path in official rank order. PF is season points for."},
}


def _header(key: str, theme: str) -> str:
    headers = _HEADERS[key]
    return headers.get(theme, headers["*"])


def _get(row: Mapping[str, Any], key: str) -> Any:
    try:
        return row[key]
    except (KeyError, TypeError):
        return None


def _raw(value: Any) -> str:
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


def _fixed(value: Any, digits: int) -> str:
    if value is None or value == "":
        return MISSING
    return f"{float(value):.{digits}f}"


def _int_text(value: Any) -> str:
    if value is None or value == "":
        return ""
    return str(int(value))


def _short_name(name: str) -> str:
    """CBS 17 Sep 2009 projection grammar: ``A. Rodgers``.

    A particle stays with the last name (``Amon-Ra St. Brown`` → ``A. St. Brown``).
    Jr/III is dropped. The full name remains the cell's raw value.
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


def _limit_career(
    rows: list[Mapping[str, Any]],
    theme: str,
) -> tuple[list[Mapping[str, Any]], str | None]:
    if theme == "era2010":
        request = current_request.get()
        show_all = bool(request and request.query_params.get("rows") == "all")
        cap = CAREER_ALL if show_all else CAREER_MODULE
        if not show_all and len(rows) > cap:
            return rows[:cap], qhref("/players", rows="all")
        return rows[:cap], None
    return rows[:CAREER_ALL], None


def _career_map(row: Mapping[str, Any], index: int) -> dict[str, Cell]:
    theme = current_theme.get()
    name = str(_get(row, "player_name") or "")
    label = _short_name(name) if theme == "era2010" else name
    points = _get(row, "starter_points")
    position = _get(row, "position")
    return {
        "player": Cell("player", label or MISSING, name, _player_href(row)),
        "pos": Cell("pos", str(position) if position else MISSING, str(position or "")),
        "yrs": Cell("yrs", _int_text(_get(row, "seasons")), _raw(_get(row, "seasons"))),
        "starts": Cell("starts", _int_text(_get(row, "starts")), _raw(_get(row, "starts"))),
        "pf": Cell(
            "pf",
            _fixed(points, 1),
            _raw(points),
            emphasis="leader" if index == 0 and points is not None else "",
        ),
        "avg": Cell("avg", _fixed(_get(row, "avg"), 1), _raw(_get(row, "avg"))),
        "vorp": Cell("vorp", _fixed(_get(row, "started_vorp"), 1), _raw(_get(row, "started_vorp"))),
    }


def _standings_map(row: Mapping[str, Any], index: int) -> dict[str, Cell]:
    wins = int(_get(row, "wins") or 0)
    losses = int(_get(row, "losses") or 0)
    ties = int(_get(row, "ties") or 0)
    rank = _get(row, "rank")
    leader = (int(rank) == 1) if rank is not None else index == 0
    played = wins + losses + ties
    pct = _get(row, "win_pct")
    if pct is None and played:
        pct = (wins + 0.5 * ties) / played
    theme = current_theme.get()
    tie_text = "-" if theme == "era90" and ties == 0 else str(ties)
    record_text = f"{wins}-{losses}-{ties}" if theme == "era2010" else _modern_record(row, wins, losses, ties)
    name = str(_get(row, "display_name") or "")
    return {
        "team": Cell("team", name or MISSING, name, _member_href(row, "manager_id"), "leader" if leader else ""),
        "w": Cell("w", str(wins), str(wins)),
        "l": Cell("l", str(losses), str(losses)),
        "t": Cell("t", tie_text, str(ties)),
        "record": Cell("record", record_text, f"{wins}-{losses}-{ties}"),
        "pct": Cell("pct", _fixed(pct, 3), _raw(pct)),
        "pf": Cell("pf", _fixed(_get(row, "points_for"), 2), _raw(_get(row, "points_for"))),
        "pa": Cell("pa", _fixed(_get(row, "points_against"), 2), _raw(_get(row, "points_against"))),
    }


def _distribution_map(row: Mapping[str, Any], index: int) -> dict[str, Cell]:
    del index
    pairs = (
        ("manager_weeks", "manager_weeks", 0),
        ("teams", "managers", 0),
        ("avg", "avg", 2),
        ("median", "median", 2),
        ("stddev", "stddev", 2),
        ("min", "min", 2),
        ("max", "max", 2),
        ("league_pf", "total_pf", 2),
    )
    cells: dict[str, Cell] = {}
    for key, source, digits in pairs:
        value = _get(row, source)
        text = _int_text(value) if digits == 0 and value is not None else _fixed(value, digits)
        if digits == 0 and value is None:
            text = MISSING
        cells[key] = Cell(key, text, _raw(value))
    return cells


def _matchup_map(row: Mapping[str, Any], index: int) -> dict[str, Cell]:
    del index
    home_pts = _get(row, "home_points")
    away_pts = _get(row, "away_points")
    home_lead = ""
    away_lead = ""
    if home_pts is not None and away_pts is not None:
        if float(home_pts) > float(away_pts):
            home_lead = "leader"
        elif float(away_pts) > float(home_pts):
            away_lead = "leader"
    return {
        "home": Cell(
            "home",
            str(_get(row, "home_name") or MISSING),
            str(_get(row, "home_name") or ""),
            _member_href(row, "home_manager_id"),
        ),
        "home_pts": Cell("home_pts", _fixed(home_pts, 1), _raw(home_pts), emphasis=home_lead),
        "away": Cell(
            "away",
            str(_get(row, "away_name") or MISSING),
            str(_get(row, "away_name") or ""),
            _member_href(row, "away_manager_id"),
        ),
        "away_pts": Cell("away_pts", _fixed(away_pts, 1), _raw(away_pts), emphasis=away_lead),
        "lineups": Cell("lineups", "lineups", str(_get(row, "id") or ""), _lineup_href(row)),
    }


def _playoff_map(row: Mapping[str, Any], index: int) -> dict[str, Cell]:
    rank = _get(row, "rank")
    leader = (int(rank) == 1) if rank is not None else index == 0
    name = str(_get(row, "display_name") or "")
    return {
        "rank": Cell("rank", _int_text(rank), _raw(rank)),
        "manager": Cell(
            "manager",
            name or MISSING,
            name,
            _member_href(row, "manager_id"),
            "leader" if leader else "",
        ),
        "pf": Cell("pf", _fixed(_get(row, "points_for"), 2), _raw(_get(row, "points_for"))),
    }


_CELL_MAPS = {
    "career_rankings": _career_map,
    "standings": _standings_map,
    "scoring_distribution": _distribution_map,
    "matchups": _matchup_map,
    "playoff_path": _playoff_map,
}


def _modern_record(row: Mapping[str, Any], wins: int, losses: int, ties: int) -> str:
    existing = _get(row, "record")
    if existing:
        return str(existing)
    if ties:
        return f"{wins}-{losses}-{ties}"
    return f"{wins}-{losses}"


def _player_href(row: Mapping[str, Any]) -> str | None:
    player_id = _get(row, "player_id")
    if not player_id:
        return None
    return qhref(f"/players/{player_id}")


def _member_href(row: Mapping[str, Any], key: str) -> str | None:
    manager_id = _get(row, key)
    if not manager_id:
        return None
    return qhref(f"/members/{manager_id}")


def _lineup_href(row: Mapping[str, Any]) -> str | None:
    year = _get(row, "year") or _year_from_request()
    week = _get(row, "week")
    game_id = _get(row, "id")
    if year is None or week is None or not game_id:
        return None
    return qhref(f"/seasons/{int(year)}/week/{int(week)}/{game_id}")


def _year_from_request() -> int | None:
    request = current_request.get()
    if request is None:
        return None
    match = re.search(r"/seasons/(\d+)", request.url.path)
    if not match:
        return None
    return int(match.group(1))


# --- environments ------------------------------------------------------------

def _environment(templates: Jinja2Templates, theme: str) -> jinja2.Environment:
    loader = jinja2.ChoiceLoader(
        [
            jinja2.FileSystemLoader(str(THEME_ROOT / theme)),
            jinja2.FileSystemLoader(str(SHARED_DIR)),
            jinja2.FileSystemLoader(str(LEGACY_DIR)),
        ]
    )
    env = jinja2.Environment(
        loader=loader,
        autoescape=jinja2.select_autoescape(),
        auto_reload=True,
    )
    _prime(templates, env)
    return env


def _prime(templates: Jinja2Templates, env: jinja2.Environment) -> None:
    templates._setup_env_defaults(env)
    env.filters.update(templates.env.filters)
    env.globals.update(templates.env.globals)
    env.globals["present"] = present
    env.globals["theme_href"] = theme_href
    env.globals["theme_choices"] = theme_choices
    env.globals["theme_name"] = theme_name
    env.globals["qhref"] = qhref
    env.globals["league_tasks"] = league_tasks
    env.globals["fantasy_links"] = fantasy_links
    env.globals["season_panes"] = season_panes
    env.globals["active_pane"] = active_pane
    env.globals["week_slice"] = week_slice
    env.globals["theme_include"] = theme_include


def _shared_environment(templates: Jinja2Templates) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(SHARED_DIR)),
        autoescape=jinja2.select_autoescape(),
        auto_reload=True,
    )
    _prime(templates, env)
    return env


# --- contract ----------------------------------------------------------------

def collect_contract_problems() -> list[str]:
    """Everything that must be true before a themed page is served."""
    problems: list[str] = []
    problems.extend(_coverage_problems())
    problems.extend(_macro_problems())
    problems.extend(_source_problems())
    problems.extend(_render_problems())
    return problems


def _html_set(theme: str) -> set[str]:
    root = THEME_ROOT / theme
    if not root.is_dir():
        return set()
    return {path.relative_to(root).as_posix() for path in root.rglob("*.html")}


def _coverage_problems() -> list[str]:
    problems: list[str] = []
    sets = {theme: _html_set(theme) for theme in THEMES if theme != "modern"}
    union = set.union(*sets.values()) if sets else set()
    for theme, files in sets.items():
        for name in REQUIRED_THEME_FILES:
            if name not in files:
                problems.append(f"{theme} is missing required template {name}")
        for name in sorted(union - files):
            problems.append(f"{theme} is missing {name}, which another era overrides")
    for pane_id, _label in modern_pane_names():
        relative = f"panes/{pane_id}.html"
        for theme in THEMES:
            if theme == "modern":
                continue
            if not (THEME_ROOT / theme / relative).is_file() and not (SHARED_DIR / relative).is_file():
                problems.append(f"{theme} cannot resolve {relative}")
    return problems


def _macro_names(path: Path) -> set[str]:
    return set(_MACRO_NAME.findall(path.read_text(encoding="utf-8")))


def _macro_problems() -> list[str]:
    problems: list[str] = []
    legacy_path = LEGACY_DIR / "scoring_macros.html"
    legacy = _macro_names(legacy_path)
    legacy_text = legacy_path.read_text(encoding="utf-8")
    if 'theme_include("boards/scoring_distribution.html"' not in legacy_text:
        problems.append("scoring_macros.html distribution must theme_include the board")
    for theme in ("era90", "era2010"):
        path = THEME_ROOT / theme / "scoring_macros.html"
        if not path.is_file():
            continue
        found = _macro_names(path)
        if found != legacy:
            missing = sorted(legacy - found)
            extra = sorted(found - legacy)
            problems.append(
                f"{theme}/scoring_macros.html macros drifted; missing {missing}; extra {extra}"
            )
    for theme in ("era90", "era2010"):
        for path in (THEME_ROOT / theme).rglob("*.html"):
            if path.name == "scoring_macros.html":
                continue
            for imported in _imported_macros(path.read_text(encoding="utf-8")):
                if imported not in THEMED_MACROS:
                    problems.append(
                        f"{theme}/{path.relative_to(THEME_ROOT / theme).as_posix()} "
                        f"imports unthemed macro {imported}"
                    )
    return problems


def _imported_macros(text: str) -> list[str]:
    names: list[str] = []
    for block in _MACRO_IMPORT.findall(text):
        for part in block.split(","):
            name = part.strip()
            if name:
                names.append(name)
    return names


def _source_problems() -> list[str]:
    problems: list[str] = []
    for path in THEME_ROOT.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(THEME_ROOT).as_posix()
        for token in FORBIDDEN_TEMPLATE_TOKENS:
            if token in text:
                problems.append(f"{relative} reads {token}; walk present() cells instead")
    for theme in ("era90", "era2010"):
        base = (THEME_ROOT / theme / "base.html").read_text(encoding="utf-8")
        if "hub.css" in base or "hub.js" in base:
            problems.append(f"{theme}/base.html pulls the modern stylesheet or script")
        if theme == "era90" and "stylesheet" in base:
            problems.append("era90/base.html links a stylesheet; 1998 chrome is FONT and TABLE")
        if theme == "era2010" and "era2010.css" not in base:
            problems.append("era2010/base.html does not link era2010.css")
    for path in (THEME_ROOT / "era90").rglob("boards/*.html"):
        text = path.read_text(encoding="utf-8")
        if "bgcolor" in text or "<th" in text or "class=" in text:
            problems.append(
                f"era90/{path.name} uses a header fill, th, or class; Reeve tables are td and bold"
            )
        if 'border="2"' not in text or 'cellpadding="5"' not in text:
            problems.append(f"era90/{path.name} is missing border=2 cellpadding=5")
        if "present(" not in text:
            problems.append(f"era90/{path.name} does not call present()")
    modern_board = THEME_ROOT / "modern" / "boards" / "career_rankings.html"
    if modern_board.is_file():
        text = modern_board.read_text(encoding="utf-8")
        if "js-sort" not in text or "<th" not in text or "present(" not in text:
            problems.append("modern career board left the hub table grammar")
    era2010_board = THEME_ROOT / "era2010" / "boards" / "career_rankings.html"
    if era2010_board.is_file() and "board.more_href" not in era2010_board.read_text(encoding="utf-8"):
        problems.append("era2010 career board has no View All hook")
    return problems


def _render_problems() -> list[str]:
    problems: list[str] = []
    for name, check in (
        ("career", _render_career),
        ("standings", _render_standings),
        ("distribution", _render_distribution),
        ("weeks", _render_weeks),
        ("limit", _render_limit),
    ):
        try:
            problems.extend(check())
        except Exception as exc:
            problems.append(f"{name} render failed: {exc}")
    return problems


def _bind(path: str, query: str, theme: str) -> tuple[Token[str], Token[Request | None]]:
    return (
        current_theme.set(theme),
        current_request.set(_fake_request(path, query)),
    )


def _release(tokens: tuple[Token[str], Token[Request | None]]) -> None:
    current_theme.reset(tokens[0])
    current_request.reset(tokens[1])


def _fake_request(path: str, query: str) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8121),
        "root_path": "",
    }
    return Request(scope)


def _visible(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parsed_cells(page: str) -> list[tuple[str, str, str]]:
    cells: list[tuple[str, str, str]] = []
    for key, _gap, raw, _tail, body in _CELL.findall(page):
        cells.append((html.unescape(key), html.unescape(raw), _visible(body)))
    return cells


def _raws_equal(left: str, right: str) -> bool:
    if left == right:
        return True
    try:
        return abs(float(left) - float(right)) <= 1e-6
    except ValueError:
        return False


def _expect_board(page: str, board: Board, label: str) -> list[str]:
    parsed = _parsed_cells(page)
    expected = [cell for row in board.rows for cell in row]
    problems: list[str] = []
    if len(parsed) != len(expected):
        found = [key for key, _raw, _text in parsed]
        wanted = [cell.key for cell in expected]
        problems.append(f"{label} cell count {len(parsed)} != {len(expected)} ({found} vs {wanted})")
        return problems
    for index, (found, cell) in enumerate(zip(parsed, expected, strict=True)):
        key, raw, text = found
        where = f"{label} cell {index} ({cell.key})"
        if key != cell.key:
            problems.append(f"{where} key {key!r}")
        if not _raws_equal(raw, cell.raw):
            problems.append(f"{where} raw {raw!r} != {cell.raw!r}")
        if text != cell.text:
            problems.append(f"{where} text {text!r} != {cell.text!r}")
    return problems


_CAREER_FIXTURE: list[dict[str, Any]] = [
    {
        "player_id": "p1",
        "player_name": "Aaron Rodgers",
        "position": "QB",
        "seasons": 3,
        "starts": 30,
        "starter_points": 600.0,
        "avg": 20.0,
        "started_vorp": 80.5,
    },
    {
        "player_id": "p2",
        "player_name": "Saquon Barkley",
        "position": "RB",
        "seasons": 2,
        "starts": 20,
        "starter_points": 400.5,
        "avg": 20.0,
        "started_vorp": 10.0,
    },
    {
        "player_id": "p3",
        "player_name": "Amon-Ra St. Brown",
        "position": "WR",
        "seasons": 2,
        "starts": 18,
        "starter_points": 300.0,
        "avg": 16.5,
        "started_vorp": 4.0,
    },
]

_STANDINGS_FIXTURE: list[dict[str, Any]] = [
    {
        "manager_id": "m1",
        "display_name": "Alex Kim",
        "rank": 1,
        "wins": 8,
        "losses": 5,
        "ties": 0,
        "points_for": 1500.25,
        "points_against": 1400.5,
        "win_pct": 0.615,
        "record": "8-5",
    },
    {
        "manager_id": "m2",
        "display_name": "Blair Jones",
        "rank": 2,
        "wins": 7,
        "losses": 5,
        "ties": 1,
        "points_for": 1400.0,
        "points_against": 1410.0,
        "win_pct": 0.577,
        "record": "7-5-1",
    },
]

_DISTRIBUTION_FIXTURE: dict[str, Any] = {
    "manager_weeks": 168,
    "managers": 12,
    "avg": 112.5,
    "median": 110.25,
    "stddev": 18.25,
    "min": 62.5,
    "max": 178.5,
    "total_pf": 18873.5,
    "deciles": [],
}

_GAME_FIXTURE: dict[str, Any] = {
    "id": "g1",
    "week": 1,
    "year": 2024,
    "home_manager_id": "h",
    "home_name": "Alex Kim",
    "home_points": 120.5,
    "away_manager_id": "a",
    "away_name": "Blair Jones",
    "away_points": 98.0,
}


def _render_career() -> list[str]:
    problems: list[str] = []
    boards: dict[str, Board] = {}
    pages: dict[str, str] = {}
    for theme in THEMES:
        tokens = _bind("/players", f"theme={theme}", theme)
        try:
            page = _ENVS[theme].get_template("players.html").render(
                career=_CAREER_FIXTURE,
                title="Players",
                nav="players",
            )
            boards[theme] = present("career_rankings", _CAREER_FIXTURE)
        finally:
            _release(tokens)
        pages[theme] = page
        problems.extend(_expect_board(page, boards[theme], f"{theme} career"))
    problems.extend(_cross_raws("career_rankings", boards))
    if "Aaron Rodgers" not in pages["era90"] or "A. Rodgers" in pages["era90"]:
        problems.append("era90 career should show the full player name")
    if "A. Rodgers" not in pages["era2010"] or "A. St. Brown" not in pages["era2010"]:
        problems.append("era2010 career should use initial-and-last, keeping a last-name particle")
    if "hub.css" in pages["era90"] or "hub.js" in pages["era90"]:
        problems.append("era90 players page pulled modern assets")
    if "#660000" not in pages["era90"] or "FANTASY LINKS" not in pages["era90"]:
        problems.append("era90 players page is missing the commissioner band or link box")
    if "era2010.css" not in pages["era2010"] or "hub.css" in pages["era2010"]:
        problems.append("era2010 players page has the wrong stylesheet")
    if "hub.css" not in pages["modern"] or "js-sort" not in pages["modern"]:
        problems.append("modern players page left the hub table")
    if "<b>600.0</b>" not in pages["era90"]:
        problems.append("era90 leader points are not bold text")
    return problems


def _render_standings() -> list[str]:
    problems: list[str] = []
    context = {
        "current": {"year": 2024},
        "title": "2024 season",
        "nav": "seasons",
        "standings": _STANDINGS_FIXTURE,
        "schedule": {"regular": [], "weeks": []},
        "now_week": None,
        "path": [],
        "trades": [],
        "wire": {},
        "draft": {},
        "lineups": {},
        "stacks": {"stack_weeks": 0, "managers_with_stack": 0},
    }
    boards: dict[str, Board] = {}
    for theme in ("era90", "era2010"):
        tokens = _bind("/seasons/2024", f"theme={theme}&pane=standings", theme)
        try:
            page = _ENVS[theme].get_template("season.html").render(**context)
            boards[theme] = present("standings", _STANDINGS_FIXTURE)
        finally:
            _release(tokens)
        problems.extend(_expect_board(page, boards[theme], f"{theme} standings"))
        for _pane_id, label in modern_pane_names():
            if label not in page:
                problems.append(f"{theme} season shell dropped pane {label}")
    problems.extend(_cross_raws("standings", boards))
    if boards["era90"].rows[0]["t"].text != "-":
        problems.append("era90 zero ties must render as -")
    if boards["era2010"].rows[0]["record"].text != "8-5-0":
        problems.append("era2010 record must stay W-L-T, including a zero tie")
    if "bgcolor" in (THEME_ROOT / "era90" / "boards" / "standings.html").read_text(encoding="utf-8"):
        problems.append("era90 standings board paints a cell")
    return problems


def _render_distribution() -> list[str]:
    problems: list[str] = []
    texts: dict[str, list[str]] = {}
    for theme in THEMES:
        tokens = _bind(f"/seasons/2024/scoring", f"theme={theme}", theme)
        try:
            template = _ENVS[theme].from_string(
                '{% from "scoring_macros.html" import distribution %}{{ distribution(season) }}'
            )
            page = template.render(season=_DISTRIBUTION_FIXTURE)
            board = present("scoring_distribution", [_DISTRIBUTION_FIXTURE])
        finally:
            _release(tokens)
        problems.extend(_expect_board(page, board, f"{theme} distribution"))
        texts[theme] = [text for _key, _raw, text in _parsed_cells(page)]
    if texts["era90"] != texts["modern"] or texts["era2010"] != texts["modern"]:
        problems.append(
            "scoring distribution digits drifted across themes: "
            f"modern={texts['modern']} era90={texts['era90']} era2010={texts['era2010']}"
        )
    return problems


def _render_weeks() -> list[str]:
    problems: list[str] = []
    schedule = {"regular": [(1, [_GAME_FIXTURE]), (2, [])], "weeks": [1, 2]}
    context = {
        "current": {"year": 2024},
        "title": "2024 season",
        "nav": "seasons",
        "standings": _STANDINGS_FIXTURE,
        "schedule": schedule,
        "now_week": 2,
        "path": [],
        "trades": [],
        "wire": {},
        "draft": {},
        "lineups": {},
        "stacks": {"stack_weeks": 4, "managers_with_stack": 2},
    }
    for theme in ("era90", "era2010"):
        tokens = _bind("/seasons/2024", f"theme={theme}&pane=weeks&week=1", theme)
        try:
            page = _ENVS[theme].get_template("season.html").render(**context)
            board = present("matchups", [{**_GAME_FIXTURE}])
        finally:
            _release(tokens)
        problems.extend(_expect_board(page, board, f"{theme} matchups"))
        if ">1<" not in page and ">1</a>" not in page and ">1</b>" not in page:
            problems.append(f"{theme} weeks pane is missing numeral 1")
        if "Results" not in page and theme == "era90":
            problems.append("era90 weeks pane is missing the Results numeral row")
        if "matchup" not in page and theme == "era2010":
            problems.append("era2010 weeks pane is missing matchup cards")
        if "<b>120.5</b>" not in page:
            problems.append(f"{theme} did not bold the higher score")
    tokens = _bind("/seasons/2024", "theme=era90&pane=stacks", "era90")
    try:
        page = _ENVS["era90"].get_template("season.html").render(**context)
    finally:
        _release(tokens)
    if "4 regular-season stacks" not in page:
        problems.append("stacks pane did not fall through to the shared summary")
    return problems


def _render_limit() -> list[str]:
    problems: list[str] = []
    rows = [
        {
            "player_id": str(index),
            "player_name": f"Player {index} Name",
            "position": "WR",
            "seasons": 1,
            "starts": index,
            "starter_points": 1000 - index,
            "avg": 10.0,
            "started_vorp": 1.0,
        }
        for index in range(1, 12)
    ]
    tokens = _bind("/players", "theme=era2010", "era2010")
    try:
        board = present("career_rankings", rows)
        if board.shown != CAREER_MODULE or board.more_href is None or "rows=all" not in board.more_href:
            problems.append("era2010 career module did not cap at 10 with a View All link")
    finally:
        _release(tokens)
    tokens = _bind("/players", "theme=era2010&rows=all", "era2010")
    try:
        board = present("career_rankings", rows)
        if board.shown != 11 or board.more_href is not None:
            problems.append("era2010 View All did not expand the module to the 50-row cap")
    finally:
        _release(tokens)
    return problems


def _cross_raws(board_id: str, boards: Mapping[str, Board]) -> list[str]:
    problems: list[str] = []
    themes = [theme for theme, board in boards.items() if board.rows]
    for left_index, left in enumerate(themes):
        for right in themes[left_index + 1 :]:
            shared = [key for key in PROJECTIONS[board_id][left] if key in PROJECTIONS[board_id][right]]
            for key in shared:
                for row_index, (left_row, right_row) in enumerate(
                    zip(boards[left].rows, boards[right].rows, strict=False)
                ):
                    if not _raws_equal(left_row[key].raw, right_row[key].raw):
                        problems.append(
                            f"{board_id} raw {key} row {row_index} drifted "
                            f"{left}={left_row[key].raw!r} {right}={right_row[key].raw!r}"
                        )
    return problems
