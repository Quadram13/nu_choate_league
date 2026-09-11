-- Counterfactual universes: never-median / always-median standings, seeds, playoffs.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_career_median,
    v_career_h2h,
    v_universe_outcomes,
    v_universe_games,
    v_universe_seeds,
    v_universe_playoff_shape,
    v_universe_standings
CASCADE;

-- Counterfactual universes matching alternate.py (never_median / always_median).
CREATE VIEW v_universe_standings AS
SELECT
    'never_median'::text AS universe,
    h.year,
    h.manager_id,
    h.display_name,
    h.wins,
    h.losses,
    h.ties,
    h.points_for,
    h.points_against,
    h.win_pct,
    h.rank,
    (h.rank = 1) AS rs_champ,
    (h.wins = r.wins AND h.losses = r.losses AND h.ties = r.ties) AS matches_official_record
FROM v_standings_h2h h
JOIN official_records r ON r.year = h.year AND r.manager_id = h.manager_id
UNION ALL
SELECT
    'always_median',
    med.year,
    med.manager_id,
    med.display_name,
    med.wins,
    med.losses,
    med.ties,
    med.points_for,
    med.points_against,
    med.win_pct,
    med.rank,
    (med.rank = 1) AS rs_champ,
    (med.wins = r.wins AND med.losses = r.losses AND med.ties = r.ties) AS matches_official_record
FROM v_standings_median med
JOIN official_records r ON r.year = med.year AND r.manager_id = med.manager_id;

CREATE VIEW v_universe_playoff_shape AS
SELECT
    o.year,
    o.playoff_teams,
    o.playoff_start_week,
    o.champion AS official_champion,
    o.runner_up AS official_runner_up,
    CASE
        WHEN o.champion IS NULL OR o.playoff_teams IS NULL THEN NULL
        WHEN o.playoff_teams = 6 AND o.playoff_start_week IS NOT NULL THEN 'six'
        WHEN o.playoff_teams = 4 AND pw.playoff_weeks = 2 THEN 'four'
        ELSE NULL
    END AS shape,
    pw.semi_week,
    pw.final_week
FROM season_outcomes o
LEFT JOIN (
    SELECT
        year,
        count(DISTINCT week) AS playoff_weeks,
        min(week) AS semi_week,
        max(week) AS final_week
    FROM matchups
    WHERE kind = 'playoff'
    GROUP BY year
) pw ON pw.year = o.year;

CREATE VIEW v_universe_seeds AS
SELECT
    seeded.universe,
    seeded.year,
    seeded.manager_id,
    seeded.display_name,
    seeded.wins,
    seeded.losses,
    seeded.ties,
    seeded.points_for,
    seeded.seed
FROM (
    SELECT
        u.universe,
        u.year,
        u.manager_id,
        u.display_name,
        u.wins,
        u.losses,
        u.ties,
        u.points_for,
        o.playoff_teams,
        row_number() OVER (
            PARTITION BY u.universe, u.year
            ORDER BY u.rank, u.manager_id
        ) AS seed
    FROM v_universe_standings u
    JOIN season_outcomes o ON o.year = u.year
    WHERE o.playoff_teams IS NOT NULL
        AND o.playoff_teams > 0
        AND (u.wins + u.losses + u.ties > 0 OR u.points_for > 0)
) seeded
WHERE seeded.seed <= seeded.playoff_teams;

