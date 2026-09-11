from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .client import EspnClient
from .dump import write_json

PAGE_SIZE = 500
POOL_STATUSES = ["FREEAGENT", "WAIVERS", "ONTEAM"]


def _is_error(payload: Any) -> bool:
    return isinstance(payload, dict) and bool(payload.get("_dump_error"))


def _pool_id_filter(*, offset: int) -> dict[str, Any]:
    return {
        "players": {
            "filterStatus": {"value": POOL_STATUSES},
            "limit": PAGE_SIZE,
            "offset": offset,
            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
        }
    }


def _player_filter(*, year: int, week: int, offset: int) -> dict[str, Any]:
    additional = [f"00{year}", f"10{year}", f"11{year}{week}"]
    filt = _pool_id_filter(offset=offset)
    filt["players"]["filterStatsForTopScoringPeriodIds"] = {
        "value": 2,
        "additionalValue": additional,
    }
    return filt


def _wrap_player_id(wrap: Any) -> int | None:
    if not isinstance(wrap, dict):
        return None
    player_id = wrap.get("id")
    if isinstance(player_id, int) and player_id > 0:
        return player_id
    inner = wrap.get("player")
    if isinstance(inner, dict):
        inner_id = inner.get("id")
        if isinstance(inner_id, int) and inner_id > 0:
            return inner_id
    return None


def fetch_player_pool_ids(client: EspnClient, *, year: int, week: int) -> list[int]:
    payload = fetch_player_pool(client, year=year, week=week, include_stats=False)
    if _is_error(payload):
        print(f"  player pool id fetch failed: {payload.get('_dump_error')}")
        return []
    found: list[int] = []
    seen: set[int] = set()
    for wrap in payload.get("players") or []:
        player_id = _wrap_player_id(wrap)
        if player_id is None or player_id in seen:
            continue
        seen.add(player_id)
        found.append(player_id)
    print(f"  player pool ids: {len(found)}")
    return found


def fetch_player_pool(
    client: EspnClient,
    *,
    year: int,
    week: int,
    include_stats: bool = True,
) -> dict[str, Any]:
    players: list[Any] = []
    combined: dict[str, Any] | None = None
    offset = 0
    while True:
        print(f"  player pool {year} week {week} offset {offset}", flush=True)
        filt = (
            _player_filter(year=year, week=week, offset=offset)
            if include_stats
            else _pool_id_filter(offset=offset)
        )
        page = client.league(
            views="kona_player_info",
            scoring_period=week,
            headers={"x-fantasy-filter": json.dumps(filt)},
        )
        if _is_error(page):
            if not players:
                return page
            return {
                **(combined or {}),
                "players": players,
                "_dump_error": page["_dump_error"],
            }
        if combined is None:
            combined = dict(page)
        batch = page.get("players") if isinstance(page, dict) else None
        if not isinstance(batch, list) or not batch:
            break
        players.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    if combined is None:
        return {"players": []}
    combined["players"] = players
    return combined


def _weekly_projection(player_wrap: dict[str, Any], *, week: int) -> float | None:
    inner = player_wrap.get("player") if isinstance(player_wrap.get("player"), dict) else player_wrap
    stats = inner.get("stats") if isinstance(inner, dict) else None
    if not isinstance(stats, list):
        return None
    for row in stats:
        if not isinstance(row, dict):
            continue
        if row.get("statSourceId") == 1 and row.get("scoringPeriodId") == week:
            try:
                return float(row.get("appliedTotal") or 0)
            except (TypeError, ValueError):
                return 0.0
    return None


def _season_projection(player_wrap: dict[str, Any]) -> float | None:
    inner = player_wrap.get("player") if isinstance(player_wrap.get("player"), dict) else player_wrap
    stats = inner.get("stats") if isinstance(inner, dict) else None
    if not isinstance(stats, list):
        return None
    for row in stats:
        if not isinstance(row, dict):
            continue
        if row.get("statSourceId") == 1 and row.get("scoringPeriodId") == 0 and row.get("statSplitTypeId") == 0:
            try:
                return float(row.get("appliedTotal") or 0)
            except (TypeError, ValueError):
                return 0.0
    return None


def summarize_player_pool(payload: dict[str, Any], *, week: int) -> None:
    if _is_error(payload):
        print(f"  request failed: {payload.get('_dump_error')}")
        if not payload.get("players"):
            return
    wraps = payload.get("players") or []
    statuses: Counter[str] = Counter()
    weekly_rows = Counter()
    weekly_nonzero = Counter()
    season_nonzero = Counter()
    fa_samples: list[str] = []
    for wrap in wraps:
        if not isinstance(wrap, dict):
            continue
        status = str(wrap.get("status") or "(none)")
        statuses[status] += 1
        weekly = _weekly_projection(wrap, week=week)
        if weekly is not None:
            weekly_rows[status] += 1
            if weekly:
                weekly_nonzero[status] += 1
                if status in {"FREEAGENT", "WAIVERS"} and len(fa_samples) < 5:
                    name = ((wrap.get("player") or {}).get("fullName") if isinstance(wrap.get("player"), dict) else None) or "?"
                    fa_samples.append(f"{name} {weekly:.2f}")
        season = _season_projection(wrap)
        if season:
            season_nonzero[status] += 1

    total = sum(statuses.values())
    print(f"  players {total}  statuses {dict(statuses)}")
    print(
        f"  weekly proj rows {dict(weekly_rows)}  nonzero {dict(weekly_nonzero)}  "
        f"({sum(weekly_nonzero.values())}/{total})"
    )
    print(f"  season proj nonzero {dict(season_nonzero)} ({sum(season_nonzero.values())}/{total})")
    if fa_samples:
        print(f"  FA/waiver weekly samples: {', '.join(fa_samples)}")


def dump_player_pool_weeks(
    *,
    year: int,
    league_id: int,
    espn_s2: str,
    swid: str,
    out_dir: Path,
    weeks: list[int],
) -> None:
    dest = out_dir / str(year)
    dest.mkdir(parents=True, exist_ok=True)
    client = EspnClient(year, league_id, espn_s2, swid)
    print(f"Probing player pool {year} ({league_id}) weeks {weeks} -> {dest}")
    for week in weeks:
        payload = fetch_player_pool(client, year=year, week=week)
        path = dest / f"weeks/{week:02d}/player_pool.json"
        write_json(path, payload)
        n = len(payload.get("players") or []) if isinstance(payload, dict) else 0
        print(f"  wrote {path} ({n} players)")
        summarize_player_pool(payload, week=week)
