"""Prove the players-index snapshots match a fresh run of their own queries.

The page query that adds age is checked against the pre-snapshot career
statement. Fa-chain checksums are printed so a caller can see this script
did not rewrite v_fa_weeks, v_fa_season, or v_fa_career.
"""

from __future__ import annotations

import time

from nu_choate_league.db import _statements
from nu_choate_league.paths import project_root
from nu_choate_league.web.queries import connect

NAMES = (
    "v_players_index_career",
    "v_players_index_season",
    "v_players_index_gap",
    "v_players_index_vol_career",
    "v_players_index_vol_season",
)
FA = ("v_fa_weeks", "v_fa_season", "v_fa_career")

# The served career statement before the snapshot, and the statement the
# page runs after it. Age stays on the read path. Column order matches.
OLD_CAREER = """
SELECT
    i.player_id, i.player_name, i.position, i.seasons, i.first_year, i.last_year,
    i.starts, i.bench_weeks, i.starter_points, i.rostered_weeks, i.fa_weeks,
    i.started_vorp, i.own_pct, i.lineup_weeks, i.times_drafted, i.times_added,
    i.times_traded,
    coalesce(r.rings, 0) AS rings,
    coalesce(r.title_starts, 0) AS title_starts,
    coalesce(r.champ_roster_weeks, 0) AS champ_roster_weeks,
    coalesce(jm.managers, 0) AS managers,
    p.birth_date, p.height_in, p.weight_lb, p.rookie_year,
    CASE
        WHEN p.birth_date IS NULL THEN NULL
        ELSE EXTRACT(YEAR FROM age(p.birth_date))::integer
    END AS age_years
FROM v_player_index i
LEFT JOIN players p ON p.id = i.player_id
LEFT JOIN v_player_rings r ON r.player_id = i.player_id
LEFT JOIN v_player_managers jm ON jm.player_id = i.player_id
"""

NEW_CAREER = """
SELECT
    player_id, player_name, position, seasons, first_year, last_year,
    starts, bench_weeks, starter_points, rostered_weeks, fa_weeks,
    started_vorp, own_pct, lineup_weeks, times_drafted, times_added,
    times_traded, rings, title_starts, champ_roster_weeks, managers,
    birth_date, height_in, weight_lb, rookie_year,
    CASE
        WHEN birth_date IS NULL THEN NULL
        ELSE EXTRACT(YEAR FROM age(birth_date))::integer
    END AS age_years
FROM v_players_index_career
"""


def checksum_sql(name_or_query: str, *, query: bool) -> str:
    source = f"({name_or_query}) t" if query else f"{name_or_query} t"
    return f"""
        SELECT count(*)::bigint,
               md5(string_agg(md5(t::text), '' ORDER BY md5(t::text)))
        FROM {source}
    """


def one(cur, sql: str) -> tuple:
    cur.execute(sql)
    row = cur.fetchone()
    return (int(row["count"]), row["md5"])


def main() -> None:
    path = project_root() / "sql" / "analysis" / "99_players_index_snapshot.sql"
    text = path.read_text(encoding="utf-8")
    statements = _statements(text)
    if not any(statement.lstrip().startswith("CREATE MATERIALIZED VIEW") for statement in statements):
        raise SystemExit("splitter dropped the snapshot creates")
    creates = [statement for statement in statements if "CREATE MATERIALIZED VIEW" in statement]
    if len(creates) != len(NAMES):
        raise SystemExit(f"expected {len(NAMES)} creates, splitter returned {len(creates)}")

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.relname, c.relkind::text
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = ANY(%s)
        ORDER BY c.relname
        """,
        (list(NAMES),),
    )
    kinds = {row["relname"]: row["relkind"] for row in cur.fetchall()}
    missing = [name for name in NAMES if kinds.get(name) != "m"]
    if missing:
        raise SystemExit(f"expected materialized views, found {kinds} missing {missing}")
    print("relkind", kinds)

    for name in NAMES:
        cur.execute("SELECT pg_get_viewdef(%s::regclass, true) AS def", (name,))
        definition = cur.fetchone()["def"].strip().rstrip(";").strip()
        started = time.perf_counter()
        fresh = one(cur, checksum_sql(definition, query=True))
        fresh_ms = (time.perf_counter() - started) * 1000.0
        stored = one(cur, checksum_sql(name, query=False))
        reads = []
        for _ in range(3):
            t0 = time.perf_counter()
            cur.execute(f"SELECT * FROM {name}")
            cur.fetchall()
            reads.append((time.perf_counter() - t0) * 1000.0)
        if fresh != stored:
            raise SystemExit(f"{name} checksum mismatch fresh={fresh} stored={stored}")
        print(
            f"{name} rows={stored[0]} md5={stored[1]} "
            f"fresh_ms={fresh_ms:.1f} read_ms={[round(item, 2) for item in reads]}"
        )

    old = one(cur, checksum_sql(OLD_CAREER, query=True))
    new = one(cur, checksum_sql(NEW_CAREER, query=True))
    if old != new:
        raise SystemExit(f"career page checksum mismatch old={old} new={new}")
    print(f"career_with_age rows={new[0]} md5={new[1]} matches the pre-snapshot statement")

    cur.execute(
        """
        SELECT ref.relname AS snapshot, c.relname AS dependent, c.relkind::text AS kind
        FROM pg_depend d
        JOIN pg_rewrite rw ON rw.oid = d.objid
        JOIN pg_class c ON c.oid = rw.ev_class
        JOIN pg_class ref ON ref.oid = d.refobjid
        WHERE ref.relname = ANY(%s)
          AND c.oid <> ref.oid
        ORDER BY 1, 2
        """,
        (list(NAMES),),
    )
    dependents = cur.fetchall()
    if dependents:
        raise SystemExit(f"unexpected dependents {dependents}")
    print("dependents none")

    cur.execute(
        """
        SELECT DISTINCT c.relname AS snapshot, ref.relname AS reads, ref.relkind::text AS kind
        FROM pg_depend d
        JOIN pg_rewrite rw ON rw.oid = d.objid
        JOIN pg_class c ON c.oid = rw.ev_class
        JOIN pg_class ref ON ref.oid = d.refobjid
        JOIN pg_namespace n ON n.oid = ref.relnamespace
        WHERE c.relname = ANY(%s)
          AND n.nspname = 'public'
          AND ref.oid <> c.oid
          AND ref.relkind IN ('v', 'm', 'r')
        ORDER BY 1, 2
        """,
        (list(NAMES),),
    )
    print("reads")
    for row in cur.fetchall():
        print(f"  {row['snapshot']} -> {row['reads']} ({row['kind']})")

    for name in FA:
        count, digest = one(cur, checksum_sql(name, query=False))
        print(f"fa {name} rows={count} md5={digest}")
    conn.close()
    print("ok")


if __name__ == "__main__":
    main()
