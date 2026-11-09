-- League scoring environment (issue #41).
--
-- Two grains, on purpose.
--
-- Manager-weeks. v_scoring_manager_weeks is one paired team total on a
-- posted regular-season week. That is the same cut the season-page band
-- already uses: v_posted_weeks (median team total at least 40, and not
-- past seasons.through_week) plus a regular matchup with a non-zero side.
-- 2026 keeps the eight posted weeks and leaves the live leg out. Playoff
-- weeks stay out of the distribution, the season table, position share,
-- and the league-week records. Sample standard deviation is stddev_samp.
-- Median and deciles are percentile_cont. Nothing rescales a season.
--
-- Tightest week is the smallest sample standard deviation of that week's
-- team totals. Span (high minus low) is stored beside it and can name a
-- different week. 2025 week 12 is the tightest spread and 2025 week 9 is
-- the narrowest span. Boom week, inside one season, is the highest league
-- total. Team count does not change inside a season here, so that week is
-- also the highest mean. Across seasons the two diverge: 2023 and 2024
-- fielded 10 teams, and 2022, 2025, and 2026 fielded 12. v_scoring_league_week_ranks
-- ranks both the sum and the mean. The page lists every week tied for an
-- extreme. The rank columns break a tie toward the earlier year, then the
-- earlier week.
--
-- Position share. Started points from player_week_scores, grouped by the
-- player's position, on the manager-week grain above. A flex start stays
-- with RB, WR, or TE. Bench points are excluded. lineup_slots by slot
-- would park the flex in its own column, so the share uses position.
-- Starter lines equal league PF in 2022-2025. 2026 week 6 does not:
-- John Wilson's team total is 108.08 and both his started slots and his
-- started player_week_scores sum to 103.08. The five points are on the
-- team total only. The share stays on player position.
--
-- Replacement. v_replacement_weeks already holds the Nth score at the
-- position and the player id, and it keeps every posted week, playoffs
-- included. v_replacement_named selects that id and the player name.
-- v_replacement_season is the mean of those weekly levels. v_replacement_baseline
-- is the same mean across every posted week. That baseline is the audit
-- line recomputed: the audit rounded it to QB ~18.5, WR ~11.5, TE ~10.7,
-- RB ~9.8, K ~9.4, DEF ~5.5.
--
-- Reloading 05_posted_weeks.sql drops v_posted_weeks CASCADE, and reloading
-- 60_players.sql drops v_replacement_weeks CASCADE. Either drop takes these
-- views with it. Reapply this file afterward. Reapply 06_finished_seasons.sql
-- and 31_career_grains.sql after 05, before this file.

DROP VIEW IF EXISTS v_scoring_league_week_ranks;
DROP VIEW IF EXISTS v_scoring_position_share;
DROP VIEW IF EXISTS v_scoring_season;
DROP VIEW IF EXISTS v_replacement_baseline;
DROP VIEW IF EXISTS v_replacement_season;
DROP VIEW IF EXISTS v_replacement_named;
DROP VIEW IF EXISTS v_scoring_league_weeks;
DROP VIEW IF EXISTS v_scoring_manager_weeks;

CREATE VIEW v_scoring_manager_weeks AS
SELECT
    w.year,
    w.week,
    w.manager_id,
    m.display_name,
    w.points
FROM week_scores w
JOIN managers m ON m.id = w.manager_id
JOIN v_posted_weeks pw ON pw.year = w.year AND pw.week = w.week
WHERE w.paired
    AND EXISTS (
        SELECT 1
        FROM matchups mu
        WHERE mu.year = w.year
            AND mu.week = w.week
            AND mu.kind = 'regular'
            AND (mu.home_points <> 0 OR mu.away_points <> 0)
    );

COMMENT ON VIEW v_scoring_manager_weeks IS
    'Paired regular-season manager-weeks on posted weeks. Same cut as the season scoring band.';

CREATE VIEW v_scoring_league_weeks AS
SELECT
    year,
    week,
    CAST(count(*) AS integer) AS managers,
    sum(points) AS league_total,
    avg(points) AS mean_points,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY points) AS median_points,
    min(points) AS low_points,
    max(points) AS high_points,
    stddev_samp(points) AS spread,
    max(points) - min(points) AS point_span
FROM v_scoring_manager_weeks
GROUP BY year, week;

COMMENT ON VIEW v_scoring_league_weeks IS
    'One posted regular week. spread is stddev_samp of team totals. point_span is high minus low. league_total is the sum.';

