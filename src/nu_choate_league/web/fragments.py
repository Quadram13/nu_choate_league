"""Fragment envelopes and numeral-row pagination.

One board template and one loader. ``/fragments/<board>`` returns the bare
template (no document shell) for the inline upgrade in ``hub.js``.
``/boards/<board>`` returns that same HTML inside the modern ``page()``
document. Home includes the same template files, so the desk and the
fragment cannot fork.

Pagination is ``?page=N`` on the board URL. The numeral row is
``fragments/pager.html``; era week links are the same macro with a different
href. See ``docs/ui/disclosure.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import queries

# Digest §4: a career index of about 520 rows wants a chosen page of 25 or 50
# and a stable sort. 50 is a short printable log (about 11 pages here) rather
# than 21. A standings table of ~12 rows stays one page, so a portal does not
# grow a numeral row. Callers do not take a page-size query; the size is part
# of the board.
DEFAULT_PAGE_SIZE = 50

# A season of week numerals stays fully expanded (1..18, each one a link).
# Longer rows collapse with an ellipsis so a 30-page index is still a row.
FULL_NUMERALS_UNTIL = 18

Context = dict[str, Any]
Loader = Callable[[Request], Context]


@dataclass(frozen=True)
class Board:
    name: str
    template: str
    title: str
    nav: str
    loader: Loader


@dataclass(frozen=True)
class PageWindow:
    page: int
    pages: int
    page_size: int
    total: int
    rows: tuple[Any, ...]


def requested_page(request: Request) -> int:
    """``?page=N`` as a 1-based page. Missing means page 1. Anything else is 404."""
    raw = request.query_params.get("page")
    if raw is None or raw == "":
        return 1
    if not raw.isascii() or not raw.isdigit():
        raise StarletteHTTPException(status_code=404, detail="No such page.")
    number = int(raw)
    if number < 1:
        raise StarletteHTTPException(status_code=404, detail="No such page.")
    return number


def numeral_tokens(
    current: int,
    last: int,
    *,
    full_until: int = FULL_NUMERALS_UNTIL,
) -> list[int | None]:
    """Page numerals. ``None`` is an ellipsis, not a link.

    ``last <= full_until`` renders every numeral, which is the era week row
    (``Results 1 2 3 … 18`` with each week present). Longer rows keep the
    first, the last, and a window of two on each side of the current page,
    and fill a gap of exactly one so the ellipsis never hides a single page.
    """
    current = int(current)
    last = int(last)
    if last < 1:
        return []
    if current < 1 or current > last:
        raise StarletteHTTPException(status_code=404, detail="No such page.")
    if last <= full_until:
        return list(range(1, last + 1))
    keep = {1, last}
    keep.update(range(max(1, current - 2), min(last, current + 2) + 1))
    changed = True
    while changed:
        changed = False
        ordered = sorted(keep)
        for left, right in zip(ordered, ordered[1:]):
            if right - left == 2:
                keep.add(left + 1)
                changed = True
    tokens: list[int | None] = []
    previous = 0
    for number in sorted(keep):
        if previous and number > previous + 1:
            tokens.append(None)
        tokens.append(number)
        previous = number
    return tokens


def paginate(
    rows: Sequence[Any],
    *,
    page: int,
    page_size: int = DEFAULT_PAGE_SIZE,
    key: Callable[[Any], Any] | None = None,
) -> PageWindow:
    """One page of ``rows``.

    Pass ``key`` when the input is not already in a stable order. ``sorted``
    is stable, so a total key returns the same sequence on every request.
    Omit ``key`` to keep the input order, which is the right call when a
    query already sorted the rows and a second sort would not match it.
    Out of range pages are 404, same as an unknown board.
    """
    if page_size < 1:
        raise ValueError("page_size must be positive")
    if page < 1:
        raise StarletteHTTPException(status_code=404, detail="No such page.")
    ordered = tuple(sorted(rows, key=key) if key is not None else rows)
    total = len(ordered)
    pages = (total + page_size - 1) // page_size if total else 1
    if page > pages:
        raise StarletteHTTPException(status_code=404, detail="No such page.")
    start = (page - 1) * page_size
    return PageWindow(
        page=page,
        pages=pages,
        page_size=page_size,
        total=total,
        rows=ordered[start : start + page_size],
    )


def load_home_standings(request: Request) -> Context:
    """Same facts as ``queries.home_desk`` puts on the desk standings table."""
    del request
    year = queries.latest_scored_year()
    current = queries.season_row(year) if year is not None else None
    table = queries.standings(year) if year is not None else []
    return {"year": year, "current": current, "standings": table}


def load_home_slate(request: Request) -> Context:
    """Same slate construction as ``queries.home_desk`` (groups + week card)."""
    del request
    year = queries.latest_scored_year()
    weeks = queries.scored_weeks(year) if year is not None else []
    now = int(weeks[-1]) if weeks else None
    slate = None
    if year is not None and now is not None:
        games = queries.week_slate(year, now)
        if games:
            slate = {"year": year, "week": now, "groups": games["groups"]}
    preview = queries.week_card(year, now) if year is not None and now is not None else None
    return {"year": year, "slate": slate, "preview": preview}


def load_players_career(request: Request) -> Context:
    """One page of the career ranking. Reads ``players_index``; does not change it.

    ``players_index`` still builds the season and wire boards. The fragment
    renders one page of career rows. A career-only query is D1's, not this
    ticket: ``queries.py`` stays read-only.
    """
    data = queries.players_index()
    career = data["career"]
    # Keep the query order. Re-sorting the float values disagrees with
    # ``ORDER BY starter_points DESC, started_vorp DESC, player_name`` once
    # distinct numerics collapse to the same float. That order is what
    # /players renders, and it does not move across requests.
    window = paginate(
        career,
        page=requested_page(request),
        page_size=DEFAULT_PAGE_SIZE,
    )
    return {
        "pager": window,
        "vol_partial": any(row.get("vol_partial") for row in career),
    }


def _load_player_split(name: str) -> Loader:
    """D1 (#105). Full row set for one players board. Append-only loader factory."""

    def load(request: Request) -> Context:
        del request
        payload = queries.players_board_payload(name)
        if payload is None:
            raise StarletteHTTPException(status_code=404, detail=f"No board {name}.")
        return payload

    return load


def _player_split_boards() -> tuple[Board, ...]:
    """Sortable full tables. The summary on /players slices the same rows.

    Appended beside the A3 paginated ``players-career`` log, which stays.
    Templates live under ``players/`` (D1's directory). Both envelopes render
    them through ``render_fragment``.
    """
    titles = {
        "players-career-rankings": ("players/career.html", "Career rankings"),
        "players-season-rankings": ("players/season.html", "Season rankings"),
        "players-wire-season": ("players/wire_season.html", "Wire season"),
        "players-wire-career": ("players/wire_career.html", "Wire career"),
        "players-wire-unowned": ("players/wire_unowned.html", "Never rostered"),
        "players-counting-career": ("players/counting_career.html", "Counting career"),
        "players-counting-season": ("players/counting_season.html", "Counting by season"),
    }
    specs = queries.player_split_board_specs()
    spec_names = {spec["name"] for spec in specs}
    title_names = set(titles)
    if spec_names != title_names:
        raise RuntimeError(
            "D1 player boards and templates disagree: "
            f"specs-only={sorted(spec_names - title_names)} "
            f"templates-only={sorted(title_names - spec_names)}"
        )
    return tuple(
        Board(
            name=spec["name"],
            template=titles[spec["name"]][0],
            title=titles[spec["name"]][1],
            nav="players",
            loader=_load_player_split(spec["name"]),
        )
        for spec in specs
    )


BOARDS: dict[str, Board] = {}


def _register_boards() -> None:
    specs = (
        Board(
            name="home-standings",
            template="fragments/home_standings.html",
            title="Standings",
            nav="home",
            loader=load_home_standings,
        ),
        Board(
            name="home-slate",
            template="fragments/home_slate.html",
            title="Week slate",
            nav="home",
            loader=load_home_slate,
        ),
        Board(
            name="players-career",
            template="fragments/players_career.html",
            title="Career rankings",
            nav="players",
            loader=load_players_career,
        ),
    )
    BOARDS.clear()
    BOARDS.update({spec.name: spec for spec in specs})
    # D1 (#105): register after the A3 boards so a re-call of this function
    # keeps the split. Existing board names, loaders, and page size are unchanged.
    for spec in _player_split_boards():
        if spec.name in BOARDS:
            raise RuntimeError(f"duplicate board {spec.name}")
        BOARDS[spec.name] = spec
    # D2 (#106): same envelope, registered after D1. Bodies live outside
    # fragments/ because they keep the season and member tables.
    for spec in _deferred_boards():
        if spec.name in BOARDS:
            raise RuntimeError(f"duplicate board {spec.name}")
        BOARDS[spec.name] = spec


def _query_year(request: Request) -> int:
    raw = request.query_params.get("year")
    if raw is None or not str(raw).isascii() or not str(raw).isdigit():
        raise StarletteHTTPException(status_code=404, detail="Missing year.")
    return int(raw)


def _season_fragment(name: str, part: str, title: str) -> Board:
    def load(request: Request) -> Context:
        year = _query_year(request)
        data = queries.season_board(year, part)
        if data is None:
            raise StarletteHTTPException(status_code=404, detail=f"No season {year}.")
        data["fragment_href"] = f"/fragments/{name}"
        data["board_href"] = f"/boards/{name}"
        data["body"] = f"season/{part}.html"
        return data

    return Board(
        name=name,
        template="deferred/envelope.html",
        title=title,
        nav="seasons",
        loader=load,
    )


def _member_fragment(name: str, section: str, title: str, body: str) -> Board:
    def load(request: Request) -> Context:
        manager = request.query_params.get("manager") or ""
        if not manager:
            raise StarletteHTTPException(status_code=404, detail="Missing manager.")
        data = queries.member_page(manager, section=section)
        if data is None:
            raise StarletteHTTPException(status_code=404, detail=f"No manager {manager}.")
        data["fragment_href"] = f"/fragments/{name}"
        data["board_href"] = f"/boards/{name}"
        data["body"] = body
        return data

    return Board(
        name=name,
        template="deferred/envelope.html",
        title=title,
        nav="members",
        loader=load,
    )


def _deferred_boards() -> tuple[Board, ...]:
    season = (
        ("season-universes", "universes", "Universes"),
        ("season-power", "power", "All-play"),
        ("season-heat", "heat", "Week ranks"),
        ("season-race", "race", "Points race"),
        ("season-weeks", "weeks", "Weeks"),
        ("season-playoffs", "playoffs", "Playoffs"),
        ("season-moves", "moves", "Moves"),
        ("season-draft", "draft", "Draft"),
        ("season-lineups", "lineups", "Lineups"),
        ("season-stacks", "stacks", "Stacks"),
    )
    member = (
        ("member-h2h", "h2h", "Head-to-head", "member/h2h.html"),
        ("member-draft", "draft", "Draft", "member/draft.html"),
        ("member-wire", "wire", "Wire", "member/wire.html"),
        ("member-trades", "trades", "Trades", "member/trades.html"),
        ("member-draft-board", "draft-board", "Draft board", "member/draft-board.html"),
        ("member-partners", "partners", "Trade partners", "member/partners.html"),
        ("member-waiver", "waiver-roi", "Waiver priority", "member/waiver-roi.html"),
        ("member-roster", "roster-shape", "Roster shape", "member/roster-shape.html"),
        ("member-lineups", "lineups", "Lineups", "member/lineups.html"),
        ("member-luck", "luck", "Luck", "member/luck.html"),
        ("member-highs", "highs", "Highs", "member/highs.html"),
        ("member-consistency", "consistency", "Consistency", "member/consistency.html"),
        ("member-clutch", "clutch", "Clutch", "member/clutch.html"),
    )
    return tuple(_season_fragment(name, part, title) for name, part, title in season) + tuple(
        _member_fragment(name, section, title, body) for name, section, title, body in member
    )


_register_boards()


def board_by_name(name: str) -> Board:
    try:
        return BOARDS[name]
    except KeyError:
        raise StarletteHTTPException(status_code=404, detail=f"No board {name}.") from None


def render_fragment(request: Request, name: str) -> str:
    """Render one board template. Both envelopes call this."""
    spec = board_by_name(name)
    from .app import templates

    templates.env.globals["numeral_tokens"] = numeral_tokens
    context = spec.loader(request)
    context["request"] = request
    template = templates.env.get_template(spec.template)
    return template.render(context)


def board_fragment(request: Request, board: str) -> HTMLResponse:
    """Bare fragment. No ``<html>`` shell, so a parent page can swap it inline."""
    return HTMLResponse(render_fragment(request, board))


def board_document(request: Request, board: str) -> HTMLResponse:
    """The same fragment inside the modern document shell (``page()``)."""
    from . import themes

    if themes.resolve_theme(request) == "era90":
        return themes.era90_board_document(request, board)
    spec = board_by_name(board)
    html = render_fragment(request, board)
    from .app import page

    return page(
        request,
        "board.html",
        nav=spec.nav,
        title=spec.title,
        fragment_html=html,
    )


def install() -> None:
    """Publish ``numeral_tokens`` to Jinja so ``pager.html`` can call it."""
    from .app import templates

    templates.env.globals["numeral_tokens"] = numeral_tokens
