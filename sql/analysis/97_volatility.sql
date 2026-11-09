-- Weekly volatility for players and managers.
-- Facts only: player_week_scores, week_scores, seasons, players, managers.
--
-- Sample. A player-week counts when it is a non-zero score or a start
-- (a started zero is a goose egg; an unstarted zero is a bye or an inactive
-- roster hold and is not a game). A manager-week counts for every team
-- total on a posted week, paired or not — a playoff bye still posted a
-- lineup. Weeks after seasons.through_week are ignored, matching the
-- record book (2024 and 2025 week 18 are stored and uncounted).
--
-- Posted week. The predicate lives in v_posted_weeks: median team total
-- at least 40, and not past seasons.through_week. This view is that set.
-- 2026 volatility is the posted weeks only. partial_season is
-- through_week < 17 (completed Sleeper seasons store last_scored_leg 17;
-- ESPN history stores NULL).
--
-- Spread. stddev_samp (n-1), not stddev_pop. One week has no spread
-- (NULL, not a fake 0). 2026 is a partial sample, and a career is a
-- sample of weeks, so the sample deviation is the one that matches.
-- Median is percentile_cont(0.5): the average of the two middle weeks
-- when the count is even. CV is sample stddev / mean, NULL when the
-- mean is not positive or the stddev is NULL.
--
-- Boom and bust, one league-wide rule at whichever window the row is
-- (this season, or the career): boom when points >= 1.5 * that mean,
-- bust when points <= 0.5 * that mean. Rates are NULL unless the mean
-- is positive and at least two weeks were scored. A week can be neither.
-- It cannot be both while the mean is positive.
--
-- Why not the other two common rules. On this sample (posted weeks,
-- skill positions, 1,539 player-seasons with at least 8 scored weeks):
--   * Fixed 20 / 5 ranks positions. Share of weeks >= 20 is QB 24.5%,
--     RB 10.0%, WR 9.6%, TE 4.2%, DEF 3.2%, K 1.5%. Share <= 5 is
--     TE 51.1%, DEF 47.7%, RB 42.6%, WR 39.7%, K 31.7%, QB 19.3%.
--     The >=20 rate correlates -0.27 with coefficient of variation.
--   * Mean +/- 1 sample stddev is about 16.5% boom everywhere (sd of
--     that rate is 5.6 points) and correlates -0.07 with CV. It restates
--     a normal tail. It does not separate a steady 15 from a coin-flip.
--   * 1.5x / 0.5x tracks the spread: boom rates run 0% to 53.3%
--     (mean 20.1%), corr(CV, boom) = +0.43, corr(CV, bust) = +0.63,
--     corr(CV, either) = +0.63.
-- The same rule on manager seasons (CV only 0.09 to 0.29, 56 seasons
-- of 8+ weeks) fires rarely: mean boom rate 0.6%, max 12.5%, still
-- corr +0.44 with CV. Team consistency is read from stddev and CV;
-- boom/bust stays the same definition instead of a second threshold.
--
-- Best and worst break ties toward the earlier year, then the earlier
-- week. Best-3 share is NULL with fewer than 3 weeks or a non-positive
-- point total. Deviation on v_player_week_deviation and
-- v_manager_week_deviation is points minus that season's own mean.

DROP VIEW IF EXISTS
    v_player_volatility_career,
    v_manager_volatility_career,
    v_player_volatility_season,
    v_manager_volatility_season,
    v_player_week_deviation,
    v_manager_week_deviation,
    v_player_volatility_weeks,
    v_manager_volatility_weeks,
    v_volatility_posted_weeks
CASCADE;

CREATE VIEW v_volatility_posted_weeks AS
SELECT year, week
FROM v_posted_weeks;

COMMENT ON VIEW v_volatility_posted_weeks IS
    'Posted weeks (v_posted_weeks). Median team total at least 40, and not past seasons.through_week.';

