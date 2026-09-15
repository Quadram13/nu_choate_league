-- Week marks, chairs, median tax, all-play career, playoff ledger.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_median_tax,
    v_playoff_career,
    v_all_play_career,
    v_chair_career,
    v_chair_season,
    v_marks_holders,
    v_marks_weeks,
    v_week_scores_ranked
CASCADE;

-- Regular-season scored weeks only (same filter as records highs/lows).
CREATE VIEW v_week_scores_ranked AS
SELECT
    w.year,
    w.week,
    w.manager_id,
    m.display_name,
    w.points,
    rank() OVER (
        PARTITION BY w.year, w.week
        ORDER BY w.points DESC, w.manager_id
    ) AS pf_rank,
    rank() OVER (
        PARTITION BY w.year, w.week
        ORDER BY w.points ASC, w.manager_id
    ) AS pf_low_rank,
    count(*) OVER (PARTITION BY w.year, w.week) AS teams
FROM week_scores w
JOIN seasons s ON s.year = w.year
JOIN managers m ON m.id = w.manager_id
WHERE (s.through_week IS NULL OR w.week <= s.through_week)
    AND EXISTS (
        SELECT 1
        FROM matchups mu
        WHERE mu.year = w.year
            AND mu.week = w.week
            AND mu.kind = 'regular'
            AND (mu.home_points <> 0 OR mu.away_points <> 0)
    );

CREATE VIEW v_marks_weeks AS
SELECT
    r.year,
    r.week,
    'high_water'::text AS kind,
    r.manager_id,
    r.display_name,
    NULL::text AS opponent_id,
    NULL::text AS opponent_name,
    NULL::text AS matchup_id,
    r.points,
    NULL::double precision AS opp_points,
    r.points AS value,
    NULL::text AS player_id,
    NULL::text AS player_name,
    NULL::text AS position
FROM v_week_scores_ranked r
WHERE r.pf_rank = 1
UNION ALL
SELECT
    r.year,
    r.week,
    'cellar',
    r.manager_id,
    r.display_name,
    NULL,
    NULL,
    NULL,
    r.points,
    NULL,
    r.points,
    NULL,
    NULL,
    NULL
FROM v_week_scores_ranked r
WHERE r.pf_low_rank = 1
UNION ALL
SELECT
    g.year,
    g.week,
    'inch',
    g.manager_id,
    m.display_name,
    g.opponent_id,
    om.display_name,
    g.matchup_id,
    g.points,
    g.opp_points,
    abs(g.margin),
    NULL,
    NULL,
    NULL
FROM v_games g
JOIN managers m ON m.id = g.manager_id
LEFT JOIN managers om ON om.id = g.opponent_id
WHERE g.kind = 'regular'
    AND g.opponent_id IS NOT NULL
    AND g.manager_id < g.opponent_id
    AND abs(g.margin) = (
        SELECT min(abs(x.margin))
        FROM v_games x
        WHERE x.year = g.year
            AND x.week = g.week
            AND x.kind = 'regular'
            AND x.opponent_id IS NOT NULL
            AND x.manager_id < x.opponent_id
    )
UNION ALL
SELECT
    g.year,
    g.week,
    'rout',
    g.manager_id,
    m.display_name,
    g.opponent_id,
    om.display_name,
    g.matchup_id,
    g.points,
    g.opp_points,
    abs(g.margin),
    NULL,
    NULL,
    NULL
FROM v_games g
JOIN managers m ON m.id = g.manager_id
LEFT JOIN managers om ON om.id = g.opponent_id
WHERE g.kind = 'regular'
    AND g.opponent_id IS NOT NULL
    AND g.result = 'win'
    AND abs(g.margin) = (
        SELECT max(abs(x.margin))
        FROM v_games x
        WHERE x.year = g.year
            AND x.week = g.week
            AND x.kind = 'regular'
            AND x.opponent_id IS NOT NULL
            AND x.result = 'win'
    )
UNION ALL
SELECT
    l.year,
    l.week,
    'stolen',
    l.manager_id,
    l.display_name,
    l.opponent_id,
    l.opponent_name,
    l.matchup_id,
    l.points,
    l.opp_points,
    l.pf_rank::double precision,
    NULL,
    NULL,
    NULL
FROM v_luck_weeks l
WHERE l.lucky_win
    AND l.pf_rank = (
        SELECT max(x.pf_rank)
        FROM v_luck_weeks x
        WHERE x.year = l.year AND x.week = l.week AND x.lucky_win
    )
UNION ALL
SELECT
    l.year,
    l.week,
    'punched',
    l.manager_id,
    l.display_name,
    l.opponent_id,
    l.opponent_name,
    l.matchup_id,
    l.points,
    l.opp_points,
    l.pf_rank::double precision,
    NULL,
    NULL,
    NULL
