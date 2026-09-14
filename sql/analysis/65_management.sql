-- Optimal lineup from the rostered pool, and start/sit (management).
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_management_career,
    v_management_season,
    v_start_sit,
    v_management_weeks
CASCADE;

DROP MATERIALIZED VIEW IF EXISTS v_optimal_slots CASCADE;
DROP VIEW IF EXISTS v_optimal_slots CASCADE;
DROP VIEW IF EXISTS v_lineup_shape CASCADE;

-- League starter shape. Observed counts win if a season started more
-- (e.g. two FLEX); otherwise 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 K, 1 DEF.
CREATE VIEW v_lineup_shape AS
WITH
defaults AS (
    SELECT * FROM (
        VALUES
            ('QB', 1),
            ('RB', 2),
            ('WR', 2),
            ('TE', 1),
            ('FLEX', 1),
            ('K', 1),
            ('DEF', 1)
    ) AS d(slot, n)
),
observed AS (
    SELECT year, slot, max(n) AS n
    FROM (
        SELECT year, week, manager_id, slot, count(*) AS n
        FROM v_player_weeks
        WHERE started
            AND slot NOT IN ('BN', 'IR')
            AND kind IN ('regular', 'playoff', 'consolation')
        GROUP BY year, week, manager_id, slot
    ) counts
    GROUP BY year, slot
)
SELECT
    y.year,
    d.slot,
    greatest(coalesce(o.n, 0), d.n) AS n
FROM seasons y
CROSS JOIN defaults d
LEFT JOIN observed o ON o.year = y.year AND o.slot = d.slot;

-- Best legal lineup from that week's roster. Dedicated slots first, then
-- FLEX is the highest leftover RB/WR/TE. Actual points for management %
-- come from week_scores (not the started flag), so ESPN still works if a
-- slot was mis-tagged.
-- Snapshot: leftover and start/sit read this. Computing it live is ~0.3s per season.
CREATE MATERIALIZED VIEW v_optimal_slots AS
WITH roster AS (
    SELECT DISTINCT ON (pw.year, pw.week, pw.manager_id, pw.player_id)
        pw.year,
        pw.week,
        pw.kind,
        pw.matchup_id,
        pw.manager_id,
        pw.manager_name,
        pw.player_id,
        pw.player_name,
        pw.position,
        pw.points,
        pw.started
    FROM v_player_weeks pw
    WHERE pw.kind IN ('regular', 'playoff', 'consolation')
        AND pw.position IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')
    ORDER BY
        pw.year,
        pw.week,
        pw.manager_id,
        pw.player_id,
        pw.started DESC,
        pw.points DESC
),
ranked AS (
    SELECT
        r.*,
        row_number() OVER (
            PARTITION BY r.year, r.week, r.manager_id, r.position
            ORDER BY r.points DESC, r.player_id
        ) AS pos_rank
    FROM roster r
),
locked AS (
    SELECT r.*, s.slot AS opt_slot
    FROM ranked r
    JOIN v_lineup_shape s ON s.year = r.year AND s.slot = r.position
    WHERE r.pos_rank <= s.n
),
flex_pool AS (
    SELECT r.*
    FROM ranked r
    JOIN v_lineup_shape s ON s.year = r.year AND s.slot = r.position
    WHERE r.position IN ('RB', 'WR', 'TE')
        AND r.pos_rank > s.n
),
flex_ranked AS (
    SELECT
        f.*,
        row_number() OVER (
            PARTITION BY f.year, f.week, f.manager_id
            ORDER BY f.points DESC, f.player_id
        ) AS flex_rank
    FROM flex_pool f
),
flexed AS (
    SELECT f.*, 'FLEX'::text AS opt_slot
    FROM flex_ranked f
    JOIN v_lineup_shape s ON s.year = f.year AND s.slot = 'FLEX'
    WHERE f.flex_rank <= s.n
),
slots AS (
    SELECT
        year, week, kind, matchup_id, manager_id, manager_name,
        player_id, player_name, position, points, started, opt_slot
    FROM locked
    UNION ALL
    SELECT
        year, week, kind, matchup_id, manager_id, manager_name,
        player_id, player_name, position, points, started, opt_slot
    FROM flexed
)
SELECT
    year, week, kind, matchup_id, manager_id, manager_name,
    player_id, player_name, position, points, started, opt_slot
FROM slots
WITH NO DATA;

CREATE INDEX v_optimal_slots_year ON v_optimal_slots (year);
CREATE INDEX v_optimal_slots_week ON v_optimal_slots (year, week, manager_id);
CREATE INDEX v_optimal_slots_player ON v_optimal_slots (year, week, manager_id, player_id);

CREATE VIEW v_management_weeks AS
SELECT
    o.year,
    o.week,
    o.kind,
    o.matchup_id,
    o.manager_id,
    o.manager_name,
    w.points AS actual_points,
    sum(o.points) AS optimal_points,
    CASE
        WHEN sum(o.points) = 0 THEN NULL
        ELSE w.points / sum(o.points)
    END AS management_pct,
    sum(o.points) - w.points AS left_on_bench
FROM v_optimal_slots o
JOIN week_scores w
    ON w.year = o.year
    AND w.week = o.week
    AND w.manager_id = o.manager_id
GROUP BY
    o.year, o.week, o.kind, o.matchup_id,
    o.manager_id, o.manager_name, w.points;

CREATE VIEW v_start_sit AS
SELECT
    o.year,
    o.week,
    o.kind,
    o.matchup_id,
    o.manager_id,
    o.manager_name,
    o.player_id,
    o.player_name,
    o.position,
    o.opt_slot,
    o.points,
    'should_start'::text AS call
FROM v_optimal_slots o
WHERE NOT o.started
UNION ALL
SELECT
    pw.year,
    pw.week,
    pw.kind,
    pw.matchup_id,
    pw.manager_id,
    pw.manager_name,
    pw.player_id,
    pw.player_name,
    pw.position,
    pw.slot AS opt_slot,
    pw.points,
    'should_sit'::text AS call
FROM v_player_weeks pw
WHERE pw.started
    AND pw.kind IN ('regular', 'playoff', 'consolation')
    AND NOT EXISTS (
        SELECT 1
        FROM v_optimal_slots o
        WHERE o.year = pw.year
            AND o.week = pw.week
            AND o.manager_id = pw.manager_id
            AND o.player_id = pw.player_id
    );

CREATE VIEW v_management_season AS
SELECT
    year,
    manager_id,
    manager_name,
    count(*) AS weeks,
    sum(actual_points) AS actual_points,
    sum(optimal_points) AS optimal_points,
    sum(left_on_bench) AS left_on_bench,
    avg(management_pct) AS management_pct,
    rank() OVER (
        PARTITION BY year
        ORDER BY avg(management_pct) DESC NULLS LAST, manager_id
    ) AS coach_rank
FROM v_management_weeks
WHERE kind = 'regular'
GROUP BY year, manager_id, manager_name;

CREATE VIEW v_management_career AS
SELECT
    manager_id,
    manager_name,
    count(*) AS seasons,
    sum(weeks) AS weeks,
    sum(actual_points) AS actual_points,
    sum(optimal_points) AS optimal_points,
    sum(left_on_bench) AS left_on_bench,
    CASE
        WHEN sum(optimal_points) = 0 THEN NULL
        ELSE sum(actual_points) / sum(optimal_points)
    END AS management_pct
FROM v_management_season
GROUP BY manager_id, manager_name;
