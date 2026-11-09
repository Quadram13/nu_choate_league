"""Prove the fa chain still has the plain-view rows, columns, and readers.

--dry-apply executes sql/analysis/62_fa_weeks.sql through the load splitter
inside a transaction, checks the checksums, and rolls back.
Without that flag, the check runs against the committed database and calls
the query helpers the hub uses.
"""

from __future__ import annotations

import argparse
import sys

from nu_choate_league.db import ANALYSIS_SNAPSHOTS, _statements, connect
from nu_choate_league.paths import project_root
from nu_choate_league.web.queries import (
    _fa_best_week_by_season,
    _fa_career_leaders,
    _fa_season_leaders,
    _fa_week_leaders,
)

NAMES = ("v_fa_weeks", "v_fa_season", "v_fa_career")
COLUMNS = {
    "v_fa_weeks": [
        "year",
        "week",
        "player_id",
        "player_name",
        "position",
        "points",
        "n_starters",
        "replacement",
        "replacement_player_id",
        "replacement_player_name",
        "vorp",
    ],
    "v_fa_season": [
        "year",
        "player_id",
        "player_name",
        "position",
        "fa_weeks",
        "rostered_weeks",
        "lineup_weeks",
        "fa_points",
        "stored_weeks",
        "stored_vorp",
        "missing_vorp",
        "fa_vorp",
        "best_week",
        "best_points",
        "best_vorp",
        "never_rostered",
    ],
    "v_fa_career": [
        "player_id",
        "player_name",
        "position",
        "seasons",
        "first_year",
        "last_year",
        "fa_weeks",
        "rostered_weeks",
        "fa_points",
        "stored_vorp",
        "missing_vorp",
        "fa_vorp",
        "best_points",
        "never_rostered",
    ],
}
def parse_expect(items: list[str]) -> dict[str, tuple[int, str]]:
    expected: dict[str, tuple[int, str]] = {}
    for item in items:
        name, count, checksum = item.split(":")
        if name not in NAMES:
            raise SystemExit(f"unknown relation {name}")
        expected[name] = (int(count), checksum)
    return expected


def checksum(cur, name: str) -> tuple[int, str]:
    if name not in NAMES:
        raise SystemExit(f"refusing checksum of {name}")
    cur.execute(
        f"""
        SELECT count(*)::bigint,
               md5(string_agg(md5(t::text), '' ORDER BY md5(t::text)))
        FROM {name} t
        """
    )
    count, digest = cur.fetchone()
    return int(count), digest


def kinds(cur) -> dict[str, str]:
    cur.execute(
        """
        SELECT c.relname, c.relkind::text
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = ANY(%s)
        ORDER BY c.relname
        """,
        (list(NAMES),),
    )
    found = {name: kind for name, kind in cur.fetchall()}
    missing = [name for name in NAMES if name not in found]
    if missing:
        raise SystemExit(f"missing relations {missing}")
    return found


def columns(cur, name: str) -> list[str]:
    cur.execute(
        """
        SELECT a.attname
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = %s
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY a.attnum
        """,
        (name,),
    )
    return [row[0] for row in cur.fetchall()]


def dependents(cur) -> list[str]:
    cur.execute(
        """
        SELECT DISTINCT dep.relname
        FROM pg_depend d
        JOIN pg_rewrite r ON r.oid = d.objid
        JOIN pg_class dep ON dep.oid = r.ev_class
        JOIN pg_class src ON src.oid = d.refobjid
        WHERE src.relname = ANY(%s)
          AND dep.relname <> ALL(%s)
        ORDER BY dep.relname
        """,
        (list(NAMES), list(NAMES)),
    )
    return [row[0] for row in cur.fetchall()]


def check_snapshot_list(matviews: list[str]) -> None:
    positions = [ANALYSIS_SNAPSHOTS.index(name) for name in matviews]
    if positions != sorted(positions):
        raise SystemExit(f"refresh order {ANALYSIS_SNAPSHOTS} does not follow {matviews}")
    print("refresh_list", ", ".join(ANALYSIS_SNAPSHOTS))


def check_relations(cur, expected: dict[str, tuple[int, str]], matviews: list[str]) -> None:
    found = kinds(cur)
    print("relkinds", found)
    for name in NAMES:
        want = "m" if name in matviews else "v"
        if found[name] != want:
            raise SystemExit(f"{name} relkind {found[name]} wanted {want}")
        got_columns = columns(cur, name)
        if got_columns != COLUMNS[name]:
            raise SystemExit(f"{name} columns {got_columns}")
        count, digest = checksum(cur, name)
        print(f"{name} n={count} checksum={digest}")
        if name in expected and (count, digest) != expected[name]:
            raise SystemExit(
                f"{name} mismatch got {count} {digest} expected {expected[name][0]} {expected[name][1]}"
            )
    extra = dependents(cur)
    if extra:
        raise SystemExit(f"unexpected dependents {extra}")
    print("dependents_outside_chain=0")


def dry_apply(expected: dict[str, tuple[int, str]], matviews: list[str]) -> None:
    path = project_root() / "sql" / "analysis" / "62_fa_weeks.sql"
    statements = _statements(path.read_text(encoding="utf-8"))
    print(f"dry_apply statements={len(statements)}")
    if not any(statement.lstrip().startswith("DO") for statement in statements):
        raise SystemExit("splitter dropped the DO block")
    conn = connect()
    try:
        for statement in statements:
            conn.execute(statement)
        for name in matviews:
            conn.execute(f"REFRESH MATERIALIZED VIEW {name}")
        with conn.cursor() as cur:
            check_relations(cur, expected, matviews)
    finally:
        conn.rollback()
        conn.close()
    with connect() as conn:
        with conn.cursor() as cur:
            found = kinds(cur)
    print("after_rollback", found)
    if any(kind != "v" for kind in found.values()):
        raise SystemExit("rollback left a materialized view in place")
    print("dry_apply rolled back")


def live_readers() -> None:
    batches = {
        "week_leaders": _fa_week_leaders(limit=10),
        "best_week_by_season": _fa_best_week_by_season(),
        "season_leaders": _fa_season_leaders(limit=10),
        "career_leaders": _fa_career_leaders(limit=10),
    }
    for label, rows in batches.items():
        if not rows:
            raise SystemExit(f"{label} returned no rows")
        print(f"{label} rows={len(rows)} first={rows[0].get('player_name')}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", action="append", default=[])
    parser.add_argument("--matview", action="append", default=[])
    parser.add_argument("--dry-apply", action="store_true")
    args = parser.parse_args()
    for name in args.matview:
        if name not in NAMES:
            raise SystemExit(f"unknown matview {name}")
    if any(name not in ANALYSIS_SNAPSHOTS for name in args.matview):
        raise SystemExit(f"matview missing from ANALYSIS_SNAPSHOTS {ANALYSIS_SNAPSHOTS}")
    check_snapshot_list(args.matview)
    expected = parse_expect(args.expect)
    if args.dry_apply:
        dry_apply(expected, args.matview)
        return
    with connect() as conn:
        with conn.cursor() as cur:
            check_relations(cur, expected, args.matview)
    live_readers()
    print("prove_fa_identity ok")


if __name__ == "__main__":
    sys.exit(main())