CREATE VIEW v_player_volatility_weeks AS
SELECT
    s.year,
    s.week,
    s.player_id,
    coalesce(p.display_name, s.player_name) AS player_name,
    coalesce(p.position, s.position) AS position,
    s.points,
    s.started,
    s.rostered,
    s.manager_id,
    (sz.through_week IS NOT NULL AND sz.through_week < 17) AS partial_season,
    sz.through_week
FROM player_week_scores s
JOIN v_volatility_posted_weeks pw
    ON pw.year = s.year
    AND pw.week = s.week
JOIN seasons sz ON sz.year = s.year
LEFT JOIN players p ON p.id = s.player_id
WHERE s.points <> 0 OR s.started;

COMMENT ON VIEW v_player_volatility_weeks IS
    'Player-weeks in the volatility sample: posted weeks with a non-zero score or a start.';

CREATE VIEW v_player_week_deviation AS
WITH stats AS (
    SELECT
        year,
        player_id,
        avg(points) AS season_mean,
        stddev_samp(points) AS season_stddev,
        count(*) AS season_weeks
    FROM v_player_volatility_weeks
    GROUP BY year, player_id
)
SELECT
    w.year,
    w.week,
    w.player_id,
    w.player_name,
    w.position,
    w.points,
    w.started,
    w.rostered,
    w.manager_id,
    w.partial_season,
    w.through_week,
    s.season_weeks,
    s.season_mean,
    s.season_stddev,
    w.points - s.season_mean AS deviation,
    CASE
        WHEN s.season_weeks < 2 OR s.season_mean <= 0 THEN NULL
        WHEN w.points >= 1.5 * s.season_mean THEN TRUE
        ELSE FALSE
    END AS is_boom,
    CASE
        WHEN s.season_weeks < 2 OR s.season_mean <= 0 THEN NULL
        WHEN w.points <= 0.5 * s.season_mean THEN TRUE
        ELSE FALSE
    END AS is_bust
FROM v_player_volatility_weeks w
JOIN stats s
    ON s.year = w.year
    AND s.player_id = w.player_id;

COMMENT ON VIEW v_player_week_deviation IS
    'deviation is points minus the player season mean. is_boom / is_bust use 1.5x and 0.5x that mean, NULL when fewer than 2 weeks or the mean is not positive.';

CREATE VIEW v_manager_volatility_weeks AS
SELECT
    w.year,
    w.week,
    w.manager_id,
    m.display_name,
    w.points,
    w.paired,
    (sz.through_week IS NOT NULL AND sz.through_week < 17) AS partial_season,
    sz.through_week
FROM week_scores w
JOIN v_volatility_posted_weeks pw
    ON pw.year = w.year
    AND pw.week = w.week
JOIN seasons sz ON sz.year = w.year
JOIN managers m ON m.id = w.manager_id;

COMMENT ON VIEW v_manager_volatility_weeks IS
    'Manager-weeks in the volatility sample: every team total on a posted week, including unpaired playoff byes.';

CREATE VIEW v_manager_week_deviation AS
WITH stats AS (
    SELECT
        year,
        manager_id,
        avg(points) AS season_mean,
        stddev_samp(points) AS season_stddev,
        count(*) AS season_weeks
    FROM v_manager_volatility_weeks
    GROUP BY year, manager_id
)
SELECT
    w.year,
    w.week,
    w.manager_id,
    w.display_name,
    w.points,
    w.paired,
    w.partial_season,
    w.through_week,
    s.season_weeks,
    s.season_mean,
    s.season_stddev,
    w.points - s.season_mean AS deviation,
    CASE
        WHEN s.season_weeks < 2 OR s.season_mean <= 0 THEN NULL
        WHEN w.points >= 1.5 * s.season_mean THEN TRUE
        ELSE FALSE
    END AS is_boom,
    CASE
        WHEN s.season_weeks < 2 OR s.season_mean <= 0 THEN NULL
        WHEN w.points <= 0.5 * s.season_mean THEN TRUE
        ELSE FALSE
    END AS is_bust
FROM v_manager_volatility_weeks w
JOIN stats s
    ON s.year = w.year
    AND s.manager_id = w.manager_id;

