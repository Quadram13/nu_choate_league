from __future__ import annotations

import functools
import inspect

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..paths import project_root
from . import queries, themes
from .names import flavor_team, manager_hue
from .photos import avatar_url, headshot_url

HUB_DIR = project_root() / "hub"
templates = Jinja2Templates(directory=str(HUB_DIR / "templates"))
templates.env.filters["flavor_team"] = lambda team, member=None: flavor_team(member, team)
templates.env.globals["headshot_url"] = headshot_url
templates.env.globals["avatar_url"] = avatar_url
templates.env.globals["manager_hue"] = manager_hue

# --- A2 theme wiring (#98). Fail closed before any route is registered. ---
themes.install(templates)


def _with_db(endpoint):
    @functools.wraps(endpoint)
    def wrapped(*args, **kwargs):
        conn = queries.connect()
        token = queries.bind_connection(conn)
        try:
            return endpoint(*args, **kwargs)
        finally:
            queries.unbind_connection(token)
            conn.close()

    wrapped.__signature__ = inspect.signature(endpoint)
    return wrapped


class HubRoute(APIRoute):
    def __init__(self, path: str, endpoint, **kwargs):
        if not inspect.iscoroutinefunction(endpoint):
            endpoint = _with_db(endpoint)
        super().__init__(path, endpoint, **kwargs)


app = FastAPI(title="Nu Choate League", docs_url=None, redoc_url=None)
app.router.route_class = HubRoute
app.mount("/static", StaticFiles(directory=str(HUB_DIR / "static")), name="static")


# --- A2 theme wiring (#98). ?theme= wins, then the cookie, then modern. ---
@app.middleware("http")
async def persist_theme_cookie(request: Request, call_next):
    response = await call_next(request)
    return themes.persist_theme(request, response)


def page(request: Request, name: str, *, nav: str, title: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        name,
        {"nav": nav, "title": title, **context, "theme": themes.resolve_theme(request)},
    )


@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> HTMLResponse:
    status = exc.status_code
    heading = "Not found" if status == 404 else "Hub unavailable"
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "nav": "",
            "title": heading,
            "theme": themes.resolve_theme(request),
            "status": status,
            "detail": exc.detail,
        },
        status_code=status,
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    # --- C1a era90 portal (#100). The modern desk below is unchanged. ---
    if themes.resolve_theme(request) == "era90":
        return themes.era90_home(request)
    data = queries.home_desk()
    return page(
        request,
        "home.html",
        nav="home",
        title="Nu Choate League",
        **data,
    )


@app.get("/seasons", response_model=None)
def seasons(request: Request) -> HTMLResponse | RedirectResponse:
    years = queries.list_seasons()
    if not years:
        return page(
            request,
            "seasons.html",
            nav="seasons",
            title="Seasons",
            seasons=[],
        )
    year = queries.latest_scored_year() or years[0]["year"]
    return RedirectResponse(url=f"/seasons/{year}", status_code=302)


@app.get("/seasons/{year}", response_class=HTMLResponse)
def season(request: Request, year: int) -> HTMLResponse:
    # --- A2 era dispatch (#98). Modern falls through to the legacy document. ---
    if themes.resolve_theme(request) != "modern":
        return themes.season_document(request, year)
    data = queries.season_page(year)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    return page(
        request,
        "season.html",
        nav="seasons",
        title=f"{year} season",
        **data,
    )


@app.get("/seasons/{year}/trades/{transaction_id}", response_class=HTMLResponse)
def trade(request: Request, year: int, transaction_id: str) -> HTMLResponse:
    current = queries.season_row(year)
    if current is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    data = queries.trade_page(year, transaction_id)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No trade {transaction_id} in {year}.")
    return page(
        request,
        "trade.html",
        nav="seasons",
        title=f"{data['left']['name']} vs {data['right']['name']}",
        current=current,
        trade=data,
    )


@app.get("/seasons/{year}/moves", response_class=HTMLResponse)
def season_moves(request: Request, year: int) -> HTMLResponse:
    data = queries.moves_log(year)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    return page(
        request,
        "moves.html",
        nav="seasons",
        title=f"{year} moves",
        **data,
    )


@app.get("/seasons/{year}/draft", response_class=HTMLResponse)
def draft(request: Request, year: int) -> HTMLResponse:
    current = queries.season_row(year)
    if current is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    data = queries.draft_page(year)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No draft in {year}.")
    return page(
        request,
        "draft.html",
        nav="seasons",
        title=f"{year} draft",
        current=current,
        draft=data,
    )


@app.get("/seasons/{year}/wire/{transaction_id}", response_class=HTMLResponse)
def wire(request: Request, year: int, transaction_id: str) -> HTMLResponse:
    current = queries.season_row(year)
    if current is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    data = queries.wire_page(year, transaction_id)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No wire claim {transaction_id} in {year}.")
    return page(
        request,
        "wire.html",
        nav="seasons",
        title=f"{data['player_name']} · {year} W{data['week']}",
        current=current,
        claim=data,
    )


