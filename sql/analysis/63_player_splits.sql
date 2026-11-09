-- Player splits (issue #37).
--
-- Grain is one posted roster week in v_player_weeks whose matchup kind is
-- regular or playoff. Consolation is a third kind and stays out. vs_median
-- matchups have no lineup rows. A week the player was not rostered has no
-- lineup row and stays out, including a free-agent week that still has a
-- counting-stat row. The live leg stays out: the week has to be in
-- v_posted_weeks.
--
-- Two cuts of that same set:
--   phase  regular | playoff, from v_player_weeks.kind
--   half   first | second, by week number against the regular-season midpoint
-- Every week in the set is in exactly one phase and exactly one half.
-- Regular plus playoff equals the set. The two halves equal the same set.
--
-- Midpoint. regular_weeks is playoff_start_week - 1, the fantasy regular
-- season, not the 18-week NFL calendar. midpoint is regular_weeks / 2
-- (integer division). The first half is week <= midpoint. The second half
-- is every later week in the set. Playoff weeks land in the second half
-- because they start after the midpoint. An odd regular season keeps the
-- extra week in the second half.
--
-- From season_outcomes.playoff_start_week in this warehouse:
--   2022   14 regular weeks   midpoint 7   playoffs start week 15   ESPN
--   2023   15 regular weeks   midpoint 7   playoffs start week 16   ESPN
--   2024   14 regular weeks   midpoint 7   playoffs start week 15   Sleeper
--   2025   14 regular weeks   midpoint 7   playoffs start week 15   Sleeper
--   2026   14 regular weeks   midpoint 7   playoffs start week 15   Sleeper
-- 2026 is a 14-week regular season here. Only posted weeks count. The live
-- week is not in v_posted_weeks. With weeks 1-8 posted, weeks 1-7 are the
-- first half and week 8 is the second half. Later weeks join when they post.
--
-- games is rostered weeks. points sums v_player_weeks.points on those weeks,
-- bench included, as numeric so the two cuts add to the cent. points_per_game
-- is points / games. It is a rate. The rates do not add across a split.
-- Counting columns sum player_week_counting_stats on the same weeks. They
-- use that table. They do not rebuild the stat map and they do not
-- re-aggregate v_player_counting_season, which is already one row per
-- player-year. counting_games counts counting rows. A zero-point lineup
-- week has no counting row, so counting_games can be lower than games.
-- A _pg column divides by counting_games, the same denominator as
-- v_player_counting_season. Null when counting_games is 0. total_td is
-- pass_td + rush_td + rec_td and leaves out def_td and st_td. g_rush_100,
-- g_rec_100, and g_pass_300 count weeks at or above 100 rush yards, 100
-- receiving yards, and 300 pass yards. g_td_2 counts weeks whose total_td
-- is at least 2. These sums are not v_player_counting_season. That view
-- also includes free-agent weeks and, in 2022-2023, consolation weeks.
--
-- Opponent and home/away are 2022 and 2023 only. The schedule is
-- nfl_team_weeks. The club is players.nfl_team joined through
-- nfl_team_crosswalk (WAS, not ESPN's Wsh). That column is the current
-- club on the catalog snapshot (players.catalog_as_of; 2026-11-07 in this
-- warehouse), not the club in the week. A player who changed clubs is
-- credited with the current club's 2022-2023 opponents and home/away, so
-- a traded player's rows are misattributed. Week-of club is not read from
-- boxscores here. The year predicate is 2022 and 2023, so a later schedule
-- load does not start emitting Sleeper-year rows. Those seasons return no
-- rows. There is no hardcoded external schedule. A bye has no opponent and
-- a null home/away, so it is in neither view. Home plus away, and the
-- opponent rows, each partition the non-bye scheduled weeks inside this
-- rostered regular/playoff set. They do not have to equal the phase total.
-- Defensive DvP is not in these views.
--
-- Reapplying 60_players.sql drops v_player_weeks CASCADE, and reapplying
-- 05_posted_weeks.sql drops v_posted_weeks CASCADE. Both drop this file.
-- Reapply it afterward. Do not reapply 05 or 10 just to refresh it.

DROP VIEW IF EXISTS v_player_site_splits;
DROP VIEW IF EXISTS v_player_opponent_splits;
DROP VIEW IF EXISTS v_player_season_splits;
DROP VIEW IF EXISTS v_player_split_weeks;
DROP VIEW IF EXISTS v_season_split_bounds;

CREATE VIEW v_season_split_bounds AS
SELECT
    s.year,
    o.playoff_start_week,
    o.playoff_start_week - 1 AS regular_weeks,
    (o.playoff_start_week - 1) / 2 AS midpoint
FROM seasons s
JOIN season_outcomes o ON o.year = s.year
WHERE o.playoff_start_week IS NOT NULL
    AND o.playoff_start_week > 1;

COMMENT ON VIEW v_season_split_bounds IS
'Regular-season length and half midpoint per year. regular_weeks is playoff_start_week minus 1. midpoint is that length divided by 2, integer division, so an odd slate keeps the extra week in the second half. 2022 is 14 and 7. 2023 is 15 and 7. 2024 is 14 and 7. 2025 is 14 and 7. 2026 is 14 and 7. The first half is week <= midpoint. Posted weeks only, so 2026 does not include the live leg.';

CREATE VIEW v_player_split_weeks AS
SELECT
    pw.year,
    pw.week,
    pw.player_id,
    coalesce(p.display_name, pw.player_name) AS player_name,
    coalesce(p.position, pw.position) AS position,
    pw.kind AS phase,
    CASE
        WHEN pw.week <= b.midpoint THEN 'first'
        ELSE 'second'
    END AS half,
    pw.points::numeric AS points,
    coalesce(c.pass_cmp, 0) AS pass_cmp,
    coalesce(c.pass_att, 0) AS pass_att,
    coalesce(c.pass_yd, 0) AS pass_yd,
    coalesce(c.pass_td, 0) AS pass_td,
    coalesce(c.pass_int, 0) AS pass_int,
    coalesce(c.rush_att, 0) AS rush_att,
    coalesce(c.rush_yd, 0) AS rush_yd,
    coalesce(c.rush_td, 0) AS rush_td,
    coalesce(c.rec, 0) AS rec,
    coalesce(c.rec_yd, 0) AS rec_yd,
    coalesce(c.rec_td, 0) AS rec_td,
    coalesce(c.rec_tgt, 0) AS rec_tgt,
    coalesce(c.fum_lost, 0) AS fum_lost,
    coalesce(c.pass_2pt, 0) AS pass_2pt,
    coalesce(c.rush_2pt, 0) AS rush_2pt,
    coalesce(c.rec_2pt, 0) AS rec_2pt,
    coalesce(c.pass_fd, 0) AS pass_fd,
    coalesce(c.rush_fd, 0) AS rush_fd,
    coalesce(c.rec_fd, 0) AS rec_fd,
    coalesce(c.pass_rz_att, 0) AS pass_rz_att,
    coalesce(c.rush_rz_att, 0) AS rush_rz_att,
    coalesce(c.rec_rz_tgt, 0) AS rec_rz_tgt,
    coalesce(c.fgm, 0) AS fgm,
    coalesce(c.fga, 0) AS fga,
    coalesce(c.xpm, 0) AS xpm,
    coalesce(c.xpa, 0) AS xpa,
    coalesce(c.fgm_50p, 0) AS fgm_50p,
    coalesce(c.sack, 0) AS sack,
    coalesce(c.def_int, 0) AS def_int,
    coalesce(c.fum_rec, 0) AS fum_rec,
    coalesce(c.def_td, 0) AS def_td,
    coalesce(c.st_td, 0) AS st_td,
    coalesce(c.blk_kick, 0) AS blk_kick,
    coalesce(c.safe, 0) AS safe,
    coalesce(c.pts_allow, 0) AS pts_allow,
    coalesce(c.yds_allow, 0) AS yds_allow,
    coalesce(c.pass_td, 0) + coalesce(c.rush_td, 0) + coalesce(c.rec_td, 0) AS total_td,
    CASE WHEN c.player_id IS NOT NULL AND c.rush_yd >= 100 THEN 1 ELSE 0 END AS g_rush_100,
    CASE WHEN c.player_id IS NOT NULL AND c.rec_yd >= 100 THEN 1 ELSE 0 END AS g_rec_100,
    CASE WHEN c.player_id IS NOT NULL AND c.pass_yd >= 300 THEN 1 ELSE 0 END AS g_pass_300,
    CASE
        WHEN c.player_id IS NOT NULL
            AND (c.pass_td + c.rush_td + c.rec_td) >= 2 THEN 1
        ELSE 0
    END AS g_td_2,
    CASE WHEN c.player_id IS NOT NULL THEN 1 ELSE 0 END AS counting_game
FROM v_player_weeks pw
JOIN v_posted_weeks posted
    ON posted.year = pw.year
    AND posted.week = pw.week
JOIN v_season_split_bounds b ON b.year = pw.year
LEFT JOIN players p ON p.id = pw.player_id
LEFT JOIN player_week_counting_stats c
    ON c.year = pw.year
    AND c.week = pw.week
    AND c.player_id = pw.player_id
WHERE pw.kind IN ('regular', 'playoff')
    AND pw.player_id IS NOT NULL;

COMMENT ON VIEW v_player_split_weeks IS
'One posted regular or playoff roster week, tagged phase and half. Counting columns are 0 when that week has no player_week_counting_stats row. Consolation, vs_median, free-agent weeks, and the live leg are absent.';

CREATE VIEW v_player_season_splits AS
SELECT
    w.year,
    w.player_id,
    max(w.player_name) AS player_name,
    max(w.position) AS position,
    k.split_family,
    k.split_value,
    count(*)::bigint AS games,
    sum(w.points) AS points,
    sum(w.points) / count(*)::numeric AS points_per_game,
    sum(w.counting_game)::bigint AS counting_games,
    sum(w.pass_cmp)::bigint AS pass_cmp,
    sum(w.pass_att)::bigint AS pass_att,
    sum(w.pass_yd)::bigint AS pass_yd,
    sum(w.pass_td)::bigint AS pass_td,
    sum(w.pass_int)::bigint AS pass_int,
    sum(w.rush_att)::bigint AS rush_att,
    sum(w.rush_yd)::bigint AS rush_yd,
    sum(w.rush_td)::bigint AS rush_td,
    sum(w.rec)::bigint AS rec,
    sum(w.rec_yd)::bigint AS rec_yd,
    sum(w.rec_td)::bigint AS rec_td,
    sum(w.rec_tgt)::bigint AS rec_tgt,
    sum(w.fum_lost)::bigint AS fum_lost,
    sum(w.pass_2pt)::bigint AS pass_2pt,
    sum(w.rush_2pt)::bigint AS rush_2pt,
    sum(w.rec_2pt)::bigint AS rec_2pt,
    sum(w.pass_fd)::bigint AS pass_fd,
    sum(w.rush_fd)::bigint AS rush_fd,
    sum(w.rec_fd)::bigint AS rec_fd,
    sum(w.pass_rz_att)::bigint AS pass_rz_att,
    sum(w.rush_rz_att)::bigint AS rush_rz_att,
    sum(w.rec_rz_tgt)::bigint AS rec_rz_tgt,
    sum(w.fgm)::bigint AS fgm,
    sum(w.fga)::bigint AS fga,
    sum(w.xpm)::bigint AS xpm,
    sum(w.xpa)::bigint AS xpa,
    sum(w.fgm_50p)::bigint AS fgm_50p,
    sum(w.sack)::bigint AS sack,
    sum(w.def_int)::bigint AS def_int,
    sum(w.fum_rec)::bigint AS fum_rec,
    sum(w.def_td)::bigint AS def_td,
    sum(w.st_td)::bigint AS st_td,
    sum(w.blk_kick)::bigint AS blk_kick,
    sum(w.safe)::bigint AS safe,
    sum(w.pts_allow)::bigint AS pts_allow,
    sum(w.yds_allow)::bigint AS yds_allow,
    sum(w.total_td)::bigint AS total_td,
    sum(w.pass_cmp)::numeric / nullif(sum(w.counting_game), 0) AS pass_cmp_pg,
    sum(w.pass_att)::numeric / nullif(sum(w.counting_game), 0) AS pass_att_pg,
    sum(w.pass_yd)::numeric / nullif(sum(w.counting_game), 0) AS pass_yd_pg,
    sum(w.pass_td)::numeric / nullif(sum(w.counting_game), 0) AS pass_td_pg,
    sum(w.pass_int)::numeric / nullif(sum(w.counting_game), 0) AS pass_int_pg,
    sum(w.rush_att)::numeric / nullif(sum(w.counting_game), 0) AS rush_att_pg,
    sum(w.rush_yd)::numeric / nullif(sum(w.counting_game), 0) AS rush_yd_pg,
    sum(w.rush_td)::numeric / nullif(sum(w.counting_game), 0) AS rush_td_pg,
    sum(w.rec)::numeric / nullif(sum(w.counting_game), 0) AS rec_pg,
    sum(w.rec_yd)::numeric / nullif(sum(w.counting_game), 0) AS rec_yd_pg,
    sum(w.rec_td)::numeric / nullif(sum(w.counting_game), 0) AS rec_td_pg,
    sum(w.rec_tgt)::numeric / nullif(sum(w.counting_game), 0) AS rec_tgt_pg,
    sum(w.fum_lost)::numeric / nullif(sum(w.counting_game), 0) AS fum_lost_pg,
    sum(w.pass_2pt)::numeric / nullif(sum(w.counting_game), 0) AS pass_2pt_pg,
    sum(w.rush_2pt)::numeric / nullif(sum(w.counting_game), 0) AS rush_2pt_pg,
    sum(w.rec_2pt)::numeric / nullif(sum(w.counting_game), 0) AS rec_2pt_pg,
    sum(w.pass_fd)::numeric / nullif(sum(w.counting_game), 0) AS pass_fd_pg,
    sum(w.rush_fd)::numeric / nullif(sum(w.counting_game), 0) AS rush_fd_pg,
    sum(w.rec_fd)::numeric / nullif(sum(w.counting_game), 0) AS rec_fd_pg,
    sum(w.pass_rz_att)::numeric / nullif(sum(w.counting_game), 0) AS pass_rz_att_pg,
    sum(w.rush_rz_att)::numeric / nullif(sum(w.counting_game), 0) AS rush_rz_att_pg,
    sum(w.rec_rz_tgt)::numeric / nullif(sum(w.counting_game), 0) AS rec_rz_tgt_pg,
    sum(w.fgm)::numeric / nullif(sum(w.counting_game), 0) AS fgm_pg,
    sum(w.fga)::numeric / nullif(sum(w.counting_game), 0) AS fga_pg,
    sum(w.xpm)::numeric / nullif(sum(w.counting_game), 0) AS xpm_pg,
    sum(w.xpa)::numeric / nullif(sum(w.counting_game), 0) AS xpa_pg,
    sum(w.fgm_50p)::numeric / nullif(sum(w.counting_game), 0) AS fgm_50p_pg,
    sum(w.sack)::numeric / nullif(sum(w.counting_game), 0) AS sack_pg,
    sum(w.def_int)::numeric / nullif(sum(w.counting_game), 0) AS def_int_pg,
    sum(w.fum_rec)::numeric / nullif(sum(w.counting_game), 0) AS fum_rec_pg,
    sum(w.def_td)::numeric / nullif(sum(w.counting_game), 0) AS def_td_pg,
    sum(w.st_td)::numeric / nullif(sum(w.counting_game), 0) AS st_td_pg,
    sum(w.blk_kick)::numeric / nullif(sum(w.counting_game), 0) AS blk_kick_pg,
    sum(w.safe)::numeric / nullif(sum(w.counting_game), 0) AS safe_pg,
    sum(w.pts_allow)::numeric / nullif(sum(w.counting_game), 0) AS pts_allow_pg,
    sum(w.yds_allow)::numeric / nullif(sum(w.counting_game), 0) AS yds_allow_pg,
    sum(w.total_td)::numeric / nullif(sum(w.counting_game), 0) AS total_td_pg,
    sum(w.g_rush_100)::bigint AS g_rush_100,
    sum(w.g_rec_100)::bigint AS g_rec_100,
    sum(w.g_pass_300)::bigint AS g_pass_300,
    sum(w.g_td_2)::bigint AS g_td_2
FROM v_player_split_weeks w
CROSS JOIN LATERAL (
    VALUES
        ('phase'::text, w.phase),
        ('half'::text, w.half)
) AS k(split_family, split_value)
GROUP BY w.year, w.player_id, k.split_family, k.split_value;

COMMENT ON VIEW v_player_season_splits IS
'Player-season splits. split_family phase is regular or playoff. split_family half is first or second. games and points partition the posted regular-plus-playoff roster weeks: the two phase rows sum to that set, and the two half rows sum to the same set. Counting columns sum player_week_counting_stats on those weeks, with the same total_td and milestone rules as v_player_counting_season. They are not that view, which also keeps free-agent weeks and 2022-2023 consolation weeks. A _pg column divides by counting_games.';

CREATE VIEW v_player_opponent_splits AS
SELECT
    w.year,
    w.player_id,
    max(w.player_name) AS player_name,
    max(w.position) AS position,
    max(club.abbr) AS nfl_team,
    opp.abbr AS opponent,
    count(*)::bigint AS games,
    sum(w.points) AS points,
    sum(w.points) / count(*)::numeric AS points_per_game
FROM v_player_split_weeks w
JOIN players p ON p.id = w.player_id
JOIN nfl_team_crosswalk club ON club.abbr = btrim(p.nfl_team)
JOIN nfl_team_weeks n
    ON n.year = w.year
    AND n.week = w.week
    AND n.espn_pro_team_id = club.espn_pro_team_id
    AND NOT n.is_bye
JOIN nfl_team_crosswalk opp
    ON opp.espn_pro_team_id = n.opponent_espn_pro_team_id
WHERE w.year IN (2022, 2023)
    AND btrim(p.nfl_team) <> ''
GROUP BY w.year, w.player_id, opp.abbr;

COMMENT ON VIEW v_player_opponent_splits IS
'2022-2023 roster weeks against one NFL opponent. Coverage is nfl_team_weeks only, which this warehouse has for 2022 and 2023. The year filter keeps 2024-2026 empty rather than inventing a schedule. The club is players.nfl_team, the current catalog club (catalog_as_of 2026-11-07 here), not the club in that week. A traded player is misattributed to the current club''s opponents. Bye weeks are omitted. games, points, and points_per_game are the same rostered regular and playoff weeks as v_player_season_splits. Defensive DvP is not here.';

CREATE VIEW v_player_site_splits AS
SELECT
    w.year,
    w.player_id,
    max(w.player_name) AS player_name,
    max(w.position) AS position,
    max(club.abbr) AS nfl_team,
    CASE WHEN n.is_home THEN 'home' ELSE 'away' END AS site,
    count(*)::bigint AS games,
    sum(w.points) AS points,
    sum(w.points) / count(*)::numeric AS points_per_game
FROM v_player_split_weeks w
JOIN players p ON p.id = w.player_id
JOIN nfl_team_crosswalk club ON club.abbr = btrim(p.nfl_team)
JOIN nfl_team_weeks n
    ON n.year = w.year
    AND n.week = w.week
    AND n.espn_pro_team_id = club.espn_pro_team_id
    AND NOT n.is_bye
WHERE w.year IN (2022, 2023)
    AND btrim(p.nfl_team) <> ''
GROUP BY w.year, w.player_id, CASE WHEN n.is_home THEN 'home' ELSE 'away' END;

COMMENT ON VIEW v_player_site_splits IS
'2022-2023 home and away roster weeks. Same schedule coverage and current-club caveat as v_player_opponent_splits: nfl_team_weeks joined through players.nfl_team, which is the catalog club and not the week-of club. A traded player is misattributed. 2024-2026 return no rows. Bye weeks are omitted. Home plus away partitions the non-bye scheduled weeks in the regular-plus-playoff roster set. Defensive DvP is not here.';
