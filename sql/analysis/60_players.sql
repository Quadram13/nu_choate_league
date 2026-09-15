-- Player weeks: lineups, full pool, replacement level, VORP, bench, careers.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_player_index,
    v_player_season,
    v_ownership_season,
    v_player_career,
    v_bench,
    v_vorp_season,
    v_player_vorp,
    v_replacement_weeks,
    v_pool_weeks,
    v_player_weeks
CASCADE;

DROP MATERIALIZED VIEW IF EXISTS v_all_league CASCADE;
DROP VIEW IF EXISTS v_all_league CASCADE;

CREATE VIEW v_player_weeks AS
SELECT
    mu.year,
    mu.week,
    mu.kind,
    mu.id AS matchup_id,
    CASE WHEN ls.side = 'home' THEN mu.home_manager_id ELSE mu.away_manager_id END AS manager_id,
    m.display_name AS manager_name,
    ls.player_id,
    coalesce(p.display_name, ls.player_name) AS player_name,
    p.position,
    ls.slot,
    ls.started,
    ls.points
FROM lineup_slots ls
JOIN matchups mu ON mu.id = ls.matchup_id
LEFT JOIN managers m
    ON m.id = CASE WHEN ls.side = 'home' THEN mu.home_manager_id ELSE mu.away_manager_id END
LEFT JOIN players p ON p.id = ls.player_id
WHERE CASE WHEN ls.side = 'home' THEN mu.home_manager_id ELSE mu.away_manager_id END IS NOT NULL;

-- Full NFL pool (rostered + FA), scored in this league's settings.
-- Replacement = the Nth best scorer at the position, where N is how many
-- players actually started there that week (flex starts count at RB/WR/TE).
CREATE VIEW v_pool_weeks AS
SELECT
    s.year,
    s.week,
    s.player_id,
    coalesce(p.display_name, s.player_name) AS player_name,
    coalesce(s.position, p.position) AS position,
    s.points,
    s.rostered,
    s.started,
    s.manager_id
FROM player_week_scores s
LEFT JOIN players p ON p.id = s.player_id;

CREATE VIEW v_replacement_weeks AS
WITH ranked AS (
    SELECT
        year,
        week,
        position,
        player_id,
        points,
        row_number() OVER (
            PARTITION BY year, week, position
            ORDER BY points DESC, player_id
        ) AS rnk
    FROM v_pool_weeks
    WHERE position IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')
),
starters AS (
    SELECT
        year,
        week,
        position,
        count(*) AS n_starters
    FROM v_pool_weeks
    WHERE started
        AND position IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')
    GROUP BY year, week, position
)
SELECT
    s.year,
    s.week,
    s.position,
    s.n_starters,
    r.points AS replacement,
    r.player_id AS replacement_player_id
FROM starters s
JOIN ranked r
    ON r.year = s.year
    AND r.week = s.week
    AND r.position = s.position
    AND r.rnk = greatest(s.n_starters, 1);

CREATE VIEW v_player_vorp AS
SELECT
    p.year,
    p.week,
    p.player_id,
    p.player_name,
    p.position,
    p.points,
    p.rostered,
    p.started,
    p.manager_id,
    r.n_starters,
    r.replacement,
    p.points - r.replacement AS vorp
FROM v_pool_weeks p
JOIN v_replacement_weeks r
    ON r.year = p.year
    AND r.week = p.week
    AND r.position = p.position;

CREATE VIEW v_vorp_season AS
SELECT
    year,
    player_id,
    max(player_name) AS player_name,
    position,
    count(*) AS weeks,
    count(*) FILTER (WHERE rostered) AS rostered_weeks,
    count(*) FILTER (WHERE started) AS starts,
    count(*) FILTER (WHERE NOT rostered) AS fa_weeks,
    coalesce(sum(points), 0) AS points,
    coalesce(sum(points) FILTER (WHERE started), 0) AS started_points,
    count(*) FILTER (WHERE rostered AND NOT started) AS bench_weeks,
    coalesce(sum(points) FILTER (WHERE rostered AND NOT started), 0) AS bench_points,
    coalesce(sum(vorp), 0) AS vorp,
    coalesce(sum(vorp) FILTER (WHERE started), 0) AS started_vorp,
    coalesce(sum(vorp) FILTER (WHERE NOT rostered), 0) AS fa_vorp