@app.get("/seasons/{year}/week/{week}", response_class=HTMLResponse)
def week(request: Request, year: int, week: int) -> HTMLResponse:
    current = queries.season_row(year)
    if current is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    data = queries.week_slate(year, week)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No scored games in {year} week {week}.")
    return page(
        request,
        "week.html",
        nav="seasons",
        title=f"{year} week {week}",
        current=current,
        gc=data,
    )


@app.get("/seasons/{year}/week/{week}/{matchup_id}", response_class=HTMLResponse)
def gamecenter(request: Request, year: int, week: int, matchup_id: str) -> HTMLResponse:
    current = queries.season_row(year)
    if current is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    data = queries.gamecenter(year, week, matchup_id)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No matchup {matchup_id} in {year} week {week}.")
    game = data["game"]
    return page(
        request,
        "gamecenter.html",
        nav="seasons",
        title=f"{game['home']['name']} vs {game['away']['name']}",
        current=current,
        gc=data,
    )


@app.get("/seasons/{year}/marks", response_class=HTMLResponse)
def season_marks(request: Request, year: int) -> HTMLResponse:
    current = queries.season_row(year)
    if current is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    return page(
        request,
        "marks.html",
        nav="seasons",
        title=f"{year} distinctions",
        current=current,
        **queries.week_marks_season(year),
        seasons=queries.list_seasons(),
    )


@app.get("/seasons/{year}/desk", response_class=HTMLResponse)
def schedule_desk(request: Request, year: int) -> HTMLResponse:
    data = queries.schedule_desk_page(year)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    return page(
        request,
        "desk.html",
        nav="seasons",
        title=f"{year} schedule desk",
        **data,
    )


@app.get("/seasons/{year}/scoring", response_class=HTMLResponse)
def scoring(request: Request, year: int) -> HTMLResponse:
    data = queries.scoring_sheet(year)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    return page(
        request,
        "scoring.html",
        nav="seasons",
        title=f"{year} scoring",
        **data,
    )


@app.get("/versus", response_class=HTMLResponse)
def versus(request: Request) -> HTMLResponse:
    return page(
        request,
        "versus.html",
        nav="versus",
        title="Versus",
        **queries.versus_grid(),
    )


@app.get("/versus/{left_id}/{right_id}", response_class=HTMLResponse)
def versus_pair(request: Request, left_id: str, right_id: str) -> HTMLResponse:
    data = queries.versus_pair(left_id, right_id)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail="No versus series for that pair.")
    return page(
        request,
        "versus_pair.html",
        nav="versus",
        title=f"{data['left']['display_name']} vs {data['right']['display_name']}",
        **data,
    )


@app.get("/members", response_class=HTMLResponse)
def members(request: Request) -> HTMLResponse:
    rows = queries.career()
    return page(
        request,
        "members.html",
        nav="members",
        title="All-time standings",
        career=rows,
        luck_plaques=queries.luck_plaques(rows, href="/members"),
    )


@app.get("/members/{manager_id}", response_class=HTMLResponse)
def member(request: Request, manager_id: str) -> HTMLResponse:
    data = queries.member_page(manager_id)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No manager {manager_id}.")
    return page(
        request,
        "member.html",
        nav="members",
        title=data["member"]["display_name"],
        **data,
    )


@app.get("/records", response_class=HTMLResponse)
def records(request: Request) -> HTMLResponse:
    selected = request.query_params.get("year")
    year = int(selected) if selected and selected.isdigit() else None
    return page(
        request,
        "records/index.html",
        nav="records",
        title="Record book",
        selected_year=year,
        year_qs=f"?year={year}" if year else "",
        **queries.records_index_page(),
    )


@app.get("/luck")
def luck() -> RedirectResponse:
    year = queries.latest_scored_year()
    if year is None:
        return RedirectResponse(url="/records#season", status_code=302)
    return RedirectResponse(url=f"/seasons/{year}#luck", status_code=302)


@app.get("/players", response_class=HTMLResponse)
def players(request: Request) -> HTMLResponse:
    # D1 (#105): summary prefix only. Full tables are A3 boards (see the block
    # at the end of this module). players_index() itself is unchanged.
    return page(
        request,
        "players.html",
        nav="players",
        title="Players",
        **queries.players_summary(),
    )


def _player_years(weeks: list) -> list[int]:
    return sorted({int(row["year"]) for row in weeks}, reverse=True)


def _filter_year(rows: list, year: int | None) -> list:
    if year is None:
        return list(rows)
    return [row for row in rows if int(row["year"]) == year]


def _load_player(player_id: str, *, anatomy: bool) -> dict | None:
    data = queries.player_page(player_id)
    if data is None:
        return None
    years = _player_years(data["weeks"])
    data["log_years"] = years
    data["current_year"] = years[0] if years else None
    if anatomy:
        data["anatomy"] = queries.player_anatomy(player_id)
    return data


def _selected_year(request: Request) -> int | None:
    raw = request.query_params.get("year")
    if raw and raw.isdigit():
        return int(raw)
    return None


# --- B1 player anatomy (#96). Profile keeps /players/{id}. Log and splits are the two new routes. ---