CREATE VIEW v_universe_games AS
WITH
pair AS (
    SELECT
        h.universe,
        h.year,
        h.seed AS home_seed,
        h.manager_id AS home_id,
        a.seed AS away_seed,
        a.manager_id AS away_id
    FROM v_universe_seeds h
    JOIN v_universe_seeds a
        ON a.universe = h.universe
        AND a.year = h.year
        AND a.seed > h.seed
),
four_semi AS (
    SELECT
        p.universe,
        p.year,
        'semifinal'::text AS round,
        sh.semi_week AS week,
        p.home_seed,
        p.home_id,
        hs.points AS home_points,
        p.away_seed,
        p.away_id,
        aws.points AS away_points,
        CASE
            WHEN hs.points IS NULL OR aws.points IS NULL THEN NULL
            WHEN hs.points > aws.points THEN p.home_id
            WHEN aws.points > hs.points THEN p.away_id
            ELSE p.home_id
        END AS winner,
        CASE
            WHEN hs.points IS NOT NULL AND aws.points IS NOT NULL AND hs.points = aws.points
                THEN 'higher_seed'
        END AS tiebreak
    FROM pair p
    JOIN v_universe_playoff_shape sh ON sh.year = p.year AND sh.shape = 'four'
    LEFT JOIN week_scores hs
        ON hs.year = p.year AND hs.week = sh.semi_week AND hs.manager_id = p.home_id
    LEFT JOIN week_scores aws
        ON aws.year = p.year AND aws.week = sh.semi_week AND aws.manager_id = p.away_id
    WHERE (p.home_seed, p.away_seed) IN ((1, 4), (2, 3))
),
four_final AS (
    SELECT
        w1.universe,
        w1.year,
        'championship'::text AS round,
        sh.final_week AS week,
        w1.winner AS home_id,
        w2.winner AS away_id
    FROM (
        SELECT * FROM four_semi WHERE home_seed = 1
    ) w1
    JOIN (
        SELECT * FROM four_semi WHERE home_seed = 2
    ) w2 ON w2.universe = w1.universe AND w2.year = w1.year
    JOIN v_universe_playoff_shape sh ON sh.year = w1.year AND sh.shape = 'four'
    WHERE w1.winner IS NOT NULL AND w2.winner IS NOT NULL
),
four_final_scored AS (
    SELECT
        f.universe,
        f.year,
        f.round,
        f.week,
        least(s1.seed, s2.seed) AS home_seed,
        CASE WHEN s1.seed <= s2.seed THEN f.home_id ELSE f.away_id END AS home_id,
        CASE WHEN s1.seed <= s2.seed THEN hs.points ELSE aws.points END AS home_points,
        greatest(s1.seed, s2.seed) AS away_seed,
        CASE WHEN s1.seed <= s2.seed THEN f.away_id ELSE f.home_id END AS away_id,
        CASE WHEN s1.seed <= s2.seed THEN aws.points ELSE hs.points END AS away_points
    FROM four_final f
    JOIN v_universe_seeds s1
        ON s1.universe = f.universe AND s1.year = f.year AND s1.manager_id = f.home_id
    JOIN v_universe_seeds s2
        ON s2.universe = f.universe AND s2.year = f.year AND s2.manager_id = f.away_id
    LEFT JOIN week_scores hs
        ON hs.year = f.year AND hs.week = f.week AND hs.manager_id = f.home_id
    LEFT JOIN week_scores aws
        ON aws.year = f.year AND aws.week = f.week AND aws.manager_id = f.away_id
),
four_final_out AS (
    SELECT
        universe,
        year,
        round,
        week,
        home_seed,
        home_id,
        home_points,
        away_seed,
        away_id,
        away_points,
        CASE
            WHEN home_points IS NULL OR away_points IS NULL THEN NULL
            WHEN home_points > away_points THEN home_id
            WHEN away_points > home_points THEN away_id
            ELSE home_id
        END AS winner,
        CASE
            WHEN home_points IS NOT NULL AND away_points IS NOT NULL AND home_points = away_points
                THEN 'higher_seed'
        END AS tiebreak
    FROM four_final_scored
),
six_wc AS (
    SELECT
        p.universe,
        p.year,
        'wildcard'::text AS round,
        sh.playoff_start_week AS week,
        p.home_seed,
        p.home_id,
        hs.points AS home_points,
        p.away_seed,
        p.away_id,
        aws.points AS away_points,
        CASE
            WHEN hs.points IS NULL OR aws.points IS NULL THEN NULL
            WHEN hs.points > aws.points THEN p.home_id
            WHEN aws.points > hs.points THEN p.away_id
            ELSE p.home_id
        END AS winner,
        CASE
            WHEN hs.points IS NOT NULL AND aws.points IS NOT NULL AND hs.points = aws.points
                THEN 'higher_seed'
        END AS tiebreak
    FROM pair p
    JOIN v_universe_playoff_shape sh ON sh.year = p.year AND sh.shape = 'six'
    LEFT JOIN week_scores hs
        ON hs.year = p.year AND hs.week = sh.playoff_start_week AND hs.manager_id = p.home_id
    LEFT JOIN week_scores aws
        ON aws.year = p.year AND aws.week = sh.playoff_start_week AND aws.manager_id = p.away_id
    WHERE (p.home_seed, p.away_seed) IN ((3, 6), (4, 5))
),
six_semi_pair AS (
    SELECT
        w36.universe,
        w36.year,
        sh.playoff_start_week + 1 AS week,
        1 AS home_seed,
        s1.manager_id AS home_id,
        w45.winner AS away_id
    FROM six_wc w36
    JOIN six_wc w45
        ON w45.universe = w36.universe
        AND w45.year = w36.year
        AND w45.home_seed = 4
    JOIN v_universe_seeds s1
        ON s1.universe = w36.universe AND s1.year = w36.year AND s1.seed = 1
    JOIN v_universe_playoff_shape sh ON sh.year = w36.year AND sh.shape = 'six'
    WHERE w36.home_seed = 3
        AND w36.winner IS NOT NULL
        AND w45.winner IS NOT NULL
    UNION ALL
    SELECT
        w36.universe,
        w36.year,
        sh.playoff_start_week + 1,
        2,
        s2.manager_id,
        w36.winner
    FROM six_wc w36
    JOIN six_wc w45
        ON w45.universe = w36.universe
        AND w45.year = w36.year
        AND w45.home_seed = 4
        AND w45.winner IS NOT NULL
    JOIN v_universe_seeds s2
        ON s2.universe = w36.universe AND s2.year = w36.year AND s2.seed = 2
    JOIN v_universe_playoff_shape sh ON sh.year = w36.year AND sh.shape = 'six'
    WHERE w36.home_seed = 3
        AND w36.winner IS NOT NULL
),
six_semi AS (
    SELECT
        p.universe,
        p.year,
        'semifinal'::text AS round,
        p.week,
        p.home_seed,
        p.home_id,
        hs.points AS home_points,
        aw.seed AS away_seed,
        p.away_id,
        aws.points AS away_points,
        CASE
            WHEN hs.points IS NULL OR aws.points IS NULL THEN NULL
            WHEN hs.points > aws.points THEN p.home_id
            WHEN aws.points > hs.points THEN p.away_id
            ELSE p.home_id
        END AS winner,
        CASE
            WHEN hs.points IS NOT NULL AND aws.points IS NOT NULL AND hs.points = aws.points
                THEN 'higher_seed'
        END AS tiebreak
    FROM six_semi_pair p
    JOIN v_universe_seeds aw
        ON aw.universe = p.universe AND aw.year = p.year AND aw.manager_id = p.away_id
    LEFT JOIN week_scores hs
        ON hs.year = p.year AND hs.week = p.week AND hs.manager_id = p.home_id
    LEFT JOIN week_scores aws
        ON aws.year = p.year AND aws.week = p.week AND aws.manager_id = p.away_id
),
six_final_pair AS (
    SELECT
        a.universe,
        a.year,
        sh.playoff_start_week + 2 AS week,
        a.winner AS id_a,
        b.winner AS id_b
    FROM six_semi a
    JOIN six_semi b
        ON b.universe = a.universe AND b.year = a.year AND b.home_seed = 2
    JOIN v_universe_playoff_shape sh ON sh.year = a.year AND sh.shape = 'six'
    WHERE a.home_seed = 1
        AND a.winner IS NOT NULL
        AND b.winner IS NOT NULL
),
six_final AS (
    SELECT
        f.universe,
        f.year,
        'championship'::text AS round,
        f.week,
        least(sa.seed, sb.seed) AS home_seed,
        CASE WHEN sa.seed <= sb.seed THEN f.id_a ELSE f.id_b END AS home_id,
        CASE WHEN sa.seed <= sb.seed THEN ha.points ELSE hb.points END AS home_points,
        greatest(sa.seed, sb.seed) AS away_seed,
        CASE WHEN sa.seed <= sb.seed THEN f.id_b ELSE f.id_a END AS away_id,
        CASE WHEN sa.seed <= sb.seed THEN hb.points ELSE ha.points END AS away_points,
        CASE
            WHEN ha.points IS NULL OR hb.points IS NULL THEN NULL
            WHEN sa.seed <= sb.seed AND ha.points > hb.points THEN f.id_a
            WHEN sa.seed <= sb.seed AND hb.points > ha.points THEN f.id_b
            WHEN sa.seed <= sb.seed THEN f.id_a
            WHEN hb.points > ha.points THEN f.id_b
            WHEN ha.points > hb.points THEN f.id_a
            ELSE f.id_b
        END AS winner,
        CASE
            WHEN ha.points IS NOT NULL AND hb.points IS NOT NULL AND ha.points = hb.points
                THEN 'higher_seed'
        END AS tiebreak
    FROM six_final_pair f
    JOIN v_universe_seeds sa
        ON sa.universe = f.universe AND sa.year = f.year AND sa.manager_id = f.id_a
    JOIN v_universe_seeds sb
        ON sb.universe = f.universe AND sb.year = f.year AND sb.manager_id = f.id_b
    LEFT JOIN week_scores ha
        ON ha.year = f.year AND ha.week = f.week AND ha.manager_id = f.id_a
    LEFT JOIN week_scores hb
        ON hb.year = f.year AND hb.week = f.week AND hb.manager_id = f.id_b
)
SELECT universe, year, round, week, home_seed, home_id, home_points,
       away_seed, away_id, away_points, winner, tiebreak
