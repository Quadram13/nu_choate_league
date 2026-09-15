-- Week marks, chairs, median tax, all-play career, playoff ledger.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_median_tax,
    v_playoff_career,
    v_all_play_career,
    v_chair_career,
    v_chair_season,
    v_marks_holders,
    v_stream_weeks,
    v_wire_starts,
    v_first_start_over,
    v_week_scores_ranked
CASCADE;

DROP MATERIALIZED VIEW IF EXISTS v_marks_weeks CASCADE;
DROP VIEW IF EXISTS v_marks_weeks CASCADE;

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

-- Starters this week whose current tenure began as a waiver or FA add
-- (this week or earlier). Distinct so a player with two matching windows
-- is not double-counted; keep the latest acquisition.
CREATE VIEW v_wire_starts AS
SELECT DISTINCT ON (pw.year, pw.week, pw.manager_id, pw.player_id)
    pw.year,
    pw.week,
    pw.manager_id,
    pw.manager_name,
    pw.player_id,
    pw.player_name,
    coalesce(w.position, pw.position) AS position,
    pw.matchup_id,
    pw.points,
    w.week AS add_week,
    w.transaction_id
FROM v_player_weeks pw
JOIN v_asset_value w
    ON w.player_id = pw.player_id
    AND w.manager_id = pw.manager_id
    AND w.type IN ('waiver', 'free_agent')
    AND (w.year < pw.year OR (w.year = pw.year AND w.week <= pw.week))
    AND (
        w.next_year IS NULL
        OR w.next_year > pw.year
        OR (w.next_year = pw.year AND pw.week < w.next_week)
    )
WHERE pw.started
ORDER BY
    pw.year,
    pw.week,
    pw.manager_id,
    pw.player_id,
    w.year DESC,
    w.week DESC,
    w.acquisition_id DESC;

-- First start of 15+ PF this season, any roster. Breakout week, not later
-- production from a player who already proved it.
CREATE VIEW v_first_start_over AS
SELECT
    year,
    player_id,
    min(week) AS week
FROM v_player_weeks
WHERE started
    AND points >= 15
GROUP BY year, player_id;

-- One pass: first 15+ start this season, then the week's highest among those.
CREATE VIEW v_stream_weeks AS
SELECT
    year,
    week,
    manager_id,
    manager_name,
    player_id,
    player_name,
    position,
    matchup_id,
    points
FROM (
    SELECT
        v.*,
        rank() OVER (
            PARTITION BY v.year, v.week
            ORDER BY v.points DESC, v.player_id
        ) AS rk
    FROM v_wire_starts v
    JOIN v_first_start_over f
        ON f.year = v.year
        AND f.player_id = v.player_id
        AND f.week = v.week
    WHERE v.points >= 15
) ranked
WHERE rk = 1;

-- Snapshot: week/season/records distinction boards. Computing live is ~9s
-- (correlated weekly maxima over the full union, including wire starts).
CREATE MATERIALIZED VIEW v_marks_weeks AS
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
    AND abs(g.margin) <= 5
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
    AND abs(g.margin) >= 40
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
    )
UNION ALL
SELECT
    v.year,
    v.week,
    'add',
    v.manager_id,
    v.manager_name,
    NULL,
    NULL,
    v.transaction_id,
    NULL,
    NULL,
    v.ros_vorp,
    v.player_id,
    v.player_name,
    v.position
FROM v_add_value v
WHERE v.type IN ('waiver', 'free_agent')
    AND v.ros_vorp IS NOT NULL
    AND v.ros_vorp >= 10
    AND EXISTS (
        SELECT 1
        FROM v_week_scores_ranked r
        WHERE r.year = v.year AND r.week = v.week
    )
    AND v.ros_vorp = (
        SELECT max(x.ros_vorp)
        FROM v_add_value x
        WHERE x.year = v.year
            AND x.week = v.week
            AND x.type IN ('waiver', 'free_agent')
    )
UNION ALL
SELECT
    v.year,
    v.week,
    'miss',
    v.manager_id,
    v.manager_name,
    v.won_player_id,
    v.won_player,
    v.missed_transaction_id,
    NULL,
    NULL,
    v.vorp_gap,
    v.missed_player_id,
    v.missed_player,
    v.missed_position
FROM v_waiver_misses v
WHERE v.vorp_gap IS NOT NULL
    AND v.vorp_gap >= 10
    AND EXISTS (
        SELECT 1
        FROM v_week_scores_ranked r
        WHERE r.year = v.year AND r.week = v.week
    )
    AND v.vorp_gap = (
        SELECT max(x.vorp_gap)
        FROM v_waiver_misses x
        WHERE x.year = v.year
            AND x.week = v.week
    )
UNION ALL
SELECT
    v.year,
    v.week,
    'dodge',
    v.manager_id,
    v.manager_name,
    v.lost_player_id,
    v.lost_player,
    v.won_transaction_id,
    NULL,
    NULL,
    v.vorp_gap,
    v.won_player_id,
    v.won_player,
    NULL
FROM v_waiver_dodges v
WHERE v.vorp_gap IS NOT NULL
    AND v.vorp_gap >= 10
    AND EXISTS (
        SELECT 1
        FROM v_week_scores_ranked r
        WHERE r.year = v.year AND r.week = v.week
    )
    AND v.vorp_gap = (
        SELECT max(x.vorp_gap)
        FROM v_waiver_dodges x
        WHERE x.year = v.year
            AND x.week = v.week
    )
UNION ALL
SELECT
    v.year,
    v.week,
    'stream',
    v.manager_id,
    v.manager_name,
    NULL,
    NULL,
    v.matchup_id,
    v.points,
    NULL,
    v.points,
    v.player_id,
    v.player_name,
    v.position
FROM v_stream_weeks v
WHERE EXISTS (
        SELECT 1
        FROM v_week_scores_ranked r
        WHERE r.year = v.year AND r.week = v.week
    )
WITH NO DATA;

CREATE INDEX v_marks_weeks_year_week ON v_marks_weeks (year, week);
CREATE INDEX v_marks_weeks_manager ON v_marks_weeks (manager_id);
CREATE INDEX v_marks_weeks_kind ON v_marks_weeks (kind);

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
