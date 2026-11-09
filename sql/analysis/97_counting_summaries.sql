-- Season and career counting box scores over player_week_counting_stats.
-- Plain views (not materialized): load applies this file in numeric order and
-- does not refresh them. Facts stay in sql/facts.sql. No fact columns change.
--
-- Sums are posted weeks only (v_posted_weeks). A live leg stays out until
-- the median team total reaches 40.
--
-- games counts counting-stat rows. Byes and other all-zero fantasy weeks have
-- no row, so games is not an NFL games-played count and not a fantasy start
-- count. Rostered weeks and free-agent weeks are both included.
--
-- Every source counting column is a sum. Columns ending in _pg are that sum
-- divided by games. Career per-game columns divide the career sum by career
-- games. They are not the mean of the season rates.
--
-- total_td is pass_td + rush_td + rec_td. It does not include def_td or st_td.
-- g_rush_100 / g_rec_100 / g_pass_300 count games at or above 100 rush yards,
-- 100 receiving yards, and 300 pass yards. g_td_2 counts games whose total_td
-- is at least 2.
--
-- pts_allow and yds_allow sum the weekly allowed figures on stored weeks only.
-- pts_allow_pg and yds_allow_pg are the defense rates. Kickers and defenses
-- use the same games denominator as skill players.
--
-- Red-zone columns stay 0 for ESPN seasons (2022-2023): those dumps have no
-- red-zone stat id.

DROP VIEW IF EXISTS v_player_counting_career CASCADE;
DROP VIEW IF EXISTS v_player_counting_season CASCADE;

CREATE VIEW v_player_counting_season AS
SELECT
    c.year,
    c.player_id,
    coalesce(p.display_name, c.player_id) AS player_name,
    p.position,
    count(*) AS games,
    sum(c.pass_cmp) AS pass_cmp,
    sum(c.pass_att) AS pass_att,
    sum(c.pass_yd) AS pass_yd,
    sum(c.pass_td) AS pass_td,
    sum(c.pass_int) AS pass_int,
    sum(c.rush_att) AS rush_att,
    sum(c.rush_yd) AS rush_yd,
    sum(c.rush_td) AS rush_td,
    sum(c.rec) AS rec,
    sum(c.rec_yd) AS rec_yd,
    sum(c.rec_td) AS rec_td,
    sum(c.rec_tgt) AS rec_tgt,
    sum(c.fum_lost) AS fum_lost,
    sum(c.pass_2pt) AS pass_2pt,
    sum(c.rush_2pt) AS rush_2pt,
    sum(c.rec_2pt) AS rec_2pt,
    sum(c.pass_fd) AS pass_fd,
    sum(c.rush_fd) AS rush_fd,
    sum(c.rec_fd) AS rec_fd,
    sum(c.pass_rz_att) AS pass_rz_att,
    sum(c.rush_rz_att) AS rush_rz_att,
    sum(c.rec_rz_tgt) AS rec_rz_tgt,
    sum(c.fgm) AS fgm,
    sum(c.fga) AS fga,
    sum(c.xpm) AS xpm,
    sum(c.xpa) AS xpa,
    sum(c.fgm_50p) AS fgm_50p,
    sum(c.sack) AS sack,
    sum(c.def_int) AS def_int,
    sum(c.fum_rec) AS fum_rec,
    sum(c.def_td) AS def_td,
    sum(c.st_td) AS st_td,
    sum(c.blk_kick) AS blk_kick,
    sum(c.safe) AS safe,
    sum(c.pts_allow) AS pts_allow,
    sum(c.yds_allow) AS yds_allow,
    sum(c.pass_td + c.rush_td + c.rec_td) AS total_td,
    sum(c.pass_cmp)::double precision / count(*)::double precision AS pass_cmp_pg,
    sum(c.pass_att)::double precision / count(*)::double precision AS pass_att_pg,
    sum(c.pass_yd)::double precision / count(*)::double precision AS pass_yd_pg,
    sum(c.pass_td)::double precision / count(*)::double precision AS pass_td_pg,
    sum(c.pass_int)::double precision / count(*)::double precision AS pass_int_pg,
    sum(c.rush_att)::double precision / count(*)::double precision AS rush_att_pg,
    sum(c.rush_yd)::double precision / count(*)::double precision AS rush_yd_pg,
    sum(c.rush_td)::double precision / count(*)::double precision AS rush_td_pg,
    sum(c.rec)::double precision / count(*)::double precision AS rec_pg,
    sum(c.rec_yd)::double precision / count(*)::double precision AS rec_yd_pg,
    sum(c.rec_td)::double precision / count(*)::double precision AS rec_td_pg,
    sum(c.rec_tgt)::double precision / count(*)::double precision AS rec_tgt_pg,
    sum(c.fum_lost)::double precision / count(*)::double precision AS fum_lost_pg,
    sum(c.pass_2pt)::double precision / count(*)::double precision AS pass_2pt_pg,
    sum(c.rush_2pt)::double precision / count(*)::double precision AS rush_2pt_pg,
    sum(c.rec_2pt)::double precision / count(*)::double precision AS rec_2pt_pg,
    sum(c.pass_fd)::double precision / count(*)::double precision AS pass_fd_pg,
    sum(c.rush_fd)::double precision / count(*)::double precision AS rush_fd_pg,
    sum(c.rec_fd)::double precision / count(*)::double precision AS rec_fd_pg,
    sum(c.pass_rz_att)::double precision / count(*)::double precision AS pass_rz_att_pg,
    sum(c.rush_rz_att)::double precision / count(*)::double precision AS rush_rz_att_pg,
    sum(c.rec_rz_tgt)::double precision / count(*)::double precision AS rec_rz_tgt_pg,
    sum(c.fgm)::double precision / count(*)::double precision AS fgm_pg,
    sum(c.fga)::double precision / count(*)::double precision AS fga_pg,
    sum(c.xpm)::double precision / count(*)::double precision AS xpm_pg,
    sum(c.xpa)::double precision / count(*)::double precision AS xpa_pg,
    sum(c.fgm_50p)::double precision / count(*)::double precision AS fgm_50p_pg,
    sum(c.sack)::double precision / count(*)::double precision AS sack_pg,
    sum(c.def_int)::double precision / count(*)::double precision AS def_int_pg,
    sum(c.fum_rec)::double precision / count(*)::double precision AS fum_rec_pg,
    sum(c.def_td)::double precision / count(*)::double precision AS def_td_pg,
    sum(c.st_td)::double precision / count(*)::double precision AS st_td_pg,
    sum(c.blk_kick)::double precision / count(*)::double precision AS blk_kick_pg,
    sum(c.safe)::double precision / count(*)::double precision AS safe_pg,
    sum(c.pts_allow)::double precision / count(*)::double precision AS pts_allow_pg,
    sum(c.yds_allow)::double precision / count(*)::double precision AS yds_allow_pg,
    sum(c.pass_td + c.rush_td + c.rec_td)::double precision / count(*)::double precision AS total_td_pg,
    count(*) FILTER (WHERE c.rush_yd >= 100) AS g_rush_100,
    count(*) FILTER (WHERE c.rec_yd >= 100) AS g_rec_100,
    count(*) FILTER (WHERE c.pass_yd >= 300) AS g_pass_300,
    count(*) FILTER (WHERE (c.pass_td + c.rush_td + c.rec_td) >= 2) AS g_td_2
