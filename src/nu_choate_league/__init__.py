from __future__ import annotations

import argparse
import sys

from .alternate import alternate_season, format_alternate
from .build import build_data, format_draft, format_standings, format_transactions
from .history import career_records, format_career, format_h2h, head_to_head
from .inspect_managers import format_report, inspect_managers
from .inspect_players import format_player_report, inspect_players
from .ingest import ingest_all
from .load import load_facts
from .query import QUERY_NAMES, run_query


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Nu Choate League hub")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("inspect-managers", help="Check every dump owner against maps/managers.yaml")
    sub.add_parser("inspect-players", help="Check ESPN/Sleeper player ids against the Sleeper catalog")
    build = sub.add_parser("build-data", help="Write canonical JSON under site/data/")
    build.add_argument("--year", type=int, help="Only ingest this season")
    load = sub.add_parser("load", help="Ingest dumps and upsert fact tables in Postgres")
    load.add_argument("--year", type=int, help="Replace this season only")
    query = sub.add_parser("query", help="Print a Postgres analysis view")
    query.add_argument(
        "name",
        choices=QUERY_NAMES,
        help="career, h2h, record-weeks, draft, moves, universes, luck, trades, draft-value, waivers, or vorp",
    )
    query.add_argument(
        "--year",
        type=int,
        help="Only this season (draft, moves, universes, luck, trades, draft-value, waivers, vorp)",
    )
    query.add_argument("--manager", help="Only this manager id (h2h, luck, trades, draft-value, waivers)")
    standings = sub.add_parser("standings", help="Print regular-season standings")
    standings.add_argument("year", type=int)
    draft = sub.add_parser("draft", help="Print the draft board")
    draft.add_argument("year", type=int)
    txns = sub.add_parser("transactions", help="Print adds, drops, and trades")
    txns.add_argument("year", type=int)
    sub.add_parser("career", help="Print career records")
    h2h = sub.add_parser("h2h", help="Print head-to-head records")
    h2h.add_argument("manager", nargs="?", help="Only rows involving this manager id")
    alt = sub.add_parser("alternate", help="Print H2H-only and always-median what-ifs")
    alt.add_argument("year", type=int)
    args = parser.parse_args(argv)
    if args.command == "inspect-managers":
        report = inspect_managers()
        sys.stdout.write(format_report(report))
        raise SystemExit(0 if report.ok else 1)
    if args.command == "inspect-players":
        report = inspect_players()
        sys.stdout.write(format_player_report(report))
        raise SystemExit(0 if report.ok else 1)
    if args.command == "build-data":
        lines = build_data(year=args.year)
        sys.stdout.write("\n".join(lines) + "\n")
        raise SystemExit(0 if all("DIFF" not in line for line in lines) else 1)
    if args.command == "load":
        lines = load_facts(year=args.year)
        sys.stdout.write("\n".join(lines) + "\n")
        raise SystemExit(0 if all("DIFF" not in line for line in lines) else 1)
    if args.command == "query":
        sys.stdout.write(run_query(args.name, year=args.year, manager=args.manager))
        raise SystemExit(0)
    if args.command in {"standings", "draft", "transactions"}:
        bundles = ingest_all(year=args.year)
        if not bundles:
            raise SystemExit(f"No season {args.year} in maps/seasons.yaml")
        bundle = bundles[0]
        if args.command == "standings":
            sys.stdout.write(format_standings(bundle.teams))
        elif args.command == "draft":
            sys.stdout.write(format_draft(bundle.draft_picks))
        else:
            sys.stdout.write(format_transactions(bundle.transactions))
        raise SystemExit(0)
    if args.command in {"career", "h2h"}:
        bundles = ingest_all()
        if args.command == "career":
            sys.stdout.write(format_career(career_records(bundles)))
        else:
            sys.stdout.write(format_h2h(head_to_head(bundles), args.manager))
        raise SystemExit(0)
    if args.command == "alternate":
        bundles = ingest_all(year=args.year)
        if not bundles:
            raise SystemExit(f"No season {args.year} in maps/seasons.yaml")
        alt = alternate_season(bundles[0])
        if alt is None:
            raise SystemExit(f"No completed games in {args.year}")
        sys.stdout.write(format_alternate(alt))
        raise SystemExit(0)
    parser.print_help()
    raise SystemExit(2)
