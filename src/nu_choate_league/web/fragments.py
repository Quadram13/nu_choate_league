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
    key: Callable[[Any], Any],
) -> PageWindow:
    """Stable page of ``rows``.

    ``key`` must be a total order. ``sorted`` is stable, and a total key
    means two requests over the same rows return the same sequence. Out of
    range pages are 404, same as an unknown board.
    """
    if page_size < 1:
        raise ValueError("page_size must be positive")
    if page < 1:
        raise StarletteHTTPException(status_code=404, detail="No such page.")
    ordered = tuple(sorted(rows, key=key))
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


def _nulls_first_desc(value: object) -> tuple:
    """Match Postgres ``ORDER BY col DESC`` (NULLS FIRST is the default)."""
    if value is None:
        return (0,)
    return (1, -value)  # type: ignore[operator]


def career_order_key(row: dict[str, Any]) -> tuple:
    """Same order as ``v_players_index_career``, plus ``player_id`` for ties.

    The index query sorts by starter points, started VORP, then name. Name
    is not unique, so the page key adds ``player_id``. That only moves a row
    when the query's three keys were tied.
    """
    return (
        _nulls_first_desc(row.get("starter_points")),
        _nulls_first_desc(row.get("started_vorp")),
        row.get("player_name") or "",
        str(row.get("player_id") or ""),
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
    window = paginate(
        career,
        page=requested_page(request),
        page_size=DEFAULT_PAGE_SIZE,
        key=career_order_key,
    )
    return {
        "pager": window,
        "vol_partial": any(row.get("vol_partial") for row in career),
    }


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