COMMENT ON VIEW v_manager_week_deviation IS
    'deviation is team points minus that manager season mean. Boom and bust are 1.5x and 0.5x that mean.';

CREATE VIEW v_player_volatility_season AS
WITH ranked AS (
    SELECT
        d.*,
        row_number() OVER (
            PARTITION BY d.year, d.player_id
            ORDER BY d.points DESC, d.week, d.player_id
        ) AS best_rank,
        row_number() OVER (
            PARTITION BY d.year, d.player_id
            ORDER BY d.points ASC, d.week, d.player_id
        ) AS worst_rank
    FROM v_player_week_deviation d
)
SELECT
    year,
    player_id,
    max(player_name) AS player_name,
    max(position) AS position,
    count(*) AS weeks_scored,
    count(*) FILTER (WHERE started) AS started_weeks,
    sum(points) AS points_sum,
    avg(points) AS mean_points,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY points) AS median_points,
    stddev_samp(points) AS stddev_points,
    CASE
        WHEN avg(points) > 0 AND count(*) >= 2
        THEN stddev_samp(points) / avg(points)
    END AS cv,
    max(points) FILTER (WHERE best_rank = 1) AS best_points,
    max(year) FILTER (WHERE best_rank = 1) AS best_year,
    max(week) FILTER (WHERE best_rank = 1) AS best_week,
    max(points) FILTER (WHERE worst_rank = 1) AS worst_points,
    max(year) FILTER (WHERE worst_rank = 1) AS worst_year,
    max(week) FILTER (WHERE worst_rank = 1) AS worst_week,
    CASE
        WHEN count(*) >= 3 THEN sum(points) FILTER (WHERE best_rank <= 3)
    END AS best3_points,
    CASE
        WHEN count(*) >= 3 AND sum(points) > 0
        THEN sum(points) FILTER (WHERE best_rank <= 3) / sum(points)
    END AS best3_share,
    CASE
        WHEN avg(points) > 0 AND count(*) >= 2
        THEN count(*) FILTER (WHERE is_boom)
    END AS boom_weeks,
    CASE
        WHEN avg(points) > 0 AND count(*) >= 2
        THEN count(*) FILTER (WHERE is_bust)
    END AS bust_weeks,
    CASE
        WHEN avg(points) > 0 AND count(*) >= 2
        THEN count(*) FILTER (WHERE is_boom)::double precision / count(*)
    END AS boom_rate,
    CASE
        WHEN avg(points) > 0 AND count(*) >= 2
        THEN count(*) FILTER (WHERE is_bust)::double precision / count(*)
    END AS bust_rate,
    bool_or(partial_season) AS partial_season,
    max(through_week) AS through_week
FROM ranked
GROUP BY year, player_id;

COMMENT ON VIEW v_player_volatility_season IS
    'Player-season volatility. stddev_samp, CV = sd/mean, boom >= 1.5x mean, bust <= 0.5x mean, best-3 share of season points. partial_season marks 2026 while through_week < 17.';