CREATE VIEW v_scoring_season AS
SELECT
    w.year,
    CAST(count(DISTINCT w.week) AS integer) AS weeks,
    CAST(count(*) AS integer) AS manager_weeks,
    CAST(count(DISTINCT w.manager_id) AS integer) AS managers,
    avg(w.points) AS avg_points,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY w.points) AS median_points,
    stddev_samp(w.points) AS stddev_points,
    min(w.points) AS min_points,
    max(w.points) AS max_points,
    sum(w.points) AS total_pf,
    percentile_cont(0.1) WITHIN GROUP (ORDER BY w.points) AS p10,
    percentile_cont(0.2) WITHIN GROUP (ORDER BY w.points) AS p20,
    percentile_cont(0.3) WITHIN GROUP (ORDER BY w.points) AS p30,
    percentile_cont(0.4) WITHIN GROUP (ORDER BY w.points) AS p40,
    percentile_cont(0.6) WITHIN GROUP (ORDER BY w.points) AS p60,
    percentile_cont(0.7) WITHIN GROUP (ORDER BY w.points) AS p70,
    percentile_cont(0.8) WITHIN GROUP (ORDER BY w.points) AS p80,
    percentile_cont(0.9) WITHIN GROUP (ORDER BY w.points) AS p90,
    NOT coalesce(fin.regular_season_complete, false) AS partial_season
FROM v_scoring_manager_weeks w
LEFT JOIN v_finished_seasons fin ON fin.year = w.year
GROUP BY w.year, fin.regular_season_complete;

COMMENT ON VIEW v_scoring_season IS
    'Manager-week distribution for one season: mean, median, sample stddev, deciles, and total league PF. partial_season when the regular season is not finished.';

CREATE VIEW v_scoring_position_share AS
WITH started AS (
    SELECT
        s.year,
        coalesce(s.position, 'UNK') AS position,
        sum(s.points) AS points,
        CAST(count(*) AS integer) AS starts
    FROM player_week_scores s
    JOIN v_scoring_league_weeks w
        ON w.year = s.year
        AND w.week = s.week
    WHERE s.started
    GROUP BY s.year, coalesce(s.position, 'UNK')
)
SELECT
    year,
    position,
    points,
    starts,
    points / nullif(sum(points) OVER (PARTITION BY year), 0) AS share
FROM started;

COMMENT ON VIEW v_scoring_position_share IS
    'Share of started player_week_scores points by player position, on posted regular weeks. Flex stays with RB, WR, or TE. Starter lines equal league PF except a 5-point team-total remainder in 2026 week 6.';

CREATE VIEW v_scoring_league_week_ranks AS
SELECT
    year,
    week,
    managers,
    league_total,
    mean_points,
    median_points,
    low_points,
    high_points,
    spread,
    point_span,
    rank() OVER (ORDER BY league_total DESC, year, week) AS total_high_rank,
    rank() OVER (ORDER BY league_total ASC, year, week) AS total_low_rank,
    rank() OVER (ORDER BY mean_points DESC, year, week) AS mean_high_rank,
    rank() OVER (ORDER BY mean_points ASC, year, week) AS mean_low_rank
FROM v_scoring_league_weeks;

COMMENT ON VIEW v_scoring_league_week_ranks IS
    'League-week records. total_* ranks the sum of manager totals. mean_* ranks the average. Tie-break is the earlier year, then the earlier week.';

CREATE VIEW v_replacement_named AS
SELECT
    r.year,
    r.week,
    r.position,
    r.n_starters,
    r.replacement,
    r.replacement_player_id,
    coalesce(p.display_name, r.replacement_player_id) AS replacement_player_name
FROM v_replacement_weeks r
LEFT JOIN players p ON p.id = r.replacement_player_id;

COMMENT ON VIEW v_replacement_named IS
    'v_replacement_weeks with the replacement player id selected and named. Every posted week, playoffs included.';

CREATE VIEW v_replacement_season AS
SELECT
    year,
    position,
    avg(replacement) AS replacement,
    CAST(count(*) AS integer) AS weeks,
    avg(n_starters) AS starters
FROM v_replacement_named
GROUP BY year, position;

COMMENT ON VIEW v_replacement_season IS
    'Mean weekly replacement level by position for one season. Weeks match v_replacement_weeks, playoffs included.';

CREATE VIEW v_replacement_baseline AS
SELECT
    position,
    avg(replacement) AS replacement,
    CAST(count(*) AS integer) AS weeks,
    avg(n_starters) AS starters
FROM v_replacement_named
GROUP BY position;

COMMENT ON VIEW v_replacement_baseline IS
    'Mean weekly replacement level by position across every posted week. This is the recomputed audit baseline.';