FROM four_semi
UNION ALL
SELECT universe, year, round, week, home_seed, home_id, home_points,
       away_seed, away_id, away_points, winner, tiebreak
FROM four_final_out
UNION ALL
SELECT universe, year, round, week, home_seed, home_id, home_points,
       away_seed, away_id, away_points, winner, tiebreak
FROM six_wc
UNION ALL
SELECT universe, year, round, week, home_seed, home_id, home_points,
       away_seed, away_id, away_points, winner, tiebreak
FROM six_semi
UNION ALL
SELECT universe, year, round, week, home_seed, home_id, home_points,
       away_seed, away_id, away_points, winner, tiebreak
FROM six_final;

CREATE VIEW v_universe_outcomes AS
SELECT
    u.universe,
    u.year,
    rs.manager_id AS regular_season_champion,
    fin.winner AS champion,
    CASE
        WHEN fin.winner IS NULL THEN NULL
        WHEN fin.winner = fin.home_id THEN fin.away_id
        ELSE fin.home_id
    END AS runner_up,
    sh.shape,
    bool_and(u.matches_official_record)
        AND fin.winner IS NOT DISTINCT FROM sh.official_champion AS matches_official
FROM v_universe_standings u
JOIN v_universe_playoff_shape sh ON sh.year = u.year
JOIN v_universe_standings rs
    ON rs.universe = u.universe AND rs.year = u.year AND rs.rs_champ
