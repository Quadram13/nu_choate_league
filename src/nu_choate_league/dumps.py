from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import DumpOwner, DumpPlayer, Platform, Season
from .paths import data_dir


class DumpError(FileNotFoundError):
    pass


def season_dir(season: Season, root: Path | None = None) -> Path:
    return (root or data_dir()) / season.platform.value / str(season.year)


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise DumpError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def dump_owners(season: Season, root: Path | None = None) -> list[DumpOwner]:
    folder = season_dir(season, root)
    if not folder.is_dir():
        raise DumpError(f"Missing dump directory {folder}")
    if season.platform is Platform.ESPN:
        return _espn_owners(season, folder)
    return _sleeper_owners(season, folder)


def _espn_owners(season: Season, folder: Path) -> list[DumpOwner]:
    league = load_json(folder / "league.json")
    owners: list[DumpOwner] = []
    for member in league.get("members") or []:
        member_id = str(member.get("id") or "")
        if not member_id:
            continue
        first = str(member.get("firstName") or "").strip()
        last = str(member.get("lastName") or "").strip()
        display = str(member.get("displayName") or "").strip()
        label = " ".join(part for part in (first, last) if part) or display or member_id
        owners.append(
            DumpOwner(
                year=season.year,
                platform=Platform.ESPN,
                platform_id=member_id,
                label=label,
            )
        )
    return owners


def _sleeper_owners(season: Season, folder: Path) -> list[DumpOwner]:
    users = load_json(folder / "users.json")
    if not isinstance(users, list):
        raise DumpError(f"{folder / 'users.json'} must be a list")
    owners: list[DumpOwner] = []
    for user in users:
        user_id = str(user.get("user_id") or "")
        if not user_id:
            continue
        display = str(user.get("display_name") or "").strip()
        meta = user.get("metadata") or {}
        team = str(meta.get("team_name") or "").strip()
        label = display or team or user_id
        owners.append(
            DumpOwner(
                year=season.year,
                platform=Platform.SLEEPER,
                platform_id=user_id,
                label=label,
            )
        )
    return owners


ESPN_POSITIONS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}
SKIP_SLEEPER_IDS = {"", "0", "None", "null"}


def dump_players(season: Season, root: Path | None = None) -> list[DumpPlayer]:
    folder = season_dir(season, root)
    if not folder.is_dir():
        raise DumpError(f"Missing dump directory {folder}")
    if season.platform is Platform.ESPN:
        return list(_espn_players(season, folder).values())
    return list(_sleeper_players(season, folder).values())


def _espn_players(season: Season, folder: Path) -> dict[str, DumpPlayer]:
    found: dict[int, DumpPlayer] = {}

    def remember(
        player_id: int,
        *,
        name: str = "",
        position_id: object = None,
    ) -> None:
        if player_id == 0:
            return
        position = ESPN_POSITIONS.get(int(position_id)) if isinstance(position_id, int) else None
        current = found.get(player_id)
        if current is None:
            found[player_id] = DumpPlayer(
                platform=Platform.ESPN,
                platform_id=str(player_id),
                display_name=name,
                position=position,
                years=[season.year],
            )
            return
        if name and not current.display_name:
            current.display_name = name
        if position and not current.position:
            current.position = position

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            player = node.get("player") if isinstance(node.get("player"), dict) else None
            player_id = node.get("playerId")
            if not isinstance(player_id, int) and player is not None:
                player_id = player.get("id")
            inner_id = node.get("id") if "fullName" in node or "defaultPositionId" in node else None
            if isinstance(player_id, int):
                remember(
                    player_id,
                    name=str((player or {}).get("fullName") or node.get("fullName") or ""),
                    position_id=(player or {}).get("defaultPositionId", node.get("defaultPositionId")),
                )
            if isinstance(inner_id, int) and inner_id != player_id:
                remember(
                    inner_id,
                    name=str(node.get("fullName") or ""),
                    position_id=node.get("defaultPositionId"),
                )
            if player is not None:
                nested_id = player.get("id")
                if isinstance(nested_id, int):
                    remember(
                        nested_id,
                        name=str(player.get("fullName") or ""),
                        position_id=player.get("defaultPositionId"),
                    )
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for relative in ("league.json", "draft.json"):
        path = folder / relative
        if path.is_file():
            walk(load_json(path))
    weeks = folder / "weeks"
    if weeks.is_dir():
        for path in weeks.rglob("*.json"):
            walk(load_json(path))
    cards = folder / "player_cards"
    if cards.is_dir():
        for path in cards.glob("*.json"):
            walk(load_json(path))
    names_path = folder / "pro_players.json"
    if names_path.is_file():
        pool = load_json(names_path)
        if isinstance(pool, list):
            for entry in pool:
                if not isinstance(entry, dict):
                    continue
                player_id = entry.get("id")
                if not isinstance(player_id, int) or player_id not in found:
                    continue
                remember(
                    player_id,
                    name=str(entry.get("fullName") or ""),
                    position_id=entry.get("defaultPositionId"),
                )
    return {player.platform_id: player for player in found.values()}


def _sleeper_players(season: Season, folder: Path) -> dict[str, DumpPlayer]:
    found: dict[str, DumpPlayer] = {}

    def remember(player_id: object, name: str = "") -> None:
        key = str(player_id or "").strip()
        if key in SKIP_SLEEPER_IDS:
            return
        current = found.get(key)
        if current is None:
            found[key] = DumpPlayer(
                platform=Platform.SLEEPER,
                platform_id=key,
                display_name=name,
                years=[season.year],
            )
        elif name and not current.display_name:
            current.display_name = name

    rosters = load_json(folder / "rosters.json")
    if isinstance(rosters, list):
        for roster in rosters:
            for player_id in roster.get("players") or []:
                remember(player_id)
            for player_id in roster.get("starters") or []:
                remember(player_id)
    weeks = folder / "weeks"
    if weeks.is_dir():
        for path in weeks.glob("*/matchups.json"):
            matchups = load_json(path)
            if not isinstance(matchups, list):
                continue
            for matchup in matchups:
                for player_id in matchup.get("players") or []:
                    remember(player_id)
                for player_id in matchup.get("starters") or []:
                    remember(player_id)
                for player_id in matchup.get("players_points") or {}:
                    remember(player_id)
        for path in weeks.glob("*/transactions.json"):
            txns = load_json(path)
            if not isinstance(txns, list):
                continue
            for txn in txns:
                for player_id in txn.get("adds") or {}:
                    remember(player_id)
                for player_id in txn.get("drops") or {}:
                    remember(player_id)
    picks_path = folder / "drafts" / "picks.json"
    if picks_path.is_file():
        picks = load_json(picks_path)
        if isinstance(picks, list):
            for pick in picks:
                meta = pick.get("metadata") or {}
                first = str(meta.get("first_name") or "").strip()
                last = str(meta.get("last_name") or "").strip()
                name = " ".join(part for part in (first, last) if part)
                remember(pick.get("player_id"), name)
    return found
