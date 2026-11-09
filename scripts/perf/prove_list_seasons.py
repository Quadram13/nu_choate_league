"""Prove the fenced list_seasons query matches the inlined one.

Calls list_seasons() and compares every SQL column to the pre-fence
statement. Hues are derived in Python from the ids, so they are checked
against manager_hue. Exits nonzero if a column moves.
"""

from __future__ import annotations

import inspect

from nu_choate_league.web.names import manager_hue
from nu_choate_league.web.queries import connect, list_seasons

OLD = """
SELECT
    s.year,
    s.platform,
    s.vs_median,
    s.name,
    oc.id AS champion_id,
    oc.display_name AS champion,
    oc_ts.team_name AS champion_team,
    ru.display_name AS runner_up,
    CASE WHEN fin.regular_season_complete THEN rs.display_name END
        AS regular_season_champion,
    CASE WHEN fin.regular_season_complete THEN mp.display_name END
        AS most_points,
    CASE WHEN fin.regular_season_complete THEN lc.id END AS last_chair_id,
    CASE WHEN fin.regular_season_complete THEN lc.display_name END
        AS last_chair,
    CASE WHEN fin.regular_season_complete THEN lc_ts.team_name END
        AS last_chair_team
FROM seasons s
JOIN v_finished_seasons fin ON fin.year = s.year
LEFT JOIN season_outcomes o ON o.year = s.year
LEFT JOIN managers oc ON oc.id = o.champion
LEFT JOIN team_seasons oc_ts
    ON oc_ts.year = s.year AND oc_ts.manager_id = o.champion
LEFT JOIN managers ru ON ru.id = o.runner_up
LEFT JOIN managers rs ON rs.id = o.regular_season_champion
LEFT JOIN managers mp ON mp.id = o.most_points
LEFT JOIN LATERAL (
    SELECT st.manager_id
    FROM v_standings_official st
    WHERE st.year = s.year
        AND st.wins + st.losses + st.ties > 0
    ORDER BY st.rank DESC, st.manager_id
    LIMIT 1
) last ON true
LEFT JOIN managers lc ON lc.id = last.manager_id
LEFT JOIN team_seasons lc_ts
    ON lc_ts.year = s.year AND lc_ts.manager_id = last.manager_id
ORDER BY s.year DESC
"""


def main() -> None:
    source = inspect.getsource(list_seasons)
    if "WITH fin AS MATERIALIZED" not in source:
        raise SystemExit("list_seasons is missing the MATERIALIZED fence")
    if "JOIN v_finished_seasons fin" in source:
        raise SystemExit("list_seasons still inlines v_finished_seasons")
    served = list_seasons()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(OLD)
            old = list(cur.fetchall())
    if len(old) != len(served):
        raise SystemExit(f"row count {len(old)} != {len(served)}")
    if not old:
        raise SystemExit("list_seasons returned no rows")
    keys = list(old[0].keys())
    for index, (before, after) in enumerate(zip(old, served, strict=True)):
        for key in keys:
            if before[key] != after[key]:
                raise SystemExit(f"row {index} {key}: {before[key]!r} != {after[key]!r}")
        if after["champion_hue"] != manager_hue(after.get("champion_id")):
            raise SystemExit(f"row {index} champion_hue drifted")
        if after["last_chair_hue"] != manager_hue(after.get("last_chair_id")):
            raise SystemExit(f"row {index} last_chair_hue drifted")
    print(f"rows={len(served)} sql_columns={len(keys)} match")


if __name__ == "__main__":
    main()
