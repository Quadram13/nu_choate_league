-- Fa-chain statement timings. \timing lines are one run each (a ballpark).
-- Decisions use scripts/perf/time-fa.ps1, which repeats these shapes.
\timing on
\echo '=== Q1: players_index career query (full, as served) ==='
SELECT
    i.player_id, i.player_name, i.position, i.seasons, i.first_year, i.last_year,
    i.starts, i.bench_weeks, i.starter_points, i.rostered_weeks, i.fa_weeks,
    i.started_vorp, i.own_pct, i.lineup_weeks, i.times_drafted, i.times_added,
    i.times_traded,
    coalesce(r.rings, 0) AS rings,
    coalesce(r.title_starts, 0) AS title_starts,
    coalesce(r.champ_roster_weeks, 0) AS champ_roster_weeks,
    coalesce(jm.managers, 0) AS managers,
    p.birth_date, p.height_in, p.weight_lb, p.rookie_year,
    CASE WHEN p.birth_date IS NULL THEN NULL
         ELSE EXTRACT(YEAR FROM age(p.birth_date))::integer END AS age_years
FROM v_player_index i
LEFT JOIN players p ON p.id = i.player_id
LEFT JOIN v_player_rings r ON r.player_id = i.player_id
LEFT JOIN v_player_managers jm ON jm.player_id = i.player_id
ORDER BY i.starter_points DESC, i.started_vorp DESC, i.player_name;
\echo '=== Q2: _fa_week_leaders top 10 over v_fa_weeks ==='
SELECT year, week, player_id, player_name, position, points, vorp
FROM v_fa_weeks
ORDER BY points DESC, vorp DESC, year, week, player_name
LIMIT 10;
\echo '=== Q3: _fa_best_week_by_season (DISTINCT ON) ==='
SELECT DISTINCT ON (year) year, week, player_id, player_name, position, points, vorp
FROM v_fa_weeks
ORDER BY year DESC, points DESC, vorp DESC, week, player_name;
\echo '=== Q4: v_fa_season leaders ==='
SELECT year, player_id, player_name, fa_vorp FROM v_fa_season ORDER BY fa_vorp DESC LIMIT 10;
\echo '=== Q5: raw chain costs ==='
SELECT count(*) FROM v_fa_weeks;
SELECT count(*) FROM v_pool_weeks;
SELECT count(*) FROM v_replacement_weeks;
\echo '=== Q6: repeat Q2 (cache-warm repeat cost) ==='
SELECT year, week, player_id, player_name, position, points, vorp
FROM v_fa_weeks
ORDER BY points DESC, vorp DESC, year, week, player_name
LIMIT 10;
\echo '=== Q7: v_fa_career leaders ==='
SELECT player_id, player_name, fa_vorp FROM v_fa_career ORDER BY fa_vorp DESC LIMIT 10;
\echo '=== Q8: v_fa_career row count ==='
SELECT count(*) FROM v_fa_career;
