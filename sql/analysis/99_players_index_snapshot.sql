-- Players index snapshots (issue #85).
--
-- /players was spending about 1.5s of a 2.3s response in five statements
-- that recompute plain views on every request. Measured on a warm hit
-- (NU_CHOATE_PERF, one profile request, not the page median):
--   career join over v_player_index     518ms   EXPLAIN 587ms
--   v_player_season plus managers       301ms   EXPLAIN 346ms
--   v_player_volatility_season          295ms   EXPLAIN 318ms
--   v_vorp_season gap aggregate         206ms   EXPLAIN 243ms
--   v_player_volatility_career           76ms
-- The fact tables are a few megabytes and already indexed. The volatility
-- plan's scan of player_week_scores was 3ms; the rest is sort, hash, and
-- window work over the whole view, already in shared buffers. A new index
-- does not remove that.
--
-- These five snapshots are the statements the index page reads. They are
-- new names, so 60_players.sql can keep DROP VIEW on v_player_index and
-- v_vorp_season. Same-name conversion of those two would have to edit that
-- DROP, and that file's CASCADE on v_pool_weeks takes the fa snapshots
-- with it.
--
-- Age is not stored. EXTRACT(YEAR FROM age(birth_date)) moves on a
-- birthday, so the page query computes it from the stored birth_date.
--
-- Load applies this file after 97_volatility.sql, WITH NO DATA, then
-- refresh_analysis fills the five names. A hand apply has to refresh
-- them in the same session before commit (scripts/perf/apply-players.ps1).
--
-- Reapply map, from rolled-back DROP ... CASCADE (nothing committed):
--   v_player_index                -> v_players_index_career
--   v_player_season               -> v_players_index_season
--   v_vorp_season                 -> v_players_index_gap, and also
--       v_player_season, v_players_index_season, v_player_index,
--       v_players_index_career, v_fa_season, v_fa_career.
--       v_fa_weeks stays; it depends on v_pool_weeks.
--   v_player_volatility_season    -> v_players_index_vol_season
--   v_player_volatility_career    -> v_players_index_vol_career
-- 60_players.sql drops the player views and v_pool_weeks in one CASCADE,
-- so it also drops v_fa_weeks. It does not drop the volatility snapshots.
-- 97_volatility.sql drops both volatility views and both volatility
-- snapshots. Run this file again after either, then refresh the five.
-- Nothing in the fa chain depends on these names.

DO $drop_players_index$
DECLARE
    target text;
    kind "char";
BEGIN
    FOREACH target IN ARRAY ARRAY[
        'v_players_index_career',
        'v_players_index_season',
        'v_players_index_gap',
        'v_players_index_vol_career',
        'v_players_index_vol_season'
    ]
    LOOP
        kind := NULL;
        SELECT c.relkind INTO kind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = target;
        IF kind = 'v' THEN
            EXECUTE format('DROP VIEW %I', target);
        ELSIF kind = 'm' THEN
            EXECUTE format('DROP MATERIALIZED VIEW %I', target);
        ELSIF kind IS NOT NULL THEN
            RAISE EXCEPTION 'refusing to drop % (%)', target, kind;
        END IF;
    END LOOP;
END
$drop_players_index$;

CREATE MATERIALIZED VIEW v_players_index_career AS
SELECT
    i.player_id,
    i.player_name,
    i.position,
    i.seasons,
    i.first_year,
    i.last_year,
    i.starts,
    i.bench_weeks,
    i.starter_points,
    i.rostered_weeks,
    i.fa_weeks,
    i.started_vorp,
    i.own_pct,
    i.lineup_weeks,
    i.times_drafted,
    i.times_added,
    i.times_traded,
    coalesce(r.rings, 0) AS rings,
    coalesce(r.title_starts, 0) AS title_starts,
    coalesce(r.champ_roster_weeks, 0) AS champ_roster_weeks,
    coalesce(jm.managers, 0) AS managers,
    p.birth_date,
    p.height_in,
    p.weight_lb,
    p.rookie_year
FROM v_player_index i
LEFT JOIN players p ON p.id = i.player_id
LEFT JOIN v_player_rings r ON r.player_id = i.player_id
LEFT JOIN v_player_managers jm ON jm.player_id = i.player_id
WITH NO DATA;

COMMENT ON MATERIALIZED VIEW v_players_index_career IS
    'Players-index career rows. Age is computed at read time from birth_date. Snapshot, refreshed by load.';

CREATE MATERIALIZED VIEW v_players_index_season AS
SELECT
    s.year,
    s.player_id,
    s.player_name,
    s.position,
    s.rostered_weeks,
    s.starts,
    s.fa_weeks,
    s.points,
    s.started_points,
    s.vorp,
    s.started_vorp,
    s.own_pct,
    s.manager_id,
    s.owner_name,
    s.owned_weeks,
    s.lineup_weeks,
    coalesce(jm.managers, 0) AS managers
FROM v_player_season s
LEFT JOIN v_player_managers_season jm
    ON jm.year = s.year AND jm.player_id = s.player_id
WITH NO DATA;

COMMENT ON MATERIALIZED VIEW v_players_index_season IS
    'Players-index season rows, including the manager count. Snapshot, refreshed by load.';

CREATE MATERIALIZED VIEW v_players_index_gap AS
WITH seasons AS (
    SELECT player_id, rostered_weeks, points
    FROM v_vorp_season
),
players AS (
    SELECT
        player_id,
        sum(rostered_weeks) AS rostered_weeks,
        sum(points) AS points
    FROM seasons
    GROUP BY player_id
)
SELECT
    count(*) FILTER (WHERE rostered_weeks = 0) AS excluded_seasons,
    count(*) FILTER (
        WHERE rostered_weeks = 0 AND points <> 0
    ) AS excluded_seasons_scored,
    (
        SELECT count(*)
        FROM players
        WHERE rostered_weeks = 0
    ) AS excluded_players,
    (
        SELECT count(*)
        FROM players
        WHERE rostered_weeks = 0 AND points <> 0
    ) AS excluded_players_scored
FROM seasons
WITH NO DATA;

COMMENT ON MATERIALIZED VIEW v_players_index_gap IS
    'One row: seasons and players the starter index drops for zero rostered weeks. Snapshot of the v_vorp_season aggregate, refreshed by load.';

CREATE MATERIALIZED VIEW v_players_index_vol_career AS
SELECT
    player_id,
    weeks_scored,
    mean_points,
    stddev_points,
    cv,
    boom_rate,
    best_points,
    best_year,
    best_week,
    includes_partial
FROM v_player_volatility_career
WITH NO DATA;

COMMENT ON MATERIALIZED VIEW v_players_index_vol_career IS
    'Career volatility columns the players index attaches. Snapshot, refreshed by load. The player page still reads v_player_volatility_career.';

CREATE MATERIALIZED VIEW v_players_index_vol_season AS
SELECT
    year,
    player_id,
    weeks_scored,
    mean_points,
    stddev_points,
    cv,
    boom_rate,
    best_points,
    best_year,
    best_week,
    partial_season
FROM v_player_volatility_season
WITH NO DATA;

COMMENT ON MATERIALIZED VIEW v_players_index_vol_season IS
    'Season volatility columns the players index attaches. Snapshot, refreshed by load. The player page still reads v_player_volatility_season.';