FROM v_luck_weeks l
WHERE l.unlucky_loss
    AND l.pf_rank = (
        SELECT min(x.pf_rank)
        FROM v_luck_weeks x
        WHERE x.year = l.year AND x.week = l.week AND x.unlucky_loss
    )
UNION ALL
SELECT
    mw.year,
    mw.week,
    'pine',
    mw.manager_id,
    mw.manager_name,
    NULL,
    NULL,
    mw.matchup_id,
    mw.actual_points,
    mw.optimal_points,
    mw.left_on_bench,
    NULL,
    NULL,
    NULL
FROM v_management_weeks mw
WHERE mw.kind = 'regular'
    AND mw.left_on_bench = (
        SELECT max(x.left_on_bench)
        FROM v_management_weeks x
        WHERE x.year = mw.year AND x.week = mw.week AND x.kind = 'regular'
    );

CREATE VIEW v_marks_holders AS
SELECT
    manager_id,
    display_name,
    kind,
    count(*) AS weeks
FROM v_marks_weeks
GROUP BY manager_id, display_name, kind;

CREATE VIEW v_chair_season AS
SELECT
    year,
    manager_id,
    manager_name,
    count(*) FILTER (WHERE kind = 'all_league') AS first_chair,
    count(*) FILTER (WHERE kind = 'busch') AS last_chair,
    count(*) FILTER (WHERE kind = 'benched_all_star') AS benched_first_chair
FROM v_all_league
GROUP BY year, manager_id, manager_name;

CREATE VIEW v_chair_career AS
SELECT
    manager_id,
    manager_name,
    sum(first_chair) AS first_chair,
    sum(last_chair) AS last_chair,
    sum(benched_first_chair) AS benched_first_chair
FROM v_chair_season
GROUP BY manager_id, manager_name;

CREATE VIEW v_all_play_career AS
SELECT
    manager_id,
    display_name,
    sum(wins) AS wins,
    sum(losses) AS losses,
    sum(ties) AS ties,
    CASE
        WHEN sum(wins + losses + ties) = 0 THEN NULL
        ELSE (sum(wins) + 0.5 * sum(ties)) / sum(wins + losses + ties)
    END AS win_pct
FROM v_all_play_season
GROUP BY manager_id, display_name;

CREATE VIEW v_playoff_career AS
SELECT
    g.manager_id,
    m.display_name,
    count(*) AS games,
    count(*) FILTER (WHERE g.result = 'win') AS wins,
    count(*) FILTER (WHERE g.result = 'loss') AS losses,
    count(*) FILTER (WHERE g.result = 'tie') AS ties,
    count(DISTINCT g.year) FILTER (
        WHERE o.champion = g.manager_id OR o.runner_up = g.manager_id
    ) AS title_games
FROM v_games g
JOIN managers m ON m.id = g.manager_id
LEFT JOIN season_outcomes o ON o.year = g.year
WHERE g.kind = 'playoff'
    AND g.opponent_id IS NOT NULL
GROUP BY g.manager_id, m.display_name;

-- Extra wins from the median game vs H2H-only, and whether that flipped a playoff.
CREATE VIEW v_median_tax AS
SELECT
    o.year,
    o.manager_id,
    o.display_name,
    h.wins AS h2h_wins,
    h.losses AS h2h_losses,
    h.ties AS h2h_ties,
    o.wins AS official_wins,
    o.losses AS official_losses,
    o.ties AS official_ties,
    coalesce(med.wins, 0) AS median_wins,
    coalesce(med.losses, 0) AS median_losses,
    coalesce(med.ties, 0) AS median_ties,
    o.wins - h.wins AS extra_wins,
    (p.manager_id IS NOT NULL) AS official_playoff,
    (hs.manager_id IS NOT NULL) AS h2h_playoff,
    (p.manager_id IS NOT NULL) <> (hs.manager_id IS NOT NULL) AS playoff_flip,
    (oc.champion = o.manager_id) AS champion
FROM v_standings_official o
JOIN v_standings_h2h h ON h.year = o.year AND h.manager_id = o.manager_id
JOIN seasons s ON s.year = o.year
LEFT JOIN (
    SELECT
        year,
        manager_id,
        count(*) FILTER (WHERE result = 'win') AS wins,
        count(*) FILTER (WHERE result = 'loss') AS losses,
        count(*) FILTER (WHERE result = 'tie') AS ties
    FROM v_games
    WHERE kind = 'vs_median'
    GROUP BY year, manager_id
) med ON med.year = o.year AND med.manager_id = o.manager_id
LEFT JOIN season_playoff_managers p
    ON p.year = o.year AND p.manager_id = o.manager_id
LEFT JOIN v_universe_seeds hs
    ON hs.universe = 'never_median' AND hs.year = o.year AND hs.manager_id = o.manager_id
LEFT JOIN season_outcomes oc ON oc.year = o.year
WHERE s.vs_median;