FROM v_player_vorp
GROUP BY year, player_id, position;

CREATE VIEW v_bench AS
SELECT
    year,
    week,
    manager_id,
    manager_name,
    sum(points) FILTER (WHERE started) AS started_points,
    sum(points) FILTER (WHERE NOT started) AS bench_points,
    sum(points) AS roster_points
FROM v_player_weeks
WHERE kind IN ('regular', 'playoff', 'consolation')
GROUP BY year, week, manager_id, manager_name;

CREATE VIEW v_player_career AS
SELECT
    pw.player_id,
    coalesce(p.display_name, max(pw.player_name)) AS player_name,
    p.position,
    count(*) FILTER (WHERE pw.started) AS starts,
    count(*) FILTER (WHERE NOT pw.started) AS bench_weeks,
    coalesce(sum(pw.points) FILTER (WHERE pw.started), 0) AS starter_points,
    count(DISTINCT pw.year) AS seasons,
    min(pw.year) AS first_year,
    max(pw.year) AS last_year,
    coalesce(d.times_drafted, 0) AS times_drafted,
    coalesce(mv.adds, 0) AS times_added,
    coalesce(mv.drops, 0) AS times_dropped,
    coalesce(tr.times_traded, 0) AS times_traded
FROM v_player_weeks pw
LEFT JOIN players p ON p.id = pw.player_id
LEFT JOIN (
    SELECT player_id, count(*) AS times_drafted
    FROM draft_picks
    GROUP BY player_id
) d ON d.player_id = pw.player_id
LEFT JOIN (
    SELECT
        player_id,
        count(*) FILTER (WHERE direction = 'add') AS adds,
        count(*) FILTER (WHERE direction = 'drop') AS drops
    FROM v_moves
    WHERE type <> 'trade'
    GROUP BY player_id
) mv ON mv.player_id = pw.player_id
LEFT JOIN (
    SELECT player_id, count(*) AS times_traded
    FROM v_trades
    GROUP BY player_id
) tr ON tr.player_id = pw.player_id
GROUP BY pw.player_id, p.display_name, p.position, d.times_drafted, mv.adds, mv.drops, tr.times_traded;

-- Snapshot: week chairs and career chair counts. Computing live is ~0.8s.
CREATE MATERIALIZED VIEW v_all_league AS
WITH weeks AS (
    SELECT
        year,
        week,
        CASE
            WHEN slot IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF') THEN slot
            WHEN position IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF') THEN position
            WHEN position IN ('DB', 'CB', 'LB', 'DL', 'DE', 'DT', 'S', 'SS', 'FS', 'IDP') THEN 'WR'
            WHEN position = 'FB' THEN 'RB'
            ELSE NULL
        END AS position,
        player_id,
        player_name,
        manager_id,
        manager_name,
        points,
        started,
        kind
    FROM v_player_weeks
    WHERE kind IN ('regular', 'playoff')
),
started AS (
    SELECT
        year,
        week,
        position,
        player_id,
        player_name,
        manager_id,
        manager_name,
        points,
        rank() OVER (
            PARTITION BY year, week, position
            ORDER BY points DESC, player_id
        ) AS high_rank,
        rank() OVER (
            PARTITION BY year, week, position
            ORDER BY points ASC, player_id
        ) AS low_rank
    FROM weeks
    WHERE started
        AND position IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')
),
best AS (
    SELECT year, week, position, points AS best_points
    FROM started
    WHERE high_rank = 1
),
bench AS (
    SELECT
        pw.year,
        pw.week,
        pw.position,
        pw.player_id,
        pw.player_name,
        pw.manager_id,
        pw.manager_name,
        pw.points
    FROM weeks pw
    JOIN best b
        ON b.year = pw.year
        AND b.week = pw.week
        AND b.position = pw.position
    WHERE NOT pw.started
        AND pw.position IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')
        AND pw.points > b.best_points
)
SELECT
    year,
    week,
    position,
    'all_league' AS kind,
    player_id,
    player_name,
    manager_id,
    manager_name,
    points