@app.get("/players/{player_id}", response_class=HTMLResponse)
def player(request: Request, player_id: str) -> HTMLResponse:
    data = _load_player(player_id, anatomy=True)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No player {player_id}.")
    data["shown_weeks"] = _filter_year(data["weeks"], data["current_year"]) if data["current_year"] else []
    person = data["player"]
    return page(
        request,
        "player.html",
        nav="players",
        title=person["player_name"],
        **data,
    )


# --- A3 loading: fragment routes (append-only) ---
from .fragments import board_document, board_fragment, install

install()


@app.get("/fragments/{board}", response_class=HTMLResponse)
def fragment_route(request: Request, board: str) -> HTMLResponse:
    return board_fragment(request, board)


@app.get("/boards/{board}", response_class=HTMLResponse)
def board_route(request: Request, board: str) -> HTMLResponse:
    return board_document(request, board)
# --- end A3 loading ---


# --- B2 record chapters (#97). /records above renders the index. ---


@app.get("/records/{chapter}", response_class=HTMLResponse)
def records_chapter(request: Request, chapter: str) -> HTMLResponse:
    view = queries.record_chapter_view(chapter)
    if view is None:
        raise StarletteHTTPException(
            status_code=404,
            detail=f"No records chapter {chapter}.",
        )
    selected = request.query_params.get("year")
    year = int(selected) if selected and selected.isdigit() else None
    return page(
        request,
        "records/chapter.html",
        nav="records",
        title=f"{view['chapter']['title']} · Record book",
        selected_year=year,
        year_qs=f"?year={year}" if year else "",
        chapter=view["chapter"],
        chapter_template=view["template"],
        prev_chapter=view["prev"],
        next_chapter=view["next"],
        **view["context"],
    )


# --- B1 player anatomy (#96): game log + splits routes. ---


@app.get("/players/{player_id}/log", response_class=HTMLResponse)
def player_log(request: Request, player_id: str) -> HTMLResponse:
    data = _load_player(player_id, anatomy=False)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No player {player_id}.")
    selected = _selected_year(request)
    data["selected_year"] = selected
    data["shown_weeks"] = _filter_year(data["weeks"], selected)
    person = data["player"]
    title = person["player_name"] + " game log"
    return page(request, "player_log.html", nav="players", title=title, **data)


@app.get("/players/{player_id}/splits", response_class=HTMLResponse)
def player_splits(request: Request, player_id: str) -> HTMLResponse:
    data = _load_player(player_id, anatomy=False)
    if data is None:
        raise StarletteHTTPException(status_code=404, detail=f"No player {player_id}.")
    selected = _selected_year(request)
    data["selected_year"] = selected
    splits = data.get("splits") or {}
    rows = _filter_year(splits.get("rows") or [], selected)
    data["phase_rows"] = [row for row in rows if row.get("split_family") == "phase"]
    data["half_rows"] = [row for row in rows if row.get("split_family") == "half"]
    data["site_rows"] = _filter_year(splits.get("sites") or [], selected)
    data["opponent_rows"] = _filter_year(splits.get("opponents") or [], selected)
    person = data["player"]
    title = person["player_name"] + " splits"
    return page(request, "player_splits.html", nav="players", title=title, **data)


# --- D1 players split (#105) ---
# /players above renders the summary. Each full table is one A3 board, so the
# document and the bare fragment are the same template:
#   /boards/<name>      the page
#   /fragments/<name>   the bare section, for the inline upgrade
# Names, in index order: players-career-rankings, players-season-rankings,
# players-wire-season, players-wire-career, players-wire-unowned,
# players-counting-career, players-counting-season.
# Registered at the end of fragments._register_boards. The A3 paginated
# career log stays at /boards/players-career and is linked from the full
# career page. No second route table: a parallel /players/<board> path would
# fork the envelope era themes inherit.

# --- C1a era90 season family (#100). Modern page() is the else branch. ---
_legacy_page = page


def page(request: Request, name: str, *, nav: str, title: str, **context) -> HTMLResponse:
    if themes.resolve_theme(request) == "era90" and name in themes.ERA90_FAMILY:
        return themes.era90_family_document(request, name, nav=nav, title=title, context=context)
    return _legacy_page(request, name, nav=nav, title=title, **context)



# --- C2a era2010 (#101). Home, week, gamecenter, League, and My Team.
# Modern and era90 fall through. Season pages stay on the A2 dispatch.
# person_link reads the avatar_url global. Replace it after install so the
# boot fixture still sees the plain function, and live renders only resolve
# a sleeper avatar when the request's theme is era2010.
templates.env.globals["avatar_url"] = themes.era2010_avatar_url
templates.env.globals["era2010_aliases"] = tuple(
    themes.EraAlias(alias_id, pane, label) for alias_id, pane, label in themes.ERA2010_HASH_ALIASES
)


@app.middleware("http")
async def era2010_pages(request: Request, call_next):
    if request.method == "GET" and themes.resolve_theme(request) == "era2010":
        response = themes.era2010_dispatch(request)
        if response is not None:
            return themes.persist_theme(request, response)
    return await call_next(request)