CREATE VIEW v_manager_volatility_season AS
WITH ranked AS (
    SELECT
        d.*,
        row_number() OVER (
            PARTITION BY d.year, d.manager_id
            ORDER BY d.points DESC, d.week, d.manager_id
        ) AS best_rank,
        row_number() OVER (
            PARTITION BY d.year, d.manager_id
            ORDER BY d.points ASC, d.week, d.manager_id
        ) AS worst_rank
    FROM v_manager_week_deviation d
)
SELECT
    year,
    manager_id,
    max(display_name) AS display_name,
    count(*) AS weeks_scored,
    sum(points) AS points_sum,
    avg(points) AS mean_points,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY points) AS median_points,
    stddev_samp(points) AS stddev_points,
    CASE
        WHEN avg(points) > 0 AND count(*) >= 2
        THEN stddev_samp(points) / avg(points)
    END AS cv,
    max(points) FILTER (WHERE best_rank = 1) AS best_points,
    max(year) FILTER (WHERE best_rank = 1) AS best_year,
    max(week) FILTER (WHERE best_rank = 1) AS best_week,
    max(points) FILTER (WHERE worst_rank = 1) AS worst_points,
    max(year) FILTER (WHERE worst_rank = 1) AS worst_year,
    max(week) FILTER (WHERE worst_rank = 1) AS worst_week,
    CASE
        WHEN count(*) >= 3 THEN sum(points) FILTER (WHERE best_rank <= 3)
    END AS best3_points,
    CASE
        WHEN count(*) >= 3 AND sum(points) > 0
        THEN sum(points) FILTER (WHERE best_rank <= 3) / sum(points)
    END AS best3_share,
    CASE
        WHEN avg(points) > 0 AND count(*) >= 2
        THEN count(*) FILTER (WHERE is_boom)
    END AS boom_weeks,
    CASE
        WHEN avg(points) > 0 AND count(*) >= 2
        THEN count(*) FILTER (WHERE is_bust)
    END AS bust_weeks,
    CASE
        WHEN avg(points) > 0 AND count(*) >= 2
        THEN count(*) FILTER (WHERE is_boom)::double precision / count(*)
    END AS boom_rate,
    CASE
        WHEN avg(points) > 0 AND count(*) >= 2
        THEN count(*) FILTER (WHERE is_bust)::double precision / count(*)
    END AS bust_rate,
    bool_or(partial_season) AS partial_season,
    max(through_week) AS through_week
FROM ranked
GROUP BY year, manager_id;

COMMENT ON VIEW v_manager_volatility_season IS
    'Manager-season volatility of weekly team totals. Same definitions as v_player_volatility_season.';

CREATE VIEW v_player_volatility_career AS
WITH tagged AS (
    SELECT
        w.*,
        avg(w.points) OVER (PARTITION BY w.player_id) AS career_mean,
        stddev_samp(w.points) OVER (PARTITION BY w.player_id) AS career_stddev,
        count(*) OVER (PARTITION BY w.player_id) AS career_weeks,
        row_number() OVER (
            PARTITION BY w.player_id
            ORDER BY w.points DESC, w.year, w.week
        ) AS best_rank,
        row_number() OVER (
            PARTITION BY w.player_id
            ORDER BY w.points ASC, w.year, w.week
        ) AS worst_rank
    FROM v_player_volatility_weeks w
)
SELECT
    player_id,
    max(player_name) AS player_name,
    max(position) AS position,
    count(DISTINCT year) AS seasons,
    count(*) AS weeks_scored,
    count(*) FILTER (WHERE started) AS started_weeks,
    sum(points) AS points_sum,
    max(career_mean) AS mean_points,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY points) AS median_points,
    max(career_stddev) AS stddev_points,
    CASE
        WHEN max(career_mean) > 0 AND count(*) >= 2
        THEN max(career_stddev) / max(career_mean)
    END AS cv,
    max(points) FILTER (WHERE best_rank = 1) AS best_points,
    max(year) FILTER (WHERE best_rank = 1) AS best_year,
    max(week) FILTER (WHERE best_rank = 1) AS best_week,
    max(points) FILTER (WHERE worst_rank = 1) AS worst_points,
    max(year) FILTER (WHERE worst_rank = 1) AS worst_year,
    max(week) FILTER (WHERE worst_rank = 1) AS worst_week,
    CASE
        WHEN count(*) >= 3 THEN sum(points) FILTER (WHERE best_rank <= 3)
    END AS best3_points,
    CASE
        WHEN count(*) >= 3 AND sum(points) > 0
        THEN sum(points) FILTER (WHERE best_rank <= 3) / sum(points)
    END AS best3_share,
    CASE
        WHEN max(career_mean) > 0 AND count(*) >= 2
        THEN count(*) FILTER (
            WHERE career_weeks >= 2
                AND career_mean > 0
                AND points >= 1.5 * career_mean
        )
    END AS boom_weeks,
    CASE
        WHEN max(career_mean) > 0 AND count(*) >= 2
        THEN count(*) FILTER (
            WHERE career_weeks >= 2
                AND career_mean > 0
                AND points <= 0.5 * career_mean
        )
    END AS bust_weeks,
    CASE
        WHEN max(career_mean) > 0 AND count(*) >= 2
        THEN count(*) FILTER (
            WHERE points >= 1.5 * career_mean
        )::double precision / count(*)
    END AS boom_rate,
    CASE
        WHEN max(career_mean) > 0 AND count(*) >= 2
        THEN count(*) FILTER (
            WHERE points <= 0.5 * career_mean
        )::double precision / count(*)
    END AS bust_rate,
    bool_or(partial_season) AS includes_partial
