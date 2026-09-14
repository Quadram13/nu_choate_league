from __future__ import annotations

SLEEPER_HEADSHOT = "https://sleepercdn.com/content/nfl/players/thumb/{id}.jpg"
SLEEPER_LOGO = "https://sleepercdn.com/images/team_logos/nfl/{id}.png"
ESPN_HEADSHOT = "https://a.espncdn.com/i/headshots/nfl/players/full/{id}.png"


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