FROM player_week_counting_stats c
JOIN v_posted_weeks posted ON posted.year = c.year AND posted.week = c.week
LEFT JOIN players p ON p.id = c.player_id
GROUP BY c.year, c.player_id, p.display_name, p.position;

CREATE VIEW v_player_counting_career AS
SELECT
    player_id,
    max(player_name) AS player_name,
    max(position) AS position,
    count(*) AS seasons,
    min(year) AS first_year,
    max(year) AS last_year,
    sum(games) AS games,
    sum(pass_cmp) AS pass_cmp,
    sum(pass_att) AS pass_att,
    sum(pass_yd) AS pass_yd,
    sum(pass_td) AS pass_td,
    sum(pass_int) AS pass_int,
    sum(rush_att) AS rush_att,
    sum(rush_yd) AS rush_yd,
    sum(rush_td) AS rush_td,
    sum(rec) AS rec,
    sum(rec_yd) AS rec_yd,
    sum(rec_td) AS rec_td,
    sum(rec_tgt) AS rec_tgt,
    sum(fum_lost) AS fum_lost,
    sum(pass_2pt) AS pass_2pt,
    sum(rush_2pt) AS rush_2pt,
    sum(rec_2pt) AS rec_2pt,
    sum(pass_fd) AS pass_fd,
    sum(rush_fd) AS rush_fd,
    sum(rec_fd) AS rec_fd,
    sum(pass_rz_att) AS pass_rz_att,
    sum(rush_rz_att) AS rush_rz_att,
    sum(rec_rz_tgt) AS rec_rz_tgt,
    sum(fgm) AS fgm,
    sum(fga) AS fga,
    sum(xpm) AS xpm,
    sum(xpa) AS xpa,
    sum(fgm_50p) AS fgm_50p,
    sum(sack) AS sack,
    sum(def_int) AS def_int,
    sum(fum_rec) AS fum_rec,
    sum(def_td) AS def_td,
    sum(st_td) AS st_td,
    sum(blk_kick) AS blk_kick,
    sum(safe) AS safe,
    sum(pts_allow) AS pts_allow,
    sum(yds_allow) AS yds_allow,
    sum(total_td) AS total_td,
    sum(pass_cmp)::double precision / sum(games)::double precision AS pass_cmp_pg,
    sum(pass_att)::double precision / sum(games)::double precision AS pass_att_pg,
    sum(pass_yd)::double precision / sum(games)::double precision AS pass_yd_pg,
    sum(pass_td)::double precision / sum(games)::double precision AS pass_td_pg,
    sum(pass_int)::double precision / sum(games)::double precision AS pass_int_pg,
    sum(rush_att)::double precision / sum(games)::double precision AS rush_att_pg,
    sum(rush_yd)::double precision / sum(games)::double precision AS rush_yd_pg,
    sum(rush_td)::double precision / sum(games)::double precision AS rush_td_pg,
    sum(rec)::double precision / sum(games)::double precision AS rec_pg,
    sum(rec_yd)::double precision / sum(games)::double precision AS rec_yd_pg,
    sum(rec_td)::double precision / sum(games)::double precision AS rec_td_pg,
    sum(rec_tgt)::double precision / sum(games)::double precision AS rec_tgt_pg,
    sum(fum_lost)::double precision / sum(games)::double precision AS fum_lost_pg,
    sum(pass_2pt)::double precision / sum(games)::double precision AS pass_2pt_pg,
    sum(rush_2pt)::double precision / sum(games)::double precision AS rush_2pt_pg,
    sum(rec_2pt)::double precision / sum(games)::double precision AS rec_2pt_pg,
    sum(pass_fd)::double precision / sum(games)::double precision AS pass_fd_pg,
    sum(rush_fd)::double precision / sum(games)::double precision AS rush_fd_pg,
    sum(rec_fd)::double precision / sum(games)::double precision AS rec_fd_pg,
    sum(pass_rz_att)::double precision / sum(games)::double precision AS pass_rz_att_pg,
    sum(rush_rz_att)::double precision / sum(games)::double precision AS rush_rz_att_pg,
    sum(rec_rz_tgt)::double precision / sum(games)::double precision AS rec_rz_tgt_pg,
    sum(fgm)::double precision / sum(games)::double precision AS fgm_pg,
    sum(fga)::double precision / sum(games)::double precision AS fga_pg,
    sum(xpm)::double precision / sum(games)::double precision AS xpm_pg,
    sum(xpa)::double precision / sum(games)::double precision AS xpa_pg,
    sum(fgm_50p)::double precision / sum(games)::double precision AS fgm_50p_pg,
    sum(sack)::double precision / sum(games)::double precision AS sack_pg,
    sum(def_int)::double precision / sum(games)::double precision AS def_int_pg,
    sum(fum_rec)::double precision / sum(games)::double precision AS fum_rec_pg,
    sum(def_td)::double precision / sum(games)::double precision AS def_td_pg,
    sum(st_td)::double precision / sum(games)::double precision AS st_td_pg,
    sum(blk_kick)::double precision / sum(games)::double precision AS blk_kick_pg,
    sum(safe)::double precision / sum(games)::double precision AS safe_pg,
    sum(pts_allow)::double precision / sum(games)::double precision AS pts_allow_pg,
    sum(yds_allow)::double precision / sum(games)::double precision AS yds_allow_pg,
    sum(total_td)::double precision / sum(games)::double precision AS total_td_pg,
    sum(g_rush_100) AS g_rush_100,
    sum(g_rec_100) AS g_rec_100,
    sum(g_pass_300) AS g_pass_300,
    sum(g_td_2) AS g_td_2
