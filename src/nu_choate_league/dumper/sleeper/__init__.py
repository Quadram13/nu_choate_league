from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from nu_choate_league.dumper.dump import project_root

from .client import SleeperClient
from .dump import STOP_IDS, dump_players, dump_season, is_error


def _load_env() -> None:
    searched = [Path.cwd(), Path(__file__).resolve().parent]
    for start in searched:
        for directory in [start, *start.parents]:
            env_file = directory / ".env"
            if env_file.is_file():
                load_dotenv(env_file)
                return
    load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip().strip('"').strip("'")


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(description="Dump raw Sleeper fantasy football JSON.")
    parser.add_argument(
        "--league-id",
        default=None,
        help="Most recent Sleeper league id (from the league URL)",
    )
    parser.add_argument(
        "--min-season",
        type=int,
        default=None,
        help="Stop walking previous_league_id before this year (default: 2024)",
    )
    parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Dump only the given league id, not previous seasons",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output root (default: data/sleeper)",
    )
    parser.add_argument(
        "--fetch-players",
        action="store_true",
        help="Download /players/nfl if data/sleeper/players/nfl.json is missing (at most once per day)",
    )
    parser.add_argument(
        "--refresh-players",
        action="store_true",
        help="Re-download /players/nfl even if the file already exists",
    )
    args = parser.parse_args()

    league_id = args.league_id or _env("SLEEPER_LEAGUE_ID")
    if not league_id:
        raise SystemExit(
            "Missing Sleeper league id. Set SLEEPER_LEAGUE_ID or pass --league-id. "
            "Use the current season's id from https://sleeper.com/leagues/<id>/..."
        )
    min_season = args.min_season
    if min_season is None:
        min_season = int(_env("SLEEPER_MIN_SEASON", "2024"))

    out_dir = args.out or (project_root() / "data" / "sleeper")
    client = SleeperClient()
    print(f"Output: {out_dir}")
    if not args.no_follow:
        print(f"Will follow previous_league_id back to {min_season}")

    if args.refresh_players or args.fetch_players:
        dump_players(client, out_dir, refresh=args.refresh_players)
    else:
        print("Skipping NFL players file (pass --fetch-players to download, at most once per day)")

    current: str | None = league_id
    seen: set[str] = set()
    dumped = 0
    while current and current not in STOP_IDS and current not in seen:
        seen.add(current)
        league = client.get(f"/league/{current}")
        if is_error(league) or not isinstance(league, dict):
            raise SystemExit(f"Failed to load Sleeper league {current}. Check the league id.")
        season = int(league.get("season") or 0)
        if season and season < min_season:
            print(f"Stopping before {current}: season {season} is before {min_season}")
            break
        dump_season(client, current, out_dir, league=league)
        dumped += 1
        if args.no_follow:
            break
        nxt = league.get("previous_league_id")
        current = None if nxt in STOP_IDS else str(nxt)

    if dumped == 0:
        raise SystemExit(f"No Sleeper leagues to dump from {league_id}.")
