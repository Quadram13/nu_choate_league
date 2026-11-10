"""C2b era2010 pages: players, records, versus, and the remaining hub routes.

Modern and era90 never enter this module. A path that is not one of these
pages returns None so the existing route can answer, including its 404.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse

from . import queries
from .themes import (
    ERA2010_AVG_NOTE,
    FORMATTERS,
    _draft_board,
    _era2010_document,
    _era2010_identity,
    _moves_board,
    _plain_board,
    _short_name,
    era2010_modules,
)

_PLAYER_LOG = re.compile(r"^/players/([^/]+)/log$")
_PLAYER_SPLITS = re.compile(r"^/players/([^/]+)/splits$")
_PLAYER = re.compile(r"^/players/([^/]+)$")
_CHAPTER = re.compile(r"^/records/([^/]+)$")
_PAIR = re.compile(r"^/versus/([^/]+)/([^/]+)$")
_BOARD = re.compile(r"^/boards/([^/]+)$")
_TRADE = re.compile(r"^/seasons/(\d+)/trades/([^/]+)$")
_WIRE = re.compile(r"^/seasons/(\d+)/wire/([^/]+)$")
_SEASON_PAGE = re.compile(r"^/seasons/(\d+)/(moves|draft|marks|desk|scoring)$")

_SKIP = frozenset(
    {
        "manager_id",
        "player_id",
        "opponent_id",
        "left_id",
        "right_id",
        "matchup_id",
        "transaction_id",
        "hue",
        "hue_left",
        "hue_right",
        "kind_order",
        "anchor_chapters",
        "home_won",
        "away_won",
    }
)
_PRIORITY = (
    "display_name",
    "player_name",
    "manager_name",
    "owner_name",
    "left_name",
    "right_name",
    "name",
    "label",
    "champion",
    "year",
    "week",
    "position",
    "record",
    "span",
    "wins",
    "losses",
    "ties",
    "length",
    "points",
    "points_for",
    "points_against",
    "margin",
    "starter_points",
    "started_points",
    "starts",
    "games",
    "titles",
    "own_pct",
    "kind",
    "result",
)
_LEAD = (
    "points",
    "points_for",
    "starter_points",
    "started_points",
    "length",
    "weeks",
    "total",
    "margin",
    "starts",
    "games",
    "titles",
)
_LABELS = {
    "display_name": "Manager",
    "player_name": "Player",
    "manager_name": "Owner",
    "owner_name": "Owner",
    "points_for": "PF",
    "points_against": "PA",
    "starter_points": "PF",
    "started_points": "PF",
    "own_pct": "Own",
    "win_pct": "Pct",
    "left_name": "Left",
    "right_name": "Right",
}
_MARK_NOTE = (
    "Bold is the board's first row. Gold is that row's lead number, including ties. "
    "Italic is a current streak."
)


def c2b_response(request: Request, path: str) -> HTMLResponse | None:
    """Era2010 document for a C2b route, or None when this path is not ours."""
    route = _match(path)
    if route is None:
        return None
    conn = queries.connect()
    token = queries.bind_connection(conn)
    try:
        page = _handle(request, route)
        if page is None:
            return _not_found(request)
        return page
    finally:
        queries.unbind_connection(token)
        conn.close()


def _match(path: str) -> tuple[Any, ...] | None:
    if path == "/players":
        return ("players",)
    if path == "/records":
        return ("records",)
    if path == "/versus":
        return ("versus",)
    log = _PLAYER_LOG.match(path)
    if log:
        return ("log", log.group(1))
    splits = _PLAYER_SPLITS.match(path)
    if splits:
        return ("splits", splits.group(1))
    player = _PLAYER.match(path)
    if player:
        return ("player", player.group(1))
    chapter = _CHAPTER.match(path)
    if chapter:
        return ("chapter", chapter.group(1))
    pair = _PAIR.match(path)
    if pair:
        return ("pair", pair.group(1), pair.group(2))
    board = _BOARD.match(path)
    if board:
        return ("board", board.group(1))
    trade = _TRADE.match(path)
    if trade:
        return ("trade", int(trade.group(1)), trade.group(2))
    wire = _WIRE.match(path)
    if wire:
        return ("wire", int(wire.group(1)), wire.group(2))
    season_page = _SEASON_PAGE.match(path)
    if season_page:
        return ("season-page", int(season_page.group(1)), season_page.group(2))
    return None


def _handle(request: Request, route: tuple[Any, ...]) -> HTMLResponse | None:
    kind = route[0]
    if kind == "players":
        return _players(request)
    if kind == "player":
        return _player(request, str(route[1]), "profile")
    if kind == "log":
        return _player(request, str(route[1]), "log")
    if kind == "splits":
        return _player(request, str(route[1]), "splits")
    if kind == "records":
        return _records(request)
    if kind == "chapter":
        return _chapter(request, str(route[1]))
    if kind == "versus":
        return _versus(request)
    if kind == "pair":
        return _pair(request, str(route[1]), str(route[2]))
    if kind == "board":
        return _board(request, str(route[1]))
    if kind == "trade":
        return _trade(request, int(route[1]), str(route[2]))
    if kind == "wire":
        return _wire(request, int(route[1]), str(route[2]))
    if kind == "season-page":
        return _season_page(request, int(route[1]), str(route[2]))
    return None


def _not_found(request: Request) -> HTMLResponse:
    response = _doc(
        request,
        title="Not in the book",
        nav="home",
        template="era2010/missing.html",
    )
    response.status_code = 404
    return response


def _doc(
    request: Request,
    *,
    title: str,
    nav: str,
    template: str,
    year: int | None = None,
    context: Mapping[str, Any] | None = None,
    weeks: Sequence[int] = (),
) -> HTMLResponse:
    return _era2010_document(
        request,
        title=title,
        nav=nav,
        year=year,
        weeks=list(weeks),
        template=template,
        lead="era2010/league_lead.html",
        aside="era2010/league_aside.html",
        context=dict(context or {}),
    )


def _players(request: Request) -> HTMLResponse:
    summary = queries.players_summary()
    year = queries.latest_scored_year()
    modules = era2010_modules(request, year, "/players", ()) if year is not None else []
    career = summary["teasers"]["players-career-rankings"]["rows"]
    ids = [str(row["player_id"]) for row in career if row.get("player_id")]
    cards = queries.era2010_index_cards(ids)
    packed = []
    for row in career:
        extra = cards.get(str(row.get("player_id")), {})
        shown = dict(row)
        if shown.get("player_name"):
            shown["player_name"] = _short_name(str(shown["player_name"]))
        packed.append({"row": shown, "season": extra.get("season"), "weeks": extra.get("weeks") or []})
    boards = []
    for name in summary["board_order"]:
        teaser = summary["teasers"][name]
        boards.append(
            {
                "label": teaser["label"],
                "total": teaser["total"],
                "href": teaser["board_href"],
                "fragment": teaser["fragment_href"],
            }
        )
    return _doc(
        request,
        title="Players",
        nav="players",
        template="era2010/players_index.html",
        year=year,
        context={
            "year": year,
            "modules": modules,
            "cards": packed,
            "boards": boards,
            "avg_note": ERA2010_AVG_NOTE if modules else None,
        },
    )


def _anatomy_mark(kind: str) -> str:
    if kind == "record":
        return "is-record"
    if kind == "active":
        return "is-active-leader"
    if kind == "leader":
        return "is-leader"
    return ""


def _player(request: Request, player_id: str, mode: str) -> HTMLResponse | None:
    data = queries.player_page(player_id)
    if data is None:
        return None
    person = data["player"]
    full_name = str(person.get("player_name") or player_id)
    name = _short_name(full_name)
    anatomy = queries.player_anatomy(player_id) if mode == "profile" else {}
    season_marks = anatomy.get("summary_season") or {}
    season_rows: list[dict[str, Any]] = []
    for row in data["seasons"]:
        year = int(row["year"])
        marks = dict(season_marks.get(year) or {})
        cell_marks = {
            key: _anatomy_mark(str(kind))
            for key, kind in marks.items()
            if _anatomy_mark(str(kind))
        }
        if "started_points" in cell_marks and "points" not in cell_marks:
            cell_marks["points"] = cell_marks["started_points"]
        season_rows.append(
            {
                "year": year,
                "starts": int(row.get("starts") or 0),
                "points": row.get("started_points"),
                "owner": row.get("owner_name") or "",
                "own_pct": row.get("own_pct"),
                "_href": {
                    "year": f"/seasons/{year}",
                    "owner": f"/members/{row['manager_id']}" if row.get("manager_id") else "",
                },
                "_mark": cell_marks,
            }
        )
    weeks = list(data["weeks"])
    if mode == "log":
        selected = request.query_params.get("year")
        if selected and selected.isdigit():
            weeks = [row for row in weeks if int(row["year"]) == int(selected)]
        shown = weeks
        title = f"{name} game log"
        template = "era2010/sections.html"
    elif mode == "splits":
        shown = []
        title = f"{name} splits"
        template = "era2010/sections.html"
    else:
        latest = max((int(row["year"]) for row in weeks), default=None)
        shown = [row for row in weeks if latest is not None and int(row["year"]) == latest][-6:]
        title = name
        template = "era2010/player.html"
    week_rows = []
    for row in shown:
        week_rows.append(
            {
                "year": int(row["year"]),
                "week": int(row["week"]),
                "points": row.get("points"),
                "started": "yes" if row.get("started") else "no",
                "owner": row.get("manager_name") or "",
                "_href": {
                    "week": f"/seasons/{int(row['year'])}/week/{int(row['week'])}",
                    "owner": f"/members/{row['manager_id']}" if row.get("manager_id") else "",
                },
                "_mark": {},
            }
        )
    stints = []
    for row in data.get("stints") or []:
        stints.append(
            {
                "span": row.get("span") or "",
                "owner": row.get("manager_name") or "FA",
                "weeks": row.get("weeks"),
                "starts": row.get("starts"),
                "points": row.get("points"),
                "how": row.get("acquisition_label") or "",
                "_href": {
                    "owner": f"/members/{row['manager_id']}" if row.get("manager_id") else "",
                    "how": row.get("href") or "",
                },
                "_mark": {},
            }
        )
    sections = []
    if mode != "splits":
        if mode == "profile":
            career_marks: dict[str, str] = {}
            for key, kind in (anatomy.get("summary_career") or {}).items():
                mark = _anatomy_mark(str(kind))
                if not mark:
                    continue
                target = {"started_points": "starter_points", "points": "fantasy"}.get(str(key), str(key))
                career_marks[target] = mark
            sections.append(
                _plain_board(
                    "Career",
                    (
                        ("starts", "Starts", True, "int"),
                        ("starter_points", "Starter PF", True, "num2"),
                        ("fantasy", "Fantasy", True, "num2"),
                    ),
                    [
                        {
                            "starts": person.get("starts"),
                            "starter_points": person.get("starter_points"),
                            "fantasy": anatomy.get("fantasy_total"),
                            "_href": {},
                            "_mark": career_marks,
                        }
                    ],
                    "Gold is the career record. Italic is the lead among active players. Bold on a season row is a season lead.",
                )
            )
        if season_rows and mode == "profile":
            sections.append(
                _plain_board(
                    "Seasons",
                    (
                        ("year", "Year", True, "int"),
                        ("starts", "Starts", True, "int"),
                        ("points", "PF", True, "num2"),
                        ("owner", "Owner", False, "text"),
                        ("own_pct", "Own", True, "num3"),
                    ),
                    season_rows,
                    "PF is started points. Bold, gold, and italic are the profile leader marks.",
                )
            )
        if week_rows:
            sections.append(
                _plain_board(
                    "Weeks" if mode == "log" else "Recent weeks",
                    (
                        ("year", "Year", True, "int"),
                        ("week", "Wk", True, "int"),
                        ("points", "PTS", True, "num2"),
                        ("started", "Started", False, "text"),
                        ("owner", "Owner", False, "text"),
                    ),
                    week_rows,
                    "Recent weeks are the latest scored season. The game log lists every stored week.",
                )
            )
        if stints and mode == "profile":
            sections.append(
                _plain_board(
                    "Ownership",
                    (
                        ("span", "Span", False, "text"),
                        ("owner", "Owner", False, "text"),
                        ("weeks", "Wks", True, "int"),
                        ("starts", "Starts", True, "int"),
                        ("points", "PTS", True, "num2"),
                        ("how", "How", False, "text"),
                    ),
                    stints,
                    "Rostered runs, then unowned runs. How links to the add when one is stored.",
                )
            )
    else:
        sections = _sections(data.get("splits") or {}, "Splits")
    years = sorted({int(row["year"]) for row in data["weeks"]}, reverse=True)
    return _doc(
        request,
        title=title,
        nav="players",
        template=template,
        year=queries.latest_scored_year(),
        context={
            "player_name": name,
            "position": person.get("position") or "",
            "player_id": player_id,
            "sections": sections,
            "years": years,
            "mode": mode,
        },
    )


def _records(request: Request) -> HTMLResponse:
    page = queries.records_index_page()
    holders = []
    high = None
    for row in page.get("holders") or []:
        total = int(row.get("total") or 0)
        high = total if high is None else max(high, total)
    for row in page.get("holders") or []:
        total = int(row.get("total") or 0)
        holders.append(
            {
                "name": row.get("display_name") or "",
                "total": total,
                "href": f"/members/{row['manager_id']}",
                "leader": high is not None and total == high and total > 0,
            }
        )
    chapters = []
    for chapter in page.get("chapters") or []:
        chapters.append(
            {
                "title": chapter.get("title") or "",
                "taste": chapter.get("taste") or "",
                "href": f"/records/{chapter['slug']}",
                "anchors": chapter.get("anchors") or [],
            }
        )
    return _doc(
        request,
        title="Record book",
        nav="records",
        template="era2010/records_index.html",
        year=queries.latest_scored_year(),
        context={"holders": holders, "chapters": chapters},
    )


def _chapter(request: Request, slug: str) -> HTMLResponse | None:
    view = queries.record_chapter_view(slug)
    if view is None:
        return None
    chapter = view["chapter"]
    sections = _sections(view["context"], "")
    anchors = list(chapter.get("anchors") or [])
    for index, section in enumerate(sections):
        if index < len(anchors):
            section["anchor"] = anchors[index]["id"]
        elif section.get("key"):
            section["anchor"] = str(section["key"])
    return _doc(
        request,
        title=str(chapter.get("title") or "Records"),
        nav="records",
        template="era2010/sections.html",
        year=queries.latest_scored_year(),
        context={
            "sections": sections,
            "anchors": anchors,
            "prev": view.get("prev"),
            "next": view.get("next"),
            "chapter_href": "/records",
        },
    )


def _face(display: object, manager_id: object, names: Mapping[str, str]) -> dict[str, Any]:
    key = "" if manager_id is None else str(manager_id)
    return dict(_era2010_identity(display, names.get(key), manager_id))


def _versus(request: Request) -> HTMLResponse:
    grid = queries.versus_grid()
    names = queries.era2010_latest_franchises()
    managers = []
    for row in grid["managers"]:
        managers.append(_face(row.get("display_name"), row.get("manager_id"), names))
    rows = []
    for line in grid["grid"]:
        manager = line["manager"]
        identity = _face(manager.get("display_name"), manager.get("manager_id"), names)
        cells = []
        for cell in line["cells"]:
            if cell.get("self"):
                cells.append({"self": True})
                continue
            wins = int(cell.get("wins") or 0)
            losses = int(cell.get("losses") or 0)
            cells.append(
                {
                    "self": False,
                    "record": cell.get("record") or "—",
                    "href": cell.get("href") or "",
                    "leader": wins > losses,
                }
            )
        rows.append({"manager": identity, "cells": cells})
    notes = []
    for note in grid.get("notes") or []:
        if isinstance(note, str):
            notes.append(note)
        elif isinstance(note, Mapping):
            text = note.get("text") or note.get("label") or ""
            if text:
                notes.append(str(text))
    return _doc(
        request,
        title="Versus",
        nav="versus",
        template="era2010/versus.html",
        year=queries.latest_scored_year(),
        context={"managers": managers, "rows": rows, "notes": notes},
    )


def _pair(request: Request, left_id: str, right_id: str) -> HTMLResponse | None:
    data = queries.versus_pair(left_id, right_id)
    if data is None:
        return None
    left = data["left"]
    right = data["right"]
    names = queries.era2010_latest_franchises()
    left_id_value = str(left.get("manager_id") or left_id)
    right_id_value = str(right.get("manager_id") or right_id)
    left_face = _face(left.get("display_name"), left_id_value, names)
    right_face = _face(right.get("display_name"), right_id_value, names)
    cards = []
    for game in data["games"]:
        left_won = game.get("result") == "win"
        right_won = game.get("result") == "loss"
        cards.append(
            {
                "href": game.get("href") or "",
                "label": f"{int(game['year'])} W{int(game['week'])} {game.get('kind_label') or ''}".strip(),
                "home": {
                    "franchise": left_face["franchise"],
                    "owner": left_face["owner"],
                    "avatar": left_face["avatar"],
                    "href": left_face["href"],
                    "score": FORMATTERS["num2"](game.get("points"), "era2010"),
                    "won": left_won,
                    "cells": [],
                    "bench": [],
                },
                "away": {
                    "franchise": right_face["franchise"],
                    "owner": right_face["owner"],
                    "avatar": right_face["avatar"],
                    "href": right_face["href"],
                    "score": FORMATTERS["num2"](game.get("opp_points"), "era2010"),
                    "won": right_won,
                    "cells": [],
                    "bench": [],
                },
            }
        )
    series = data.get("series") or {}
    record = ""
    if series:
        record = (
            f"{int(series.get('regular_wins') or 0)}-"
            f"{int(series.get('regular_losses') or 0)}-"
            f"{int(series.get('regular_ties') or 0)}"
        )
    return _doc(
        request,
        title=f"{left_face['franchise']} vs {right_face['franchise']}",
        nav="versus",
        template="era2010/versus_pair.html",
        year=queries.latest_scored_year(),
        context={
            "left": left_face,
            "right": right_face,
            "record": record,
            "cards": cards,
            "streak": data.get("streak"),
        },
    )


def _board(request: Request, name: str) -> HTMLResponse | None:
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from .fragments import board_by_name, render_fragment

    try:
        spec = board_by_name(name)
    except StarletteHTTPException:
        return None
    html = render_fragment(request, name)
    return _doc(
        request,
        title=spec.title,
        nav=spec.nav,
        template="era2010/board_wrap.html",
        year=queries.latest_scored_year(),
        context={"fragment_html": html, "back": "/players"},
    )


def _trade(request: Request, year: int, transaction_id: str) -> HTMLResponse | None:
    if queries.season_row(year) is None:
        return None
    data = queries.trade_page(year, transaction_id)
    if data is None:
        return None
    sections = []
    for face in ("left", "right"):
        side = data[face]
        rows = []
        for player in side.get("players") or []:
            rows.append(
                {
                    "player": _short_name(str(player.get("player_name") or "")),
                    "position": player.get("position") or "",
                    "starts": player.get("ros_starts"),
                    "points": player.get("ros_starter"),
                    "_href": {"player": f"/players/{player['player_id']}" if player.get("player_id") else ""},
                    "_mark": {},
                }
            )
        identity = _era2010_identity(side.get("name"), side.get("team"), side.get("id"))
        sections.append(
            _plain_board(
                str(identity["franchise"]),
                (
                    ("player", "Player", False, "text"),
                    ("position", "Pos", False, "text"),
                    ("starts", "Starts", True, "int"),
                    ("points", "ROS", True, "num2"),
                ),
                rows,
                "ROS is starter points after the trade week. Nothing here is a projection.",
            )
        )
    return _doc(
        request,
        title=f"{data['left']['name']} vs {data['right']['name']}",
        nav="seasons",
        year=year,
        weeks=queries.scored_weeks(year),
        template="era2010/sections.html",
        context={"sections": sections, "anchors": [], "prev": None, "next": None, "chapter_href": f"/seasons/{year}"},
    )


def _wire(request: Request, year: int, transaction_id: str) -> HTMLResponse | None:
    if queries.season_row(year) is None:
        return None
    claim = queries.wire_page(year, transaction_id)
    if claim is None:
        return None
    row = {
        "player": _short_name(str(claim.get("player_name") or "")),
        "position": claim.get("position") or "",
        "owner": claim.get("manager_name") or "",
        "week": claim.get("week"),
        "bid": claim.get("bid"),
        "starts": claim.get("league_starts") if claim.get("league_starts") is not None else claim.get("ros_starts"),
        "points": claim.get("league_ros") if claim.get("league_ros") is not None else claim.get("ros_starter"),
        "_href": {
            "player": f"/players/{claim['player_id']}" if claim.get("player_id") else "",
            "owner": f"/members/{claim['manager_id']}" if claim.get("manager_id") else "",
            "week": f"/seasons/{year}/week/{int(claim['week'])}" if claim.get("week") is not None else "",
        },
        "_mark": {},
    }
    board = _plain_board(
        "Claim",
        (
            ("player", "Player", False, "text"),
            ("position", "Pos", False, "text"),
            ("owner", "Owner", False, "text"),
            ("week", "Wk", True, "int"),
            ("bid", "Bid", True, "int"),
            ("starts", "Starts", True, "int"),
            ("points", "ROS", True, "num2"),
        ),
        [row],
        "ROS and starts are the stored rest-of-season line. Bid is blank when the claim was not FAAB.",
    )
    return _doc(
        request,
        title=f"{claim.get('player_name') or 'Claim'} · {year}",
        nav="seasons",
        year=year,
        weeks=queries.scored_weeks(year),
        template="era2010/sections.html",
        context={"sections": [board], "anchors": [], "prev": None, "next": None, "chapter_href": f"/seasons/{year}"},
    )


def _moves_log_board(year: int) -> dict[str, Any] | None:
    data = queries.moves_log(year)
    if not data:
        return None
    rows: list[dict[str, Any]] = []
    for move in data.get("moves") or []:
        href = move.get("href") or ""
        week = move.get("week")
        for direction in ("adds", "drops"):
            for item in move.get(direction) or []:
                rows.append(
                    {
                        "week": week,
                        "type": move.get("type") or "",
                        "direction": "add" if direction == "adds" else "drop",
                        "player": _short_name(str(item.get("player_name") or "")),
                        "position": item.get("position") or "",
                        "manager": item.get("manager_name") or "",
                        "bid": item.get("bid"),
                        "_href": {
                            "week": f"/seasons/{year}/week/{int(week)}" if week is not None else "",
                            "player": f"/players/{item['player_id']}" if item.get("player_id") else "",
                            "manager": f"/members/{item['manager_id']}" if item.get("manager_id") else "",
                            "type": href,
                        },
                        "_mark": {},
                    }
                )
    if not rows:
        return None
    return _plain_board(
        "Waiver and trade log",
        (
            ("week", "Wk", True, "int"),
            ("type", "Type", False, "text"),
            ("direction", "Dir", False, "text"),
            ("player", "Player", False, "text"),
            ("position", "Pos", False, "text"),
            ("manager", "Manager", False, "text"),
            ("bid", "Bid", True, "int"),
        ),
        rows,
        "Each stored add and drop. Type links to the trade or the claim. Bid is blank when the move was not FAAB.",
    )


def _season_page(request: Request, year: int, name: str) -> HTMLResponse | None:
    if queries.season_row(year) is None:
        return None
    if name == "moves":
        board = _moves_board(year, "era2010")
        sections = [board] if board else []
        log = _moves_log_board(year)
        if log is not None:
            sections.append(log)
    elif name == "draft":
        board = _draft_board(year, "era2010")
        sections = [board] if board else []
    elif name == "marks":
        sections = _sections(queries.week_marks_season(year), "")
    elif name == "desk":
        data = queries.schedule_desk_page(year)
        sections = _sections(data, "") if data else []
    else:
        data = queries.scoring_sheet(year)
        sections = _sections(data, "") if data else []
    titles = {
        "moves": f"{year} moves",
        "draft": f"{year} draft",
        "marks": f"{year} distinctions",
        "desk": f"{year} schedule desk",
        "scoring": f"{year} scoring",
    }
    return _doc(
        request,
        title=titles[name],
        nav="seasons",
        year=year,
        weeks=queries.scored_weeks(year),
        template="era2010/sections.html",
        context={
            "sections": sections,
            "anchors": [],
            "prev": None,
            "next": None,
            "chapter_href": f"/seasons/{year}",
        },
    )


def _is_scalar(value: object) -> bool:
    if value is None or isinstance(value, (str, int, float, Decimal, bool)):
        return True
    return hasattr(value, "isoformat") and not isinstance(value, (dict, list, tuple))


def _text(value: object) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (Decimal, float)):
        return str(FORMATTERS["num2"](value, "era2010"))
    if hasattr(value, "isoformat") and not isinstance(value, (str, int, float, Decimal)):
        return str(value.isoformat())[:10]
    return str(value)


def _heading(key: str) -> str:
    return _LABELS.get(key, key.replace("_", " "))


def _row_list(value: object) -> list[Mapping[str, Any]] | None:
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(item, Mapping) for item in value[:8]):
        return None
    sample = value[:8]
    if not any(_is_scalar(cell) for item in sample for cell in item.values()):
        return None
    return [item for item in value if isinstance(item, Mapping)]


def _sections(value: object, caption: str, depth: int = 0) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    _walk(value, caption, depth, found)
    return found


def _walk(value: object, caption: str, depth: int, found: list[dict[str, Any]]) -> None:
    if depth > 3 or len(found) >= 24:
        return
    rows = _row_list(value)
    if rows is not None:
        board = _board_from_rows(caption or "Board", rows)
        if board is not None:
            found.append(board)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _SKIP or key.endswith("_id"):
                continue
            title = caption if not str(key) else _heading(str(key))
            _walk(item, title, depth + 1, found)


def _board_from_rows(caption: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    present: list[str] = []
    for key in _PRIORITY:
        if any(key in row and _is_scalar(row.get(key)) for row in rows[:12]):
            present.append(key)
    if len(present) < 12:
        for row in rows[:12]:
            for key in row:
                if key in present or key in _SKIP or str(key).endswith("_id"):
                    continue
                if not _is_scalar(row.get(key)):
                    continue
                present.append(str(key))
                if len(present) >= 12:
                    break
            if len(present) >= 12:
                break
    if not present:
        return None
    lead = next((key for key in _LEAD if key in present), None)
    lead_value = rows[0].get(lead) if lead and rows else None
    body: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        marks: dict[str, str] = {}
        if index == 0 and lead and lead_value is not None:
            name_key = next((key for key in present if key in _PRIORITY[:8]), present[0])
            marks[name_key] = "is-leader"
        if lead and lead_value is not None and row.get(lead) == lead_value:
            marks[lead] = "is-record"
        if row.get("is_current"):
            name_key = next((key for key in present if "name" in key), present[0])
            marks[name_key] = "is-active-leader"
        hrefs: dict[str, str] = {}
        manager_id = row.get("manager_id")
        player_id = row.get("player_id")
        if manager_id:
            for key in present:
                if key in {"display_name", "manager_name", "owner_name", "left_name", "right_name"}:
                    hrefs[key] = f"/members/{manager_id}"
        if player_id:
            for key in present:
                if key in {"player_name", "name"}:
                    hrefs[key] = f"/players/{player_id}"
        if row.get("year") is not None and row.get("week") is not None and "week" in present:
            hrefs["week"] = f"/seasons/{int(row['year'])}/week/{int(row['week'])}"
        if isinstance(row.get("href"), str) and row.get("href"):
            hrefs[present[0]] = str(row["href"])
        packed = {}
        for key in present:
            value = row.get(key)
            if key in {"player_name", "player"} and isinstance(value, str):
                value = _short_name(value)
            packed[key] = value
        packed["_href"] = hrefs
        packed["_mark"] = marks
        body.append(packed)
    columns = tuple(
        (key, _heading(key), _column_numeric(rows, key), _formatter(rows, key))
        for key in present
    )
    board = _plain_board(caption, columns, body, _MARK_NOTE)
    board["key"] = caption
    return board


def _column_numeric(rows: Sequence[Mapping[str, Any]], key: str) -> bool:
    for row in rows[:8]:
        value = row.get(key)
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            return True
    return False


def _formatter(rows: Sequence[Mapping[str, Any]], key: str) -> str:
    if not _column_numeric(rows, key):
        return "text"
    for row in rows[:8]:
        value = row.get(key)
        if isinstance(value, (float, Decimal)) and not isinstance(value, bool):
            return "num2"
    return "int"
