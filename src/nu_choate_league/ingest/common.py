from __future__ import annotations

from ..models import Platform
from ..players import PlayerIndex


def resolve_player(
    players: PlayerIndex,
    platform: Platform,
    platform_id: object,
    name: str = "",
    position: str | None = None,
) -> tuple[str, str]:
    if platform is Platform.ESPN:
        espn_id = int(platform_id)
        player = players.resolve_espn(espn_id, name=name, position=position)
        return player.id, player.display_name or name or player.id
    sleeper_id = str(platform_id)
    player = players.from_sleeper(sleeper_id)
    if player is None:
        return sleeper_id, name or sleeper_id
    return player.id, player.display_name or name or player.id
