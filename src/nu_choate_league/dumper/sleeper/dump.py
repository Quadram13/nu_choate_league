from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nu_choate_league.dumper.dump import write_json

from .client import SleeperClient

STOP_IDS = {None, "", "0", 0}


def is_error(payload: Any) -> bool:
    return isinstance(payload, dict) and bool(payload.get("_dump_error"))


def week_range(league: dict[str, Any], nfl_state: Any) -> tuple[int, int]:
    settings = league.get("settings") or {}
    last = int(settings.get("last_scored_leg") or 0)
    playoff_start = int(settings.get("playoff_week_start") or 15)
    season = str(league.get("season") or "")
    state = nfl_state if isinstance(nfl_state, dict) else {}
    current = str(state.get("league_season") or state.get("season") or "")
    live_week = int(state.get("leg") or state.get("week") or 0)

    if season and season == current and live_week:
        end = max(live_week, last, 1)
    else:
        end = max(18, last, playoff_start + 3)
    return 1, min(max(end, 1), 22)


def dump_players(client: SleeperClient, out_dir: Path, *, refresh: bool) -> Path:
    path = out_dir / "players" / "nfl.json"
    if path.is_file() and not refresh:
        print(f"  keeping existing {path}")
        return path
    payload = client.get("/players/nfl")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    count = len(payload) if isinstance(payload, dict) and not is_error(payload) else "?"
    print(f"  wrote {count} NFL players")
    return path


def dump_season(
    client: SleeperClient,
    league_id: str,
    out_dir: Path,
    league: dict[str, Any] | None = None,
) -> str | None:
    if league is None:
        loaded = client.get(f"/league/{league_id}")
        if is_error(loaded) or not isinstance(loaded, dict):
            print(f"Failed to load Sleeper league {league_id}")
            return None
        league = loaded

    year = str(league.get("season") or "unknown")
    dest = out_dir / year
    dest.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, Any]] = []
    dumped_at = datetime.now(timezone.utc).isoformat()

    def save(relative: str, payload: Any) -> None:
        write_json(dest / relative, payload)
        if is_error(payload):
            errors.append({"file": relative, "error": payload["_dump_error"]})

    name = league.get("name") or "(unnamed)"
    print(f"Dumping {name} {year} ({league_id}) -> {dest}")
    save("league.json", league)
    save("users.json", client.get(f"/league/{league_id}/users"))
    save("rosters.json", client.get(f"/league/{league_id}/rosters"))
    save("traded_picks.json", client.get(f"/league/{league_id}/traded_picks"))
    save("winners_bracket.json", client.get(f"/league/{league_id}/winners_bracket"))
    save("losers_bracket.json", client.get(f"/league/{league_id}/losers_bracket"))

    drafts = client.get(f"/league/{league_id}/drafts")
    save("drafts.json", drafts)
    draft_ids: list[str] = []
    if isinstance(drafts, list):
        draft_ids = [str(item.get("draft_id")) for item in drafts if isinstance(item, dict) and item.get("draft_id")]
    elif league.get("draft_id"):
        draft_ids = [str(league["draft_id"])]
    if len(draft_ids) > 1:
        print(f"  {len(draft_ids)} drafts; writing the first to drafts/ and the rest under drafts/<id>/")
    for index, draft_id in enumerate(draft_ids):
        prefix = "drafts" if index == 0 else f"drafts/{draft_id}"
        save(f"{prefix}/draft.json", client.get(f"/draft/{draft_id}"))
        save(f"{prefix}/picks.json", client.get(f"/draft/{draft_id}/picks"))
        save(f"{prefix}/traded_picks.json", client.get(f"/draft/{draft_id}/traded_picks"))

    nfl_state = client.get("/state/nfl")
    save("nfl_state.json", nfl_state)
    start, end = week_range(league, nfl_state)
    print(f"  weeks {start}-{end}")
    for week in range(start, end + 1):
        print(f"  week {week}")
        save(f"weeks/{week:02d}/matchups.json", client.get(f"/league/{league_id}/matchups/{week}"))
        save(f"weeks/{week:02d}/transactions.json", client.get(f"/league/{league_id}/transactions/{week}"))
        save(f"weeks/{week:02d}/stats.json", client.get(f"/stats/nfl/regular/{year}/{week}"))

    previous = league.get("previous_league_id")
    manifest = {
        "league_id": league_id,
        "year": year,
        "name": name,
        "dumped_at": dumped_at,
        "ok": not errors,
        "previous_league_id": previous,
        "weeks": {"first": start, "final": end},
        "draft_ids": draft_ids,
        "errors": errors,
    }
    write_json(dest / "manifest.json", manifest)
    print(f"  wrote manifest ({len(errors)} request errors)")
    if previous in STOP_IDS:
        return None
    return str(previous)