FROM started
WHERE high_rank = 1
UNION ALL
SELECT
    year,
    week,
    position,
    'busch',
    player_id,
    player_name,
    manager_id,
    manager_name,
    points
FROM started
WHERE low_rank = 1
UNION ALL
SELECT
    year,
    week,
    position,
    'benched_all_star',
    player_id,
    player_name,
    manager_id,
    manager_name,
    points
FROM bench
WITH NO DATA;

CREATE INDEX v_all_league_year_week ON v_all_league (year, week);
CREATE INDEX v_all_league_manager ON v_all_league (manager_id);
CREATE INDEX v_all_league_kind ON v_all_league (kind);

-- Who rostered a player, by season. A player can have several owners.
CREATE VIEW v_ownership_season AS
SELECT
    p.year,
    p.player_id,
    p.manager_id,
    m.display_name AS manager_name,
    count(*) AS weeks,
    count(*) FILTER (WHERE p.started) AS starts,
    coalesce(sum(p.points), 0) AS points
FROM v_pool_weeks p
JOIN managers m ON m.id = p.manager_id
WHERE p.rostered
GROUP BY p.year, p.player_id, p.manager_id, m.display_name;

-- Rostered players in a season, with the manager who held them longest.
CREATE VIEW v_player_season AS
SELECT
    v.year,
    v.player_id,
    v.player_name,
    v.position,
    v.weeks,
    v.rostered_weeks,
    v.starts,
    v.fa_weeks,
    v.points,
    v.started_points,
    v.bench_weeks,
    v.bench_points,
    v.vorp,
    CASE
        WHEN v.weeks = 0 THEN NULL
        ELSE v.rostered_weeks::double precision / v.weeks
    END AS own_pct,
    o.manager_id,
    o.manager_name AS owner_name,
    o.weeks AS owned_weeks
FROM v_vorp_season v
LEFT JOIN LATERAL (
    SELECT manager_id, manager_name, weeks
    FROM v_ownership_season o
    WHERE o.player_id = v.player_id
        AND o.year = v.year
    ORDER BY weeks DESC, manager_id
    LIMIT 1
) o ON true
WHERE v.rostered_weeks > 0;

CREATE VIEW v_player_index AS
SELECT
    c.player_id,
    c.player_name,
    c.position,
    c.seasons,
    c.first_year,
    c.last_year,
    c.starts,
    c.bench_weeks,
    c.starter_points,
    c.times_drafted,
    c.times_added,
    c.times_dropped,
    c.times_traded,
    v.weeks,
    v.rostered_weeks,
    v.fa_weeks,
    v.vorp,
    CASE
        WHEN coalesce(v.weeks, 0) = 0 THEN NULL
        ELSE v.rostered_weeks::double precision / v.weeks
    END AS own_pct
FROM v_player_career c
LEFT JOIN (
    SELECT
        player_id,
        sum(weeks) AS weeks,
        sum(rostered_weeks) AS rostered_weeks,
        sum(fa_weeks) AS fa_weeks,
        sum(vorp) AS vorp
    FROM v_vorp_season
    GROUP BY player_id
) v ON v.player_id = c.player_id
WHERE c.player_id IS NOT NULL
    AND (c.starts > 0 OR coalesce(v.rostered_weeks, 0) > 0);
