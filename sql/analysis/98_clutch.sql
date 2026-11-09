-- One-score record, blowout record, and Pythagorean wins.
--
-- Volatility is not defined here. Weekly spread, CV, best and worst week,
-- and deviation from the season mean live in sql/analysis/97_volatility.sql
-- (v_manager_volatility_season, v_manager_volatility_career,
-- v_manager_week_deviation). This file reads that shape from the app.
-- It does not replace v_luck_season. wins_vs_expected is copied onto the
-- Pythagorean views so the two lenses sit on one row.
--
-- Games. Regular-season head-to-head only: v_games.kind = 'regular' and
-- an opponent. That is the same set as v_standings_h2h and v_luck_weeks.
-- Posted weeks come in through v_games. A tie has margin 0, so it is a
-- one-score tie. A tie is not a blowout.
--
-- Cuts, from the 361 posted regular-season games (0 ties). Absolute margin
-- mean 25.00, p10 3.18, p25 9.02, p50 19.96, p75 36.34, p90 53.68,
-- max 94.70.
--   <= 5    55 games   15.2%   the inch mark (that week's closest)
--   <= 8    83 games   23.0%   one-score
--   <= 10  104 games   28.8%
--   >= 30  125 games   34.6%
--   >= 40   76 games   21.1%   blowout
-- Eight points is inside the closest quartile (p25 is 9.02) and covers one
-- rushing or receiving touchdown (6 in 2024-2026) plus about 50 yards.
-- Pass touchdowns score 4. The inch cut of 5 stays the single-game mark.
-- Forty points is about the same share of games as the one-score cut, and
-- it is double the median decision. Thirty points is the upper third, and
-- the mean margin is already 25, so that cut would not separate a blowout.
--
-- Pythagorean. games * PF^x / (PF^x + PA^x), games and points from
-- v_standings_h2h. actual_wins counts a tie as half a win.
-- wins_vs_pythagorean = actual_wins - pythagorean_wins.
-- lens_gap = wins_vs_pythagorean - wins_vs_expected.
-- A positive lens_gap means the point-ratio lens calls the season luckier
-- than the all-play lens.
--
-- Exponent 6.9. Least squares on all 56 manager-seasons bottoms at
-- 6.85-6.90 (RMSE 1.219 wins, correlation 0.879). The cross-league
-- convention 2.4 (the NFL Pythagorean 2.37, rounded) has RMSE 1.686 and
-- correlation 0.781 on this table. Leave-one-year-out training minima
-- stay between 6.7 and 7.4, and 6.9 beats 2.4 in every holdout year,
-- including the partial 2026 season. Per-season implied exponents are
-- unstable (IQR 2.60 to 13.78, median 8.04) because point ratios sit
-- near 1 across a 14-game sample. The pooled fit is the published one.
-- At 6.9 the two luck residuals correlate 0.722, and Pythagorean wins
-- correlate 0.892 with all-play expected wins. Related, and not the
-- same column.
--
-- Career Pythagorean is refit on summed points for and against. It is
-- not the sum of the season Pythagorean wins. Career one-score and
-- blowout records sum the same regular-season games, including 2026
-- (includes_partial). Season-grain record boards apply v_finished_seasons
-- in the query.
--
-- Reloading 10_games.sql drops v_games CASCADE and takes these views
-- with it. Reapply this file afterward. Reloading 20_standings.sql or
-- 40_luck.sql drops the views these depend on. Reapply this file then too.

DROP VIEW IF EXISTS
    v_pythagorean_career,
    v_pythagorean_season,
    v_clutch_career,
    v_clutch_season,
    v_clutch_games,
    v_clutch_cuts
CASCADE;

CREATE VIEW v_clutch_cuts AS
SELECT
    8::numeric AS one_score_margin,
    40::numeric AS blowout_margin,
    6.9::numeric AS pythagorean_exponent;

COMMENT ON VIEW v_clutch_cuts IS
    'One-score margin is 8 (83 of 361 games, 23.0%). Blowout margin is 40 (76 of 361, 21.1%). Pythagorean exponent is 6.9, the least-squares fit (RMSE 1.219 wins versus 1.686 at 2.4).';

CREATE VIEW v_clutch_games AS
SELECT
    g.year,
    g.week,
    g.matchup_id,
    g.manager_id,
    m.display_name,
    g.opponent_id,
    g.points,
    g.opp_points,
    g.margin,
    abs(g.margin) AS abs_margin,
    g.result,
    (abs(g.margin) <= cuts.one_score_margin) AS one_score,
    (abs(g.margin) >= cuts.blowout_margin) AS blowout,
    (sz.through_week IS NOT NULL AND sz.through_week < 17) AS partial_season
FROM v_games g
JOIN managers m ON m.id = g.manager_id
JOIN seasons sz ON sz.year = g.year
CROSS JOIN v_clutch_cuts cuts
WHERE g.kind = 'regular'
    AND g.opponent_id IS NOT NULL;

COMMENT ON VIEW v_clutch_games IS
    'Regular-season head-to-head games flagged one_score and blowout from v_clutch_cuts.';

CREATE VIEW v_clutch_season AS
SELECT
    g.year,
    g.manager_id,
    max(g.display_name) AS display_name,
    count(*) AS games,
    count(*) FILTER (WHERE g.one_score) AS one_score_games,
    count(*) FILTER (WHERE g.one_score AND g.result = 'win') AS one_score_wins,
    count(*) FILTER (WHERE g.one_score AND g.result = 'loss') AS one_score_losses,
    count(*) FILTER (WHERE g.one_score AND g.result = 'tie') AS one_score_ties,
    (
        count(*) FILTER (WHERE g.one_score AND g.result = 'win')::numeric
        + 0.5 * count(*) FILTER (WHERE g.one_score AND g.result = 'tie')
    ) / nullif(count(*) FILTER (WHERE g.one_score), 0) AS one_score_win_pct,
    count(*) FILTER (WHERE g.blowout) AS blowout_games,
    count(*) FILTER (WHERE g.blowout AND g.result = 'win') AS blowout_wins,
    count(*) FILTER (WHERE g.blowout AND g.result = 'loss') AS blowout_losses,
    count(*) FILTER (WHERE g.blowout AND g.result = 'tie') AS blowout_ties,
    (
        count(*) FILTER (WHERE g.blowout AND g.result = 'win')::numeric
        + 0.5 * count(*) FILTER (WHERE g.blowout AND g.result = 'tie')
    ) / nullif(count(*) FILTER (WHERE g.blowout), 0) AS blowout_win_pct,
    cuts.one_score_margin,
    cuts.blowout_margin,
    bool_or(g.partial_season) AS partial_season
FROM v_clutch_games g
CROSS JOIN v_clutch_cuts cuts
GROUP BY g.year, g.manager_id, cuts.one_score_margin, cuts.blowout_margin;

COMMENT ON VIEW v_clutch_season IS
    'Manager-season one-score and blowout W-L-T. Win% is wins plus half a tie, over games in that band. Null when the band is empty.';

CREATE VIEW v_clutch_career AS
SELECT
    g.manager_id,
    max(g.display_name) AS display_name,
    count(DISTINCT g.year) AS seasons,
    count(*) AS games,
    count(*) FILTER (WHERE g.one_score) AS one_score_games,
    count(*) FILTER (WHERE g.one_score AND g.result = 'win') AS one_score_wins,
    count(*) FILTER (WHERE g.one_score AND g.result = 'loss') AS one_score_losses,
    count(*) FILTER (WHERE g.one_score AND g.result = 'tie') AS one_score_ties,
    (
        count(*) FILTER (WHERE g.one_score AND g.result = 'win')::numeric
        + 0.5 * count(*) FILTER (WHERE g.one_score AND g.result = 'tie')
    ) / nullif(count(*) FILTER (WHERE g.one_score), 0) AS one_score_win_pct,
    count(*) FILTER (WHERE g.blowout) AS blowout_games,
    count(*) FILTER (WHERE g.blowout AND g.result = 'win') AS blowout_wins,
    count(*) FILTER (WHERE g.blowout AND g.result = 'loss') AS blowout_losses,
    count(*) FILTER (WHERE g.blowout AND g.result = 'tie') AS blowout_ties,
    (
        count(*) FILTER (WHERE g.blowout AND g.result = 'win')::numeric
        + 0.5 * count(*) FILTER (WHERE g.blowout AND g.result = 'tie')
    ) / nullif(count(*) FILTER (WHERE g.blowout), 0) AS blowout_win_pct,
    cuts.one_score_margin,
    cuts.blowout_margin,
    bool_or(g.partial_season) AS includes_partial
FROM v_clutch_games g
CROSS JOIN v_clutch_cuts cuts
GROUP BY g.manager_id, cuts.one_score_margin, cuts.blowout_margin;

COMMENT ON VIEW v_clutch_career IS
    'Career one-score and blowout records over the same regular-season games. includes_partial is true when 2026 is in the sample.';

CREATE VIEW v_pythagorean_season AS
WITH scored AS (
    SELECT
        h.year,
        h.manager_id,
        h.display_name,
        h.wins,
        h.losses,
        h.ties,
        (h.wins + h.losses + h.ties) AS games,
        (h.wins + 0.5 * h.ties) AS actual_wins,
        h.points_for,
        h.points_against,
        cuts.pythagorean_exponent AS exponent,
        (sz.through_week IS NOT NULL AND sz.through_week < 17) AS partial_season,
        CASE
            WHEN h.points_for > 0
                AND h.points_against > 0
                AND (h.wins + h.losses + h.ties) > 0
            THEN (h.wins + h.losses + h.ties)::numeric
                * power(h.points_for, cuts.pythagorean_exponent)
                / (
                    power(h.points_for, cuts.pythagorean_exponent)
                    + power(h.points_against, cuts.pythagorean_exponent)
                )
        END AS pythagorean_wins
    FROM v_standings_h2h h
    JOIN seasons sz ON sz.year = h.year
    CROSS JOIN v_clutch_cuts cuts
)
SELECT
    s.year,
    s.manager_id,
    s.display_name,
    s.wins,
    s.losses,
    s.ties,
    s.games,
    s.actual_wins,
    s.points_for,
    s.points_against,
    s.exponent,
    s.partial_season,
    s.pythagorean_wins,
    s.actual_wins - s.pythagorean_wins AS wins_vs_pythagorean,
    lk.expected_wins,
    lk.wins_vs_expected,
    (s.actual_wins - s.pythagorean_wins) - lk.wins_vs_expected AS lens_gap
FROM scored s
LEFT JOIN v_luck_season lk
    ON lk.year = s.year
    AND lk.manager_id = s.manager_id;

COMMENT ON VIEW v_pythagorean_season IS
    'Pythagorean wins from v_standings_h2h points, exponent on v_clutch_cuts. wins_vs_expected is the all-play lens from v_luck_season. lens_gap is wins_vs_pythagorean minus wins_vs_expected.';

CREATE VIEW v_pythagorean_career AS
WITH totals AS (
    SELECT
        h.manager_id,
        max(h.display_name) AS display_name,
        count(*) AS seasons,
        sum(h.wins) AS wins,
        sum(h.losses) AS losses,
        sum(h.ties) AS ties,
        sum(h.wins + h.losses + h.ties) AS games,
        sum(h.wins + 0.5 * h.ties) AS actual_wins,
        sum(h.points_for) AS points_for,
        sum(h.points_against) AS points_against,
        bool_or(sz.through_week IS NOT NULL AND sz.through_week < 17) AS includes_partial,
        max(cuts.pythagorean_exponent) AS exponent
    FROM v_standings_h2h h
    JOIN seasons sz ON sz.year = h.year
    CROSS JOIN v_clutch_cuts cuts
    GROUP BY h.manager_id
),
scored AS (
    SELECT
        t.manager_id,
        t.display_name,
        t.seasons,
        t.wins,
        t.losses,
        t.ties,
        t.games,
        t.actual_wins,
        t.points_for,
        t.points_against,
        t.exponent,
        t.includes_partial,
        CASE
            WHEN t.points_for > 0
                AND t.points_against > 0
                AND t.games > 0
            THEN t.games::numeric
                * power(t.points_for, t.exponent)
                / (
                    power(t.points_for, t.exponent)
                    + power(t.points_against, t.exponent)
                )
        END AS pythagorean_wins
    FROM totals t
)
SELECT
    s.manager_id,
    s.display_name,
    s.seasons,
    s.wins,
    s.losses,
    s.ties,
    s.games,
    s.actual_wins,
    s.points_for,
    s.points_against,
    s.exponent,
    s.includes_partial,
    s.pythagorean_wins,
    s.actual_wins - s.pythagorean_wins AS wins_vs_pythagorean,
    lk.expected_wins,
    lk.wins_vs_expected,
    (s.actual_wins - s.pythagorean_wins) - lk.wins_vs_expected AS lens_gap
FROM scored s
LEFT JOIN v_luck_career lk ON lk.manager_id = s.manager_id;

COMMENT ON VIEW v_pythagorean_career IS
    'Career Pythagorean wins refit on summed head-to-head points. wins_vs_expected is the sum of the season all-play residuals from v_luck_career.';
