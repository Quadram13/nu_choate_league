from __future__ import annotations

import json
from functools import lru_cache

from ..catalog import load_managers
from ..paths import data_dir

SLEEPER_HEADSHOT = "https://sleepercdn.com/content/nfl/players/thumb/{id}.jpg"
SLEEPER_LOGO = "https://sleepercdn.com/images/team_logos/nfl/{id}.png"
ESPN_HEADSHOT = "https://a.espncdn.com/i/headshots/nfl/players/full/{id}.png"
SLEEPER_AVATAR = "https://sleepercdn.com/avatars/thumbs/{id}"


def headshot_url(player_id: str | None, position: str | None = None) -> str | None:
    pid = (player_id or "").strip()
    if not pid:
        return None
    if pid.startswith("espn:"):
        espn_id = pid.removeprefix("espn:")
        if espn_id.lstrip("-").isdigit() and not espn_id.startswith("-"):
            return ESPN_HEADSHOT.format(id=espn_id)
        return None
    if position == "DEF" or (pid.isalpha() and 2 <= len(pid) <= 3):
        return SLEEPER_LOGO.format(id=pid.upper())
    if pid.isdigit():
        return SLEEPER_HEADSHOT.format(id=pid)
    return None


def avatar_url(manager_id: str | None) -> str | None:
    if not manager_id:
        return None
    return _manager_avatars().get(manager_id)


@lru_cache(maxsize=1)
def _manager_avatars() -> dict[str, str]:
    hashes = _sleeper_avatar_hashes()
    out: dict[str, str] = {}
    for manager in load_managers():
        for sleeper_id in manager.sleeper_user_ids:
            avatar = hashes.get(str(sleeper_id))
            if avatar:
                out[manager.id] = SLEEPER_AVATAR.format(id=avatar)
                break
    return out


@lru_cache(maxsize=1)
def _sleeper_avatar_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    root = data_dir() / "sleeper"
    if not root.is_dir():
        return hashes
    for year_dir in sorted(root.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        path = year_dir / "users.json"
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for user in payload:
            if not isinstance(user, dict):
                continue
            uid = str(user.get("user_id") or "")
            avatar = user.get("avatar")
            if uid and avatar:
                hashes[uid] = str(avatar)
    return hashes
