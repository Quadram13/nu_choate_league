from __future__ import annotations


def flavor_team(member_name: str | None, team_name: str | None) -> str | None:
    team = (team_name or "").strip()
    if not team:
        return None
    member = (member_name or "").strip()
    if member and team.casefold() == member.casefold():
        return None
    return team