LEFT JOIN v_universe_games fin
    ON fin.universe = u.universe
    AND fin.year = u.year
    AND fin.round = 'championship'
GROUP BY
    u.universe,
    u.year,
    rs.manager_id,
    fin.winner,
    fin.home_id,
    fin.away_id,
    sh.shape,
    sh.official_champion;

CREATE VIEW v_career_h2h AS
SELECT
    u.manager_id,
    m.display_name,
    count(*) AS seasons,
    sum(u.wins) AS wins,
    sum(u.losses) AS losses,
    sum(u.ties) AS ties,
    sum(u.points_for) AS points_for,
    CASE
        WHEN sum(u.wins + u.losses + u.ties) = 0 THEN NULL
        ELSE (sum(u.wins) + 0.5 * sum(u.ties)) / sum(u.wins + u.losses + u.ties)
    END AS win_pct,
    count(*) FILTER (WHERE o.champion = u.manager_id) AS titles,
    count(*) FILTER (WHERE o.runner_up = u.manager_id) AS runner_up,
    count(*) FILTER (WHERE o.regular_season_champion = u.manager_id) AS regular_season_titles,
    count(*) FILTER (WHERE s.manager_id IS NOT NULL) AS playoff_appearances
FROM v_universe_standings u
JOIN managers m ON m.id = u.manager_id
LEFT JOIN v_universe_outcomes o
    ON o.universe = u.universe AND o.year = u.year
LEFT JOIN v_universe_seeds s
    ON s.universe = u.universe AND s.year = u.year AND s.manager_id = u.manager_id
WHERE u.universe = 'never_median'
    AND (u.wins + u.losses + u.ties > 0 OR u.points_for > 0)
GROUP BY u.manager_id, m.display_name;

CREATE VIEW v_career_median AS
SELECT
    u.manager_id,
    m.display_name,
    count(*) AS seasons,
    sum(u.wins) AS wins,
    sum(u.losses) AS losses,
    sum(u.ties) AS ties,
    sum(u.points_for) AS points_for,
    CASE
        WHEN sum(u.wins + u.losses + u.ties) = 0 THEN NULL
        ELSE (sum(u.wins) + 0.5 * sum(u.ties)) / sum(u.wins + u.losses + u.ties)
    END AS win_pct,
    count(*) FILTER (WHERE o.champion = u.manager_id) AS titles,
    count(*) FILTER (WHERE o.runner_up = u.manager_id) AS runner_up,
    count(*) FILTER (WHERE o.regular_season_champion = u.manager_id) AS regular_season_titles,
    count(*) FILTER (WHERE s.manager_id IS NOT NULL) AS playoff_appearances
FROM v_universe_standings u
JOIN managers m ON m.id = u.manager_id
LEFT JOIN v_universe_outcomes o
    ON o.universe = u.universe AND o.year = u.year
LEFT JOIN v_universe_seeds s
    ON s.universe = u.universe AND s.year = u.year AND s.manager_id = u.manager_id
WHERE u.universe = 'always_median'
    AND (u.wins + u.losses + u.ties > 0 OR u.points_for > 0)
GROUP BY u.manager_id, m.display_name;
