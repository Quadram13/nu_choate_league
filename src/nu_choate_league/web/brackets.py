from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..paths import data_dir
from .names import flavor_team


def round_names(weeks: list[int], *, championship: bool) -> dict[int, str]:
    if not weeks:
        return {}
    if championship:
        if len(weeks) == 1:
            return {weeks[0]: "Championship"}
        if len(weeks) == 2:
            return {weeks[0]: "Semifinals", weeks[1]: "Championship"}
        names = {weeks[0]: "First round", weeks[-1]: "Championship"}
        for week in weeks[1:-1]:
            names[week] = "Semifinals"
        return names
    names = {week: f"Round {index}" for index, week in enumerate(weeks, start=1)}
    if len(weeks) > 1:
        names[weeks[-1]] = "Final"
    return names


def sleeper_tree(
    rows: list[dict[str, Any]],
    roster: dict[int, dict[str, Any]],
    games: list[dict[str, Any]],
    start_week: int,
    *,
    championship: bool,
) -> dict[str, Any] | None:
    if not rows:
        return None
    min_r = min(int(row["r"]) for row in rows if row.get("r") is not None)
    title = [row for row in rows if row.get("p") in (None, 1)]
    extra = [row for row in rows if row.get("p") not in (None, 1)]
    by_round: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(title, key=lambda item: (int(item["r"]), int(item["m"]))):
        by_round[int(row["r"])].append(_sleeper_match(row, roster, games, start_week, min_r))
    if not by_round:
        return None
    weeks = [start_week + (round_no - min_r) for round_no in sorted(by_round)]
    labels = round_names(weeks, championship=championship)
    rounds = []
    for round_no in sorted(by_round):
        week = start_week + (round_no - min_r)
        rounds.append({"week": week, "label": labels[week], "matches": by_round[round_no]})
    return {
        "kind": "tree",
        "rounds": rounds,
        "placements": [
            _sleeper_match(row, roster, games, start_week, min_r, place=True)
            for row in sorted(extra, key=lambda item: int(item.get("p") or 99))
        ],
    }


def espn_winners_tree(games: list[dict[str, Any]]) -> dict[str, Any] | None:
    playoff = [game for game in games if game["kind"] == "playoff"]
    if not playoff:
        return None
    by_week: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for game in playoff:
        by_week[int(game["week"])].append(_db_match(game))
    weeks = sorted(by_week)
    for index in range(len(weeks) - 1, 0, -1):
        by_week[weeks[index - 1]] = _align_to_later(
            by_week[weeks[index - 1]], by_week[weeks[index]]
        )
    labels = round_names(weeks, championship=True)
    return {
        "kind": "tree",
        "rounds": [
            {"week": week, "label": labels[week], "matches": by_week[week]}
            for week in weeks
        ],
        "placements": [],
    }


def espn_consolation_ladder(games: list[dict[str, Any]]) -> dict[str, Any] | None:
    consolation = [game for game in games if game["kind"] == "consolation"]
    if not consolation:
        return None
    by_week: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for game in consolation:
        by_week[int(game["week"])].append(_db_match(game))
    weeks = sorted(by_week)
    labels = round_names(weeks, championship=False)
    return {
        "kind": "ladder",
        "rounds": [
            {"week": week, "label": labels[week], "matches": by_week[week]}
            for week in weeks
        ],
        "placements": [],
    }


def load_sleeper_bracket(year: int, name: str) -> list[dict[str, Any]]:
    path = data_dir() / "sleeper" / str(year) / name
    return _read_json_list(path)


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _sleeper_match(
    row: dict[str, Any],
    roster: dict[int, dict[str, Any]],
    games: list[dict[str, Any]],
    start_week: int,
    min_r: int,
    *,
    place: bool = False,
) -> dict[str, Any]:
    week = start_week + (int(row["r"]) - min_r)
    home = _roster_side(roster, row.get("t1"))
    away = _roster_side(roster, row.get("t2"))
    scored = _find_game(games, home["id"] if home else None, away["id"] if away else None, week)
    place_no = int(row["p"]) if row.get("p") is not None else None
    match = scored or {
        "week": week,
        "home_id": home["id"] if home else None,
        "home_name": home["name"] if home else "Bye",
        "home_team": home.get("team") if home else None,
        "home_points": None,
        "away_id": away["id"] if away else None,
        "away_name": away["name"] if away else "Bye",
        "away_team": away.get("team") if away else None,
        "away_points": None,
        "winner_id": None,
    }
    match["place"] = place_no
    match["place_label"] = _place_label(place_no) if place else None
    return match


def _roster_side(roster: dict[int, dict[str, Any]], roster_id: Any) -> dict[str, Any] | None:
    if roster_id is None:
        return None
    return roster.get(int(roster_id))


def _find_game(
    games: list[dict[str, Any]], home_id: str | None, away_id: str | None, week: int
) -> dict[str, Any] | None:
    if not home_id or not away_id:
        return None
    want = {home_id, away_id}
    for game in games:
        if int(game["week"]) != week:
            continue
        got = {game["home_manager_id"], game["away_manager_id"]}
        if got == want:
            return _db_match(game)
    return None


def _db_match(game: dict[str, Any]) -> dict[str, Any]:
    home_id = game["home_manager_id"]
    away_id = game["away_manager_id"]
    home_pts = game["home_points"]
    away_pts = game["away_points"]
    winner_id = None
    if home_pts is not None and away_pts is not None:
        if home_pts > away_pts:
            winner_id = home_id
        elif away_pts > home_pts:
            winner_id = away_id
    home_name = game["home_name"] or game.get("home_team_name")
    away_name = game["away_name"] or game.get("away_team_name")
    return {
        "id": game.get("id"),
        "week": int(game["week"]),
        "home_id": home_id,
        "home_name": home_name,
        "home_team": flavor_team(home_name, game.get("home_team_name")),
        "home_points": home_pts,
        "away_id": away_id,
        "away_name": away_name,
        "away_team": flavor_team(away_name, game.get("away_team_name")),
        "away_points": away_pts,
        "winner_id": winner_id,
        "place": None,
        "place_label": None,
    }


def _align_to_later(
    earlier: list[dict[str, Any]], later: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if len(later) != 1 or len(earlier) != 2:
        return earlier
    finalists = [later[0]["home_id"], later[0]["away_id"]]
    aligned: list[dict[str, Any]] = []
    used: set[int] = set()
    for finalist in finalists:
        for index, game in enumerate(earlier):
            if index in used:
                continue
            if game["winner_id"] == finalist or finalist in {game["home_id"], game["away_id"]}:
                aligned.append(game)
                used.add(index)
                break
    for index, game in enumerate(earlier):
        if index not in used:
            aligned.append(game)
    return aligned


def _place_label(place: int | None) -> str | None:
    if place == 3:
        return "3rd place"
    if place == 5:
        return "5th place"
    if place is None:
        return None
    return f"{place}th place"