FROM tagged
GROUP BY player_id;

COMMENT ON VIEW v_player_volatility_career IS
    'Career volatility over the same player-weeks. Boom and bust are judged against the career mean, not each season mean. includes_partial is true when 2026 is in the sample.';

CREATE VIEW v_manager_volatility_career AS
WITH tagged AS (
    SELECT
        w.*,
        avg(w.points) OVER (PARTITION BY w.manager_id) AS career_mean,
        stddev_samp(w.points) OVER (PARTITION BY w.manager_id) AS career_stddev,
        count(*) OVER (PARTITION BY w.manager_id) AS career_weeks,
        row_number() OVER (
            PARTITION BY w.manager_id
            ORDER BY w.points DESC, w.year, w.week
        ) AS best_rank,
        row_number() OVER (
            PARTITION BY w.manager_id
            ORDER BY w.points ASC, w.year, w.week
        ) AS worst_rank
    FROM v_manager_volatility_weeks w
)
SELECT
    manager_id,
    max(display_name) AS display_name,
    count(DISTINCT year) AS seasons,
    count(*) AS weeks_scored,
    sum(points) AS points_sum,
    max(career_mean) AS mean_points,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY points) AS median_points,
    max(career_stddev) AS stddev_points,
    CASE
        WHEN max(career_mean) > 0 AND count(*) >= 2
        THEN max(career_stddev) / max(career_mean)
    END AS cv,
    max(points) FILTER (WHERE best_rank = 1) AS best_points,
    max(year) FILTER (WHERE best_rank = 1) AS best_year,
    max(week) FILTER (WHERE best_rank = 1) AS best_week,
    max(points) FILTER (WHERE worst_rank = 1) AS worst_points,
    max(year) FILTER (WHERE worst_rank = 1) AS worst_year,
    max(week) FILTER (WHERE worst_rank = 1) AS worst_week,
    CASE
        WHEN count(*) >= 3 THEN sum(points) FILTER (WHERE best_rank <= 3)
    END AS best3_points,
    CASE
        WHEN count(*) >= 3 AND sum(points) > 0
        THEN sum(points) FILTER (WHERE best_rank <= 3) / sum(points)
    END AS best3_share,
    CASE
        WHEN max(career_mean) > 0 AND count(*) >= 2
        THEN count(*) FILTER (
            WHERE career_weeks >= 2
                AND career_mean > 0
                AND points >= 1.5 * career_mean
        )
    END AS boom_weeks,
    CASE
        WHEN max(career_mean) > 0 AND count(*) >= 2
        THEN count(*) FILTER (
            WHERE career_weeks >= 2
                AND career_mean > 0
                AND points <= 0.5 * career_mean
        )
    END AS bust_weeks,
    CASE
        WHEN max(career_mean) > 0 AND count(*) >= 2
        THEN count(*) FILTER (
            WHERE points >= 1.5 * career_mean
        )::double precision / count(*)
    END AS boom_rate,
    CASE
        WHEN max(career_mean) > 0 AND count(*) >= 2
        THEN count(*) FILTER (
            WHERE points <= 0.5 * career_mean
        )::double precision / count(*)
    END AS bust_rate,
    bool_or(partial_season) AS includes_partial
FROM tagged
GROUP BY manager_id;

COMMENT ON VIEW v_manager_volatility_career IS
    'Career volatility of weekly team totals. Boom and bust are judged against the career mean.';