FROM v_player_counting_season
GROUP BY player_id;

COMMENT ON VIEW v_player_counting_season IS
'Season counting box score. One row per player-year with at least one player_week_counting_stats row. games is that row count: byes and other all-zero fantasy weeks have no counting row, so games is not NFL games played and not fantasy starts. Rostered and free-agent weeks are both included. Each counting column is a sum. A column ending in _pg is that sum divided by games. total_td is pass_td plus rush_td plus rec_td and leaves out def_td and st_td. g_rush_100, g_rec_100, and g_pass_300 count games with rush_yd >= 100, rec_yd >= 100, and pass_yd >= 300. g_td_2 counts games whose total_td is at least 2. pts_allow and yds_allow sum weekly figures on stored weeks only. Their _pg columns are the per-game rates, which is the honest defense number. Kickers and defenses use the same games denominator. Red-zone columns are 0 for ESPN seasons (2022-2023) because those dumps have no red-zone stat id.';

COMMENT ON VIEW v_player_counting_career IS
'Career counting box score summed from v_player_counting_season. seasons counts years that have a counting row. games sums those season game counts. Per-game columns are the career sum divided by career games, not the average of season rates. Milestone columns sum the season game counters. total_td is pass plus rush plus rec touchdowns and leaves out defensive and special-teams touchdowns. Points and yards allowed stay sums of weekly figures. The _pg columns are the rate over counting-stat rows.';
