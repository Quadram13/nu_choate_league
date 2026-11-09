-- NFL-team lineup stacks (issue #38).
--
-- A stack is one started quarterback plus at least one started pass-catcher
-- leg on the same matchup side in a posted week, sharing players.nfl_team.
--
-- Pass-catcher legs are players.position in WR, TE, and RB. The slot can be
-- the position or FLEX. An RB counts, and the points are whatever the lineup
-- slot scored, rushing included. There is no target filter. Kickers,
-- defenses, and any other catalog position are not legs. A flex start whose
-- catalog position is DB stays out with them.
--
-- Starters only. lineup_slots.started is true and the slot is not BN or IR.
-- The warehouse has 123 IR rows and none of them are started. The slot
-- filter is the lineup rule, so an IR row cannot become a leg later.
--
-- Club is players.nfl_team after trim. That column is the current club on
-- players.catalog_as_of (2026-11-07 in this warehouse), filled for 856 of
-- 1,298 players. It is the club on that date. A stack in an earlier season
-- is two starters who share that later club. Teammates who have since split
-- are missed. Players who joined the same club after the week are matched.
-- A blank club cannot stack. v_stack_coverage counts how many starter rows
-- have a club, by season.
--
-- Two or more catchers are one stack. Combined points add the quarterback
-- once and each catcher once. v_lineup_stacks is that grain: one row per
-- quarterback on a side. v_lineup_stack_pairs is the pair grain, one row
-- per catcher, and pair_points adds the quarterback again on every catcher.
-- Summing pair_points double-counts the quarterback. The stack total does
-- not. This league has one started QB on every side that has one. A second
-- started QB would form his own stack with the catchers who share his club.
--
-- Posted weeks only (v_posted_weeks). The live leg stays out. vs_median
-- matchups have no lineup rows. kind is kept. Manager-season totals, the
-- scoring comparison, and the record boards use kind = 'regular' so the
-- points sit on the same regular-season team total as official_records.points_for.
-- Playoff and consolation stacks remain on v_lineup_stacks for a separate read.
--
-- Share of PF is combined stack points divided by official_records.points_for.
-- Those points are already inside the team total.
--
-- The scoring comparison is a description of the starts that met the rule.
-- Stacked legs are a selected group: the manager started both players, and
-- the catalog still gives them the same club. It is not a measure of what
-- stacking caused. A blended average also mixes ratios. A stack is one
-- quarterback plus one or more catchers. A full lineup starts one
-- quarterback and several more skill players. Read the quarterback row and
-- the catcher row. The pair average counts the quarterback once per catcher.
--
-- These views do not reference v_player_weeks. Reapplying 60_players.sql
-- does not drop them. Reapplying 05_posted_weeks.sql does (CASCADE). Reapply
-- this file afterward, with 06_finished_seasons.sql and 31_career_grains.sql.

DROP VIEW IF EXISTS v_manager_season_stacks;
DROP VIEW IF EXISTS v_stack_scoring_compare;
DROP VIEW IF EXISTS v_stack_coverage;
DROP VIEW IF EXISTS v_lineup_stacks;
DROP VIEW IF EXISTS v_lineup_stack_pairs;
DROP VIEW IF EXISTS v_stack_starts;

CREATE VIEW v_stack_starts AS
SELECT
    mu.year,
    mu.week,
    mu.kind,
    mu.id AS matchup_id,
    ls.side,
    CASE
        WHEN ls.side = 'home' THEN mu.home_manager_id
        ELSE mu.away_manager_id
    END AS manager_id,
    m.display_name AS manager_name,
    ls.player_id,
    coalesce(p.display_name, ls.player_name) AS player_name,
    p.position,
    ls.slot,
    ls.points,
    NULLIF(btrim(p.nfl_team), '') AS nfl_team
FROM lineup_slots ls
JOIN matchups mu ON mu.id = ls.matchup_id
JOIN v_posted_weeks pw ON pw.year = mu.year AND pw.week = mu.week
JOIN players p ON p.id = ls.player_id
JOIN managers m
    ON m.id = CASE
        WHEN ls.side = 'home' THEN mu.home_manager_id
        ELSE mu.away_manager_id
    END
WHERE ls.started
    AND ls.slot NOT IN ('BN', 'IR')
    AND p.position IN ('QB', 'RB', 'WR', 'TE');

COMMENT ON VIEW v_stack_starts IS
    'Posted-week started QB/RB/WR/TE lineup slots. nfl_team is the catalog club on players.catalog_as_of, not the club during that season. BN and IR are excluded.';

COMMENT ON COLUMN v_stack_starts.nfl_team IS
    'players.nfl_team as of players.catalog_as_of. Blank becomes null. Historical club is not stored.';

-- starts is MATERIALIZED. Inlining v_stack_starts on both sides of this
-- join made the planner nest-loop every lineup slot for every quarterback
-- (about 20s, and the comparison view about 55s). One pass, then a hash
-- join, stays under a tenth of a second.
CREATE VIEW v_lineup_stack_pairs AS
WITH starts AS MATERIALIZED (
    SELECT *
    FROM v_stack_starts
)
SELECT
    q.year,
    q.week,
    q.kind,
    q.matchup_id,
    q.side,
    q.manager_id,
    q.manager_name,
    q.nfl_team,
    q.player_id AS qb_player_id,
    q.player_name AS qb_name,
    q.points AS qb_points,
    c.player_id AS catcher_player_id,
    c.player_name AS catcher_name,
    c.position AS catcher_position,
    c.points AS catcher_points,
    (q.points + c.points)::double precision AS pair_points
FROM starts q
JOIN starts c
    ON c.matchup_id = q.matchup_id
    AND c.side = q.side
    AND c.nfl_team = q.nfl_team
    AND c.position IN ('RB', 'WR', 'TE')
WHERE q.position = 'QB'
    AND q.nfl_team IS NOT NULL;

COMMENT ON VIEW v_lineup_stack_pairs IS
    'One started QB plus one same-club started WR/TE/RB on that matchup side. pair_points counts the quarterback on every catcher.';

CREATE VIEW v_lineup_stacks AS
SELECT
    year,
    week,
    kind,
    matchup_id,
    side,
    manager_id,
    manager_name,
    nfl_team,
    qb_player_id,
    qb_name,
    qb_points,
    count(*)::integer AS catcher_count,
    sum(catcher_points)::double precision AS catcher_points,
    (qb_points + sum(catcher_points))::double precision AS combined_points,
    string_agg(
        catcher_name || ' (' || catcher_position || ')',
        ', ' ORDER BY catcher_points DESC, catcher_player_id
    ) AS catcher_names
FROM v_lineup_stack_pairs
GROUP BY
    year, week, kind, matchup_id, side, manager_id, manager_name, nfl_team,
    qb_player_id, qb_name, qb_points;

COMMENT ON VIEW v_lineup_stacks IS
    'One stack per started QB on a side with at least one same-club WR/TE/RB. Combined points add the QB once. Two catchers are one stack, not two.';

CREATE VIEW v_manager_season_stacks AS
WITH regular AS (
    SELECT *
    FROM v_lineup_stacks
    WHERE kind = 'regular'
),
agg AS (
    SELECT
        year,
        manager_id,
        count(*)::integer AS stack_weeks,
        sum(combined_points)::double precision AS combined_points,
        count(*) FILTER (WHERE catcher_count >= 2)::integer AS multi_catcher_weeks
    FROM regular
    GROUP BY year, manager_id
),
best AS (
    SELECT DISTINCT ON (year, manager_id)
        year,
        manager_id,
        week AS best_week,
        matchup_id AS best_matchup_id,
        combined_points AS best_combined,
        qb_player_id AS best_qb_player_id,
        qb_name AS best_qb_name,
        catcher_names AS best_catcher_names,
        catcher_count AS best_catcher_count,
        nfl_team AS best_nfl_team
    FROM regular
    ORDER BY year, manager_id, combined_points DESC, week, matchup_id, qb_player_id
)
SELECT
    r.year,
    r.manager_id,
    m.display_name AS manager_name,
    ts.team_name,
    coalesce(agg.stack_weeks, 0)::integer AS stack_weeks,
    coalesce(agg.combined_points, 0)::double precision AS combined_points,
    r.points_for,
    CASE
        WHEN r.points_for > 0 THEN coalesce(agg.combined_points, 0) / r.points_for
    END AS stack_share,
    coalesce(agg.multi_catcher_weeks, 0)::integer AS multi_catcher_weeks,
    best.best_week,
    best.best_matchup_id,
    best.best_combined,
    best.best_qb_player_id,
    best.best_qb_name,
    best.best_catcher_names,
    best.best_catcher_count,
    best.best_nfl_team
FROM official_records r
JOIN managers m ON m.id = r.manager_id
LEFT JOIN team_seasons ts ON ts.year = r.year AND ts.manager_id = r.manager_id
LEFT JOIN agg ON agg.year = r.year AND agg.manager_id = r.manager_id
LEFT JOIN best ON best.year = r.year AND best.manager_id = r.manager_id;

COMMENT ON VIEW v_manager_season_stacks IS
    'Regular-season stack weeks, combined points (QB counted once), and that sum divided by official points_for. Zero-stack seasons are included.';

CREATE VIEW v_stack_scoring_compare AS
WITH regular_starts AS (
    SELECT *
    FROM v_stack_starts
    WHERE kind = 'regular'
),
stacked_qb AS (
    SELECT matchup_id, side, qb_player_id
    FROM v_lineup_stacks
    WHERE kind = 'regular'
),
stacked_catcher AS (
    SELECT DISTINCT matchup_id, side, catcher_player_id
    FROM v_lineup_stack_pairs
    WHERE kind = 'regular'
),
labeled AS (
    SELECT
        s.points,
        s.nfl_team IS NOT NULL AS clubbed,
        CASE WHEN s.position = 'QB' THEN 'QB' ELSE 'catcher' END AS role,
        CASE
            WHEN s.position = 'QB' AND q.qb_player_id IS NOT NULL THEN true
            WHEN s.position <> 'QB' AND c.catcher_player_id IS NOT NULL THEN true
            ELSE false
        END AS stacked
    FROM regular_starts s
    LEFT JOIN stacked_qb q
        ON q.matchup_id = s.matchup_id
        AND q.side = s.side
        AND q.qb_player_id = s.player_id
    LEFT JOIN stacked_catcher c
        ON c.matchup_id = s.matchup_id
        AND c.side = s.side
        AND c.catcher_player_id = s.player_id
),
starter_rows AS (
    SELECT 'starter'::text AS grain, 'all'::text AS population, role,
        count(*)::integer AS starts,
        sum(points)::double precision AS points,
        avg(points)::double precision AS avg_points
    FROM labeled
    GROUP BY role
    UNION ALL
    SELECT 'starter', 'clubbed', role,
        count(*)::integer,
        sum(points)::double precision,
        avg(points)::double precision
    FROM labeled
    WHERE clubbed
    GROUP BY role
    UNION ALL
    SELECT 'starter', 'stacked', role,
        count(*)::integer,
        sum(points)::double precision,
        avg(points)::double precision
    FROM labeled
    WHERE stacked
    GROUP BY role
    UNION ALL
    SELECT 'starter', 'all', 'skill',
        count(*)::integer,
        sum(points)::double precision,
        avg(points)::double precision
    FROM labeled
    UNION ALL
    SELECT 'starter', 'clubbed', 'skill',
        count(*)::integer,
        sum(points)::double precision,
        avg(points)::double precision
    FROM labeled
    WHERE clubbed
    UNION ALL
    SELECT 'starter', 'stacked', 'skill',
        count(*)::integer,
        sum(points)::double precision,
        avg(points)::double precision
    FROM labeled
    WHERE stacked
)
SELECT grain, population, role, starts, points, avg_points
FROM starter_rows
UNION ALL
SELECT
    'pair'::text,
    'stacked'::text,
    'pair'::text,
    count(*)::integer,
    sum(pair_points)::double precision,
    avg(pair_points)::double precision
FROM v_lineup_stack_pairs
WHERE kind = 'regular';

COMMENT ON VIEW v_stack_scoring_compare IS
    'Regular-season starter averages for stacked QB and WR/TE/RB starts versus all such starts and versus clubbed starts. Pair row averages QB+catcher and counts the QB once per catcher. Description of a selected group, not a cause.';

CREATE VIEW v_stack_coverage AS
WITH starts AS (
    SELECT
        mu.year,
        s.platform,
        mu.kind,
        p.position,
        NULLIF(btrim(p.nfl_team), '') IS NOT NULL AS clubbed,
        pw.week IS NOT NULL AS posted
    FROM lineup_slots ls
    JOIN matchups mu ON mu.id = ls.matchup_id
    JOIN seasons s ON s.year = mu.year
    LEFT JOIN players p ON p.id = ls.player_id
    LEFT JOIN v_posted_weeks pw ON pw.year = mu.year AND pw.week = mu.week
    WHERE ls.started
        AND ls.slot NOT IN ('BN', 'IR')
)
SELECT
    year,
    platform,
    count(*)::integer AS starter_rows,
    count(*) FILTER (WHERE clubbed)::integer AS starter_with_club,
    count(*) FILTER (WHERE position IN ('QB', 'RB', 'WR', 'TE'))::integer AS skill_rows,
    count(*) FILTER (
        WHERE position IN ('QB', 'RB', 'WR', 'TE') AND clubbed
    )::integer AS skill_with_club,
    count(*) FILTER (WHERE position = 'QB')::integer AS qb_rows,
    count(*) FILTER (WHERE position = 'QB' AND clubbed)::integer AS qb_with_club,
    count(*) FILTER (WHERE position IN ('RB', 'WR', 'TE'))::integer AS catcher_rows,
    count(*) FILTER (
        WHERE position IN ('RB', 'WR', 'TE') AND clubbed
    )::integer AS catcher_with_club,
    count(*) FILTER (WHERE posted)::integer AS posted_starter_rows,
    count(*) FILTER (WHERE posted AND clubbed)::integer AS posted_starter_with_club,
    count(*) FILTER (
        WHERE posted AND kind = 'regular' AND position IN ('QB', 'RB', 'WR', 'TE')
    )::integer AS regular_skill_rows,
    count(*) FILTER (
        WHERE posted
            AND kind = 'regular'
            AND position IN ('QB', 'RB', 'WR', 'TE')
            AND clubbed
    )::integer AS regular_skill_with_club,
    count(*) FILTER (
        WHERE posted AND kind = 'regular' AND position = 'QB'
    )::integer AS regular_qb_rows,
    count(*) FILTER (
        WHERE posted AND kind = 'regular' AND position = 'QB' AND clubbed
    )::integer AS regular_qb_with_club,
    count(*) FILTER (
        WHERE posted AND kind = 'regular' AND position IN ('RB', 'WR', 'TE')
    )::integer AS regular_catcher_rows,
    count(*) FILTER (
        WHERE posted
            AND kind = 'regular'
            AND position IN ('RB', 'WR', 'TE')
            AND clubbed
    )::integer AS regular_catcher_with_club,
    count(*) FILTER (
        WHERE position IS NULL OR position NOT IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')
    )::integer AS other_rows
FROM starts
GROUP BY year, platform;

COMMENT ON VIEW v_stack_coverage IS
    'Started lineup rows with a catalog club, by season. Starter rows include every week. Regular skill rows are the posted regular-season population stacks can see. ESPN years are missing the club more often than Sleeper years.';
