from __future__ import annotations

import hashlib


def flavor_team(member_name: str | None, team_name: str | None) -> str | None:
    team = (team_name or "").strip()
    if not team:
        return None
    member = (member_name or "").strip()
    if member and team.casefold() == member.casefold():
        return None
    return team


def manager_hue(manager_id: str | None) -> int | None:
    if not manager_id:
        return None
    digest = hashlib.md5(manager_id.encode("utf-8"), usedforsecurity=False).digest()
    return int.from_bytes(digest[:2], "big") % 360
