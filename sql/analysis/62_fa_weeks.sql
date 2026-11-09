-- Unowned production (issue #36). Left on the wire.
--
-- v_fa_weeks is one posted player-week with rostered = false. VORP is
-- points minus that week's replacement, the same Nth-starter line as
-- v_player_vorp. pool.py drops a zero-score free-agent week, so that
-- week is not a row here. A position outside QB/RB/WR/TE/K/DEF has no
-- replacement row, so those weeks are absent, the same cut v_vorp_season
-- makes. The season CTEs are MATERIALIZED so a leaderboard does not
-- recompute replacement once per player.
--
-- v_fa_season is one v_vorp_season player with fa_weeks > 0. fa_points
-- and stored_vorp sum the stored unowned weeks. fa_vorp is copied from
-- v_vorp_season, which also charges each missing posted week as
-- 0 minus replacement. stored_vorp + missing_vorp = fa_vorp.
-- A fully rostered season has fa_vorp of 0 aside from float dust, so
-- leaving those rows out does not change a year sum.
--
-- v_fa_career sums those seasons. never_rostered is zero rostered weeks
-- across every v_vorp_season row, including a fully rostered year that
-- this file does not list. Reapplying 60_players.sql drops v_pool_weeks
-- and these views with it. Reapply this file after that.

DROP VIEW IF EXISTS v_fa_career;
DROP VIEW IF EXISTS v_fa_season;
DROP VIEW IF EXISTS v_fa_weeks;

CREATE VIEW v_fa_weeks AS
SELECT
    p.year,
    p.week,
    p.player_id,
    p.player_name,
    p.position,
    p.points,
    r.n_starters,
    r.replacement,
    r.replacement_player_id,
    coalesce(rp.display_name, r.replacement_player_id) AS replacement_player_name,
    p.points - r.replacement AS vorp
FROM v_pool_weeks p
JOIN v_replacement_weeks r
    ON r.year = p.year
    AND r.week = p.week
    AND r.position = p.position
JOIN v_posted_weeks pw
    ON pw.year = p.year
    AND pw.week = p.week
LEFT JOIN players rp ON rp.id = r.replacement_player_id
WHERE NOT p.rostered;

COMMENT ON VIEW v_fa_weeks IS
    'Posted player-weeks with rostered = false, and VORP against that week''s replacement. A zero-score free-agent week is not stored.';

CREATE VIEW v_fa_season AS
WITH stored AS MATERIALIZED (
    SELECT
        year,
        player_id,
        position,
        sum(points) AS fa_points,
        count(*)::bigint AS stored_weeks,
        sum(vorp) AS stored_vorp
    FROM v_fa_weeks
    GROUP BY year, player_id, position
),
best AS MATERIALIZED (
    SELECT DISTINCT ON (year, player_id, position)
        year,
        player_id,
        position,
        week AS best_week,
        points AS best_points,
        vorp AS best_vorp
    FROM v_fa_weeks
    ORDER BY year, player_id, position, points DESC, vorp DESC, week
)
SELECT
    v.year,
    v.player_id,
    v.player_name,
    v.position,
    v.fa_weeks,
    v.rostered_weeks,
    v.lineup_weeks,
    coalesce(stored.fa_points, 0) AS fa_points,
    coalesce(stored.stored_weeks, 0) AS stored_weeks,
    coalesce(stored.stored_vorp, 0) AS stored_vorp,
    v.fa_vorp - coalesce(stored.stored_vorp, 0) AS missing_vorp,
    v.fa_vorp,
    best.best_week,
    best.best_points,
    best.best_vorp,
    v.rostered_weeks = 0 AS never_rostered
FROM v_vorp_season v
LEFT JOIN stored
    ON stored.year = v.year
    AND stored.player_id = v.player_id
    AND stored.position = v.position
LEFT JOIN best
    ON best.year = v.year
    AND best.player_id = v.player_id
    AND best.position = v.position
WHERE v.fa_weeks > 0;

COMMENT ON VIEW v_fa_season IS
    'Unowned season totals. fa_vorp matches v_vorp_season.fa_vorp. missing_vorp is 0 minus replacement on posted weeks with no stored row.';

CREATE VIEW v_fa_career AS
WITH sums AS MATERIALIZED (
    SELECT
        player_id,
        max(player_name) AS player_name,
        count(*)::bigint AS seasons,
        min(year) AS first_year,
        max(year) AS last_year,
        sum(fa_weeks)::bigint AS fa_weeks,
        sum(fa_points) AS fa_points,
        sum(stored_vorp) AS stored_vorp,
        sum(missing_vorp) AS missing_vorp,
        sum(fa_vorp) AS fa_vorp,
        max(best_points) AS best_points
    FROM v_fa_season
    GROUP BY player_id
),
pos AS MATERIALIZED (
    SELECT DISTINCT ON (player_id)
        player_id,
        position
    FROM v_fa_season
    ORDER BY player_id, fa_vorp DESC, year DESC, position
),
owned AS MATERIALIZED (
    SELECT
        player_id,
        sum(rostered_weeks)::bigint AS rostered_weeks
    FROM v_vorp_season
    GROUP BY player_id
)
SELECT
    sums.player_id,
    sums.player_name,
    pos.position,
    sums.seasons,
    sums.first_year,
    sums.last_year,
    sums.fa_weeks,
    owned.rostered_weeks,
    sums.fa_points,
    sums.stored_vorp,
    sums.missing_vorp,
    sums.fa_vorp,
    sums.best_points,
    owned.rostered_weeks = 0 AS never_rostered
FROM sums
JOIN pos ON pos.player_id = sums.player_id
JOIN owned ON owned.player_id = sums.player_id;

COMMENT ON VIEW v_fa_career IS
    'Career sum of v_fa_season. never_rostered means zero rostered weeks in v_vorp_season, fully rostered seasons included.';
