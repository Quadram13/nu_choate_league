-- Player weeks: lineups, full pool, replacement level, VORP, bench, careers.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_all_league,
    v_player_career,
    v_bench,
    v_vorp_season,
    v_player_vorp,
    v_replacement_weeks,
    v_pool_weeks,
    v_player_weeks
CASCADE;

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

CREATE VIEW v_all_league AS
WITH started AS (
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
    FROM v_player_weeks
    WHERE started
        AND position IS NOT NULL
        AND kind IN ('regular', 'playoff')
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
    FROM v_player_weeks pw
    JOIN best b
        ON b.year = pw.year
        AND b.week = pw.week
        AND b.position = pw.position
    WHERE NOT pw.started
        AND pw.position IS NOT NULL
        AND pw.kind IN ('regular', 'playoff')
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
FROM bench;
