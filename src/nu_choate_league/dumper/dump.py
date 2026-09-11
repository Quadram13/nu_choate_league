from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .client import EspnClient

LEAGUE_VIEWS = ["mTeam", "mRoster", "mMatchup", "mSettings", "mStandings"]
BOXSCORE_VIEWS = ["mMatchupScore", "mScoreboard", "mBoxscore"]
TRANSACTION_TYPES = [
    "DRAFT",
    "TRADE_ACCEPT",
    "WAIVER",
    "TRADE_VETO",
    "FUTURE_ROSTER",
    "ROSTER",
    "RETRO_ROSTER",
    "TRADE_PROPOSAL",
    "TRADE_UPHOLD",
    "FREEAGENT",
    "TRADE_DECLINE",
    "WAIVER_ERROR",
    "TRADE_ERROR",
]
PLAYER_CARD_BATCH = 40


def project_root() -> Path:
    here = Path(__file__).resolve()
    for directory in [here.parent, *here.parents]:
        if (directory / "pyproject.toml").is_file() and (directory / "src" / "nu_choate_league").is_dir():
            return directory
    return Path.cwd()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def collect_player_ids(obj: Any) -> set[int]:
    found: set[int] = set()

    def walk(node: Any, in_player: bool = False) -> None:
        if isinstance(node, dict):
            player_id = node.get("playerId")
            if isinstance(player_id, int) and player_id > 0:
                found.add(player_id)
            if in_player:
                inner_id = node.get("id")
                if isinstance(inner_id, int) and inner_id > 0:
                    found.add(inner_id)
            for key, value in node.items():
                walk(value, in_player or key in {"player", "playerPoolEntry"})
        elif isinstance(node, list):
            for item in node:
                walk(item, in_player)

    walk(obj)
    return found


def scoring_period_range(league: dict[str, Any]) -> tuple[int, int]:
    status = league.get("status") or {}
    start = status.get("firstScoringPeriod") or 1
    end = status.get("finalScoringPeriod") or league.get("scoringPeriodId") or 18
    return int(start), int(end)


def dump_season(
    *,
    year: int,
    league_id: int,
    espn_s2: str,
    swid: str,
    out_dir: Path,
    skip_player_cards: bool = False,
) -> Path:
    client = EspnClient(year, league_id, espn_s2, swid)
    dest = out_dir / str(year)
    dest.mkdir(parents=True, exist_ok=True)
    player_ids: set[int] = set()
    errors: list[dict[str, Any]] = []
    dumped_at = datetime.now(timezone.utc).isoformat()

    def save(relative: str, payload: Any) -> None:
        path = dest / relative
        write_json(path, payload)
        if isinstance(payload, dict) and payload.get("_dump_error"):
            errors.append({"file": relative, "error": payload["_dump_error"]})
        player_ids.update(collect_player_ids(payload))

    print(f"Dumping league {league_id} ({year}) -> {dest}")

    league = client.league(views=LEAGUE_VIEWS)
    save("league.json", league)
    if isinstance(league, dict) and league.get("_dump_error"):
        write_json(
            dest / "manifest.json",
            {
                "league_id": league_id,
                "year": year,
                "dumped_at": dumped_at,
                "ok": False,
                "errors": errors,
            },
        )
        raise SystemExit(f"Failed to load league {league_id} for {year}. Check cookies and league id.")

    draft = client.league(views="mDraftDetail")
    save("draft.json", draft)
    save(
        "pro_players.json",
        client.season(
            views="players_wl",
            extend="/players",
            headers={"x-fantasy-filter": json.dumps({"filterActive": {"value": True}})},
        ),
    )
    save("pro_schedule.json", client.season(views="proTeamSchedules_wl"))

    communication_filter = {
        "topics": {
            "filterType": {"value": ["ACTIVITY_TRANSACTIONS"]},
            "limit": 50,
            "sortMessageDate": {"sortPriority": 1, "sortAsc": False},
        }
    }
    save(
        "communication.json",
        client.league(
            views="kona_league_communication",
            extend="/communication/",
            headers={"x-fantasy-filter": json.dumps(communication_filter)},
        ),
    )

    start, end = scoring_period_range(league)
    name = (league.get("settings") or {}).get("name") or "(unnamed)"
    print(f"  {name}: scoring periods {start}-{end}")

    txn_headers = {
        "x-fantasy-filter": json.dumps({"transactions": {"filterType": {"value": TRANSACTION_TYPES}}})
    }
    for period in range(start, end + 1):
        week_dir = f"weeks/{period:02d}"
        print(f"  week {period}")
        save(
            f"{week_dir}/boxscore.json",
            client.league(views=BOXSCORE_VIEWS, scoring_period=period),
        )
        save(
            f"{week_dir}/roster.json",
            client.league(views="mRoster", scoring_period=period),
        )
        save(
            f"{week_dir}/transactions.json",
            client.league(
                views="mTransactions2",
                scoring_period=period,
                headers=txn_headers,
            ),
        )

    card_files: list[str] = []
    ids: list[int] = []
    if skip_player_cards:
        print("  skipping player cards")
    else:
        from .player_pool import fetch_player_pool_ids

        cards_dir = dest / "player_cards"
        if cards_dir.is_dir():
            for old in cards_dir.glob("*.json"):
                old.unlink()
        pool_ids = set(fetch_player_pool_ids(client, year=year, week=end))
        ids = sorted(pool_ids | player_ids)
        print(
            f"  {len(ids)} player ids "
            f"({len(pool_ids)} pool, {len(player_ids)} from dumps); "
            f"fetching cards in batches of {PLAYER_CARD_BATCH}"
        )
        additional_value = [f"00{year}", f"10{year}"]
        for index, batch in enumerate(_chunks(ids, PLAYER_CARD_BATCH)):
            filters = {
                "players": {
                    "filterIds": {"value": batch},
                    "filterStatsForTopScoringPeriodIds": {
                        "value": end,
                        "additionalValue": additional_value,
                    },
                }
            }
            relative = f"player_cards/{index:03d}.json"
            save(
                relative,
                client.league(
                    views="kona_playercard",
                    headers={"x-fantasy-filter": json.dumps(filters)},
                ),
            )
            card_files.append(relative)

    manifest = {
        "league_id": league_id,
        "year": year,
        "name": name,
        "dumped_at": dumped_at,
        "ok": not errors,
        "scoring_periods": {"first": start, "final": end},
        "player_ids": len(ids) if card_files else len(player_ids),
        "player_card_files": card_files,
        "errors": errors,
    }
    write_json(dest / "manifest.json", manifest)
    print(f"  wrote manifest ({len(errors)} request errors)")
    return dest


def _chunks(values: list[int], size: int) -> Iterable[list[int]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]
