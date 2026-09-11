from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .dump import dump_season, project_root
from .player_pool import dump_player_pool_weeks


def _load_env() -> None:
    searched = [Path.cwd(), Path(__file__).resolve().parent]
    for start in searched:
        for directory in [start, *start.parents]:
            env_file = directory / ".env"
            if env_file.is_file():
                load_dotenv(env_file)
                return
    load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip().strip('"').strip("'")
    if not value:
        raise SystemExit(f"Missing {name}. Copy .env.example to .env and fill in cookies and leagues.")
    return value


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip().strip('"').strip("'")


def _parse_leagues(raw: str) -> list[tuple[int, int]]:
    leagues: list[tuple[int, int]] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if ":" not in item:
            raise SystemExit(f"Invalid ESPN_LEAGUES entry {item!r}. Use year:leagueId,year:leagueId.")
        year_text, league_text = item.split(":", 1)
        leagues.append((int(year_text), int(league_text)))
    return leagues


def _leagues_from_year_keys() -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    prefix = "ESPN_LEAGUE_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        suffix = key.removeprefix(prefix)
        if not suffix.isdigit() or len(suffix) != 4:
            continue
        league_id = value.strip().strip('"').strip("'")
        if league_id:
            found.append((int(suffix), int(league_id)))
    return sorted(found)


def _leagues_from_env() -> list[tuple[int, int]]:
    from_keys = _leagues_from_year_keys()
    if from_keys:
        return from_keys
    packed = _parse_leagues(_env("ESPN_LEAGUES"))
    if packed:
        return packed
    year = _env("ESPN_YEAR")
    league_id = _env("ESPN_LEAGUE_ID")
    if year and league_id:
        return [(int(year), int(league_id))]
    return []


def _parse_weeks(raw: str | None) -> list[int]:
    text = (raw or "1,8").strip()
    weeks: list[int] = []
    for part in text.split(","):
        item = part.strip()
        if not item:
            continue
        week = int(item)
        if week < 1:
            raise SystemExit(f"Invalid week {week}. Scoring periods start at 1.")
        weeks.append(week)
    if not weeks:
        raise SystemExit("No weeks to probe.")
    return weeks


def _leagues_from_env_and_args(args: argparse.Namespace) -> list[tuple[int, int]]:
    mapped = _leagues_from_env()
    by_year = {year: league_id for year, league_id in mapped}

    if args.year is not None and args.league_id is not None:
        return [(args.year, args.league_id)]
    if args.year is not None:
        if args.year not in by_year:
            raise SystemExit(
                f"No ESPN league id for {args.year}. "
                f"Set ESPN_LEAGUE_{args.year} in .env or pass --league-id."
            )
        return [(args.year, by_year[args.year])]
    if args.league_id is not None:
        raise SystemExit("Pass --year with --league-id, or set ESPN_LEAGUE_{year} in .env.")
    if mapped:
        return mapped
    raise SystemExit(
        "No ESPN leagues in .env. Set ESPN_LEAGUE_2022 and ESPN_LEAGUE_2023 "
        "(or ESPN_LEAGUES=year:leagueId,...), or pass --year and --league-id."
    )


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(description="Dump raw ESPN fantasy football JSON.")
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Dump a single season (league id from ESPN_LEAGUE_{year} unless --league-id is set)",
    )
    parser.add_argument("--league-id", type=int, default=None, help="Override the ESPN league id for --year")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output root (default: data/espn)",
    )
    parser.add_argument(
        "--skip-player-cards",
        action="store_true",
        help="Skip batched kona_playercard fetches",
    )
    parser.add_argument(
        "--probe-player-pool",
        action="store_true",
        help="Fetch kona_player_info for a few weeks instead of a full season dump",
    )
    parser.add_argument(
        "--weeks",
        default=None,
        help="Comma-separated scoring periods for --probe-player-pool (default: 1,8)",
    )
    args = parser.parse_args()

    espn_s2 = _require_env("ESPN_S2")
    swid = _require_env("ESPN_SWID")
    if not swid.startswith("{"):
        print("warning: SWID usually looks like {UUID} with curly braces", file=sys.stderr)

    out_dir = args.out or (project_root() / "data" / "espn")
    print(f"Output: {out_dir}")

    if args.probe_player_pool:
        if args.year is None:
            args.year = 2023
        leagues = _leagues_from_env_and_args(args)
        weeks = _parse_weeks(args.weeks)
        year, league_id = leagues[0]
        dump_player_pool_weeks(
            year=year,
            league_id=league_id,
            espn_s2=espn_s2,
            swid=swid,
            out_dir=out_dir,
            weeks=weeks,
        )
        return

    leagues = _leagues_from_env_and_args(args)
    for year, league_id in leagues:
        dump_season(
            year=year,
            league_id=league_id,
            espn_s2=espn_s2,
            swid=swid,
            out_dir=out_dir,
            skip_player_cards=args.skip_player_cards,
        )
