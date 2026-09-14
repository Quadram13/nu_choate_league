from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..paths import project_root
from . import queries

HUB_DIR = project_root() / "hub"
templates = Jinja2Templates(directory=str(HUB_DIR / "templates"))

app = FastAPI(title="Nu Choate League", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(HUB_DIR / "static")), name="static")


def page(request: Request, name: str, *, nav: str, title: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        name,
        {"nav": nav, "title": title, **context},
    )


@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> HTMLResponse:
    status = exc.status_code
    heading = "Not found" if status == 404 else "Hub unavailable"
    return templates.TemplateResponse(
        request,
        "error.html",
        {"nav": "", "title": heading, "status": status, "detail": exc.detail},
        status_code=status,
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    seasons = queries.list_seasons()
    year = queries.latest_scored_year()
    current = queries.season_row(year) if year is not None else None
    table = queries.standings(year) if year is not None else []
    return page(
        request,
        "home.html",
        nav="home",
        title="Nu Choate League",
        seasons=seasons,
        year=year,
        current=current,
        standings=table,
    )


@app.get("/seasons", response_class=HTMLResponse)
def seasons(request: Request) -> HTMLResponse:
    return page(
        request,
        "seasons.html",
        nav="seasons",
        title="Seasons",
        seasons=queries.list_seasons(),
    )


@app.get("/seasons/{year}", response_class=HTMLResponse)
def season(request: Request, year: int) -> HTMLResponse:
    current = queries.season_row(year)
    if current is None:
        raise StarletteHTTPException(status_code=404, detail=f"No season {year} in the warehouse.")
    return page(
        request,
        "season.html",
        nav="seasons",
        title=f"{year} season",
        current=current,
        standings=queries.standings(year),
        weeks=queries.matchups_by_week(year),
    )


@app.get("/members", response_class=HTMLResponse)
def members(request: Request) -> HTMLResponse:
    return page(
        request,
        "members.html",
        nav="members",
        title="All-time standings",
        career=queries.career(),
    )


@app.get("/members/{manager_id}", response_class=HTMLResponse)
def member(request: Request, manager_id: str) -> HTMLResponse:
    person = queries.career_one(manager_id)
    if person is None:
        raise StarletteHTTPException(status_code=404, detail=f"No manager {manager_id}.")
    return page(
        request,
        "member.html",
        nav="members",
        title=person["display_name"],
        person=person,
        finishes=queries.finishes(manager_id),
        h2h=queries.h2h_for(manager_id),
    )


@app.get("/records", response_class=HTMLResponse)
def records(request: Request) -> HTMLResponse:
    return page(
        request,
        "coming.html",
        nav="records",
        title="Record book",
        heading="Record book",
        note="High/low weeks, blowouts, and streaks are already in v_record_weeks, v_record_matchups, and v_streaks. This page is next after the spine.",
    )


@app.get("/luck", response_class=HTMLResponse)
def luck(request: Request) -> HTMLResponse:
    return page(
        request,
        "coming.html",
        nav="luck",
        title="Universes & luck",
        heading="Universes & luck",
        note="Always-H2H, always-median, all-play, and lucky weeks are already queryable. This page is Phase 2.",
    )


@app.get("/players", response_class=HTMLResponse)
def players(request: Request) -> HTMLResponse:
    return page(
        request,
        "coming.html",
        nav="players",
        title="Players",
        heading="Players",
        note="League career PF and VORP are already in v_player_career and v_vorp_season. This page is Phase 2.",
    )
