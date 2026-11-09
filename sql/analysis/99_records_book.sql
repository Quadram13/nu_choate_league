-- Records book expansion (issue #42).
--
-- Two views. Career and single-season player counting stay on
-- v_player_counting_season and v_player_counting_career (97_counting_summaries.sql).
-- This file does not rebuild those sums.
--
-- v_lineup_week_counting is one starting lineup in one posted week.
-- A starter is lineup_slots.started with a slot other than BN or IR.
-- Yards are the sum of player_week_counting_stats for those player ids.
-- A starter with no counting row adds zero (coalesce). Quarterback
-- rushing yards are in rush_yd. Kickers and defenses stay in the lineup
-- and usually add zero to these three totals. The record boards keep
-- kind = 'regular'. Playoff and consolation rows stay on the view.
--
-- v_playoff_seed_games is one official playoff matchup week where both
-- managers are in season_playoff_managers. Seed is v_standings_official.rank,
-- so the seed and the standings rank are the same number. Consolation
-- games, and playoff-kind games against a team outside the field, stay off.
-- A two-week series is still two rows here. The page sums a series.
--
-- 2026 has no champion. Season-grain chapters filter v_finished_seasons
-- themselves. This file does not.
--
-- Reapplying 05_posted_weeks.sql drops v_lineup_week_counting (CASCADE on
-- v_posted_weeks). Reapply this file afterward, with 06_finished_seasons.sql,
-- 31_career_grains.sql, and 62_lineup_stacks.sql.
-- Reapplying 20_standings.sql drops v_playoff_seed_games (CASCADE on
-- v_standings_official). Reapply this file afterward.

DROP VIEW IF EXISTS v_lineup_week_counting;
DROP VIEW IF EXISTS v_playoff_seed_games;

CREATE VIEW v_lineup_week_counting AS
SELECT
    mu.year,
    mu.week,
    mu.kind,
    mu.id AS matchup_id,
    CASE
        WHEN ls.side = 'home' THEN mu.home_manager_id
        ELSE mu.away_manager_id
    END AS manager_id,
    m.display_name AS manager_name,
    sum(coalesce(c.rush_yd, 0))::integer AS rush_yd,
    sum(coalesce(c.rec_yd, 0))::integer AS rec_yd,
    sum(coalesce(c.pass_yd, 0))::integer AS pass_yd,
    count(*)::integer AS starters,
    count(c.player_id)::integer AS counted_starters
FROM lineup_slots ls
JOIN matchups mu ON mu.id = ls.matchup_id
JOIN v_posted_weeks pw ON pw.year = mu.year AND pw.week = mu.week
JOIN managers m
    ON m.id = CASE
        WHEN ls.side = 'home' THEN mu.home_manager_id
        ELSE mu.away_manager_id
    END
LEFT JOIN player_week_counting_stats c
    ON c.year = mu.year
    AND c.week = mu.week
    AND c.player_id = ls.player_id
WHERE ls.started
    AND ls.slot NOT IN ('BN', 'IR')
GROUP BY
    mu.year,
    mu.week,
    mu.kind,
    mu.id,
    ls.side,
    mu.home_manager_id,
    mu.away_manager_id,
    m.display_name;

COMMENT ON VIEW v_lineup_week_counting IS
    'Posted-week starting lineup counting totals. Starters are lineup_slots.started and not BN or IR. rush_yd, rec_yd, and pass_yd sum player_week_counting_stats; a starter with no counting row adds zero.';

CREATE VIEW v_playoff_seed_games AS
SELECT
    mu.year,
    mu.week,
    mu.id AS matchup_id,
    mu.home_manager_id AS home_id,
    hm.display_name AS home_name,
    hs.rank::integer AS home_seed,
    mu.home_points,
    mu.away_manager_id AS away_id,
    am.display_name AS away_name,
    aws.rank::integer AS away_seed,
    mu.away_points
FROM matchups mu
JOIN season_playoff_managers hp
    ON hp.year = mu.year AND hp.manager_id = mu.home_manager_id
JOIN season_playoff_managers ap
    ON ap.year = mu.year AND ap.manager_id = mu.away_manager_id
JOIN v_standings_official hs
    ON hs.year = mu.year AND hs.manager_id = mu.home_manager_id
JOIN v_standings_official aws
    ON aws.year = mu.year AND aws.manager_id = mu.away_manager_id
JOIN managers hm ON hm.id = mu.home_manager_id
JOIN managers am ON am.id = mu.away_manager_id
WHERE mu.kind = 'playoff';

COMMENT ON VIEW v_playoff_seed_games IS
    'Official playoff weeks between two season_playoff_managers. home_seed and away_seed are v_standings_official.rank.';

COMMENT ON COLUMN v_playoff_seed_games.home_seed IS
    'Regular-season rank from v_standings_official. Same number as the standings rank.';
