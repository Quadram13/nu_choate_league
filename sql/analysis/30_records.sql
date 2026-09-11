-- Record book: career, head-to-head, record weeks/matchups, streaks, all-play.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_all_play_season,
    v_all_play,
    v_streaks,
    v_record_matchups,
    v_record_weeks,
    v_h2h,
    v_career
CASCADE;

CREATE VIEW v_career AS
SELECT
    r.manager_id,
    m.display_name,
    count(*) AS seasons,
    sum(r.wins) AS wins,
    sum(r.losses) AS losses,
    sum(r.ties) AS ties,
    sum(r.points_for) AS points_for,
    CASE
        WHEN sum(r.wins + r.losses + r.ties) = 0 THEN NULL
        ELSE (sum(r.wins) + 0.5 * sum(r.ties)) / sum(r.wins + r.losses + r.ties)
    END AS win_pct,
    count(*) FILTER (WHERE o.champion = r.manager_id) AS titles,
    count(*) FILTER (WHERE o.runner_up = r.manager_id) AS runner_up,
    count(*) FILTER (WHERE o.regular_season_champion = r.manager_id) AS regular_season_titles,
    count(*) FILTER (WHERE o.most_points = r.manager_id) AS most_points_titles,
    count(*) FILTER (WHERE p.manager_id IS NOT NULL) AS playoff_appearances
FROM official_records r
JOIN managers m ON m.id = r.manager_id
LEFT JOIN season_outcomes o ON o.year = r.year
LEFT JOIN season_playoff_managers p ON p.year = r.year AND p.manager_id = r.manager_id
WHERE r.wins + r.losses + r.ties > 0 OR r.points_for > 0
GROUP BY r.manager_id, m.display_name;

-- Regular H2H plus winners-bracket playoff only (both managers in season_playoff_managers).
-- One row per unordered pair. Stats are from the lexicographically smaller manager_id.
CREATE VIEW v_h2h AS
SELECT
    least(g.manager_id, g.opponent_id) AS left_id,
    lm.display_name AS left_name,
    greatest(g.manager_id, g.opponent_id) AS right_id,
    rm.display_name AS right_name,
    count(*) FILTER (WHERE g.kind = 'regular') AS regular_games,
    count(*) FILTER (WHERE g.kind = 'regular' AND g.result = 'win') AS regular_wins,
    count(*) FILTER (WHERE g.kind = 'regular' AND g.result = 'loss') AS regular_losses,
    count(*) FILTER (WHERE g.kind = 'regular' AND g.result = 'tie') AS regular_ties,
    sum(g.points) FILTER (WHERE g.kind = 'regular') AS regular_points_for,
    sum(g.opp_points) FILTER (WHERE g.kind = 'regular') AS regular_points_against,
    count(*) FILTER (WHERE g.kind = 'playoff') AS playoff_games,
    count(*) FILTER (WHERE g.kind = 'playoff' AND g.result = 'win') AS playoff_wins,
    count(*) FILTER (WHERE g.kind = 'playoff' AND g.result = 'loss') AS playoff_losses,
    count(*) FILTER (WHERE g.kind = 'playoff' AND g.result = 'tie') AS playoff_ties,
    sum(g.points) FILTER (WHERE g.kind = 'playoff') AS playoff_points_for,
    sum(g.opp_points) FILTER (WHERE g.kind = 'playoff') AS playoff_points_against,
    avg(g.margin) FILTER (WHERE g.kind = 'regular') AS regular_avg_margin,
    max(abs(g.margin)) FILTER (WHERE g.kind = 'regular') AS regular_biggest_blowout,
    min(abs(g.margin)) FILTER (WHERE g.kind = 'regular') AS regular_closest
FROM v_games g
JOIN managers lm ON lm.id = least(g.manager_id, g.opponent_id)
JOIN managers rm ON rm.id = greatest(g.manager_id, g.opponent_id)
LEFT JOIN season_playoff_managers pm ON pm.year = g.year AND pm.manager_id = g.manager_id
LEFT JOIN season_playoff_managers po ON po.year = g.year AND po.manager_id = g.opponent_id
WHERE g.opponent_id IS NOT NULL
    AND (
        g.kind = 'regular'
        OR (g.kind = 'playoff' AND pm.manager_id IS NOT NULL AND po.manager_id IS NOT NULL)
    )
    AND g.manager_id < g.opponent_id
GROUP BY
    least(g.manager_id, g.opponent_id),
    lm.display_name,
    greatest(g.manager_id, g.opponent_id),
    rm.display_name;

CREATE VIEW v_record_weeks AS
SELECT
    w.year,
    w.week,
    w.manager_id,
    m.display_name,
    w.points,
    w.paired,
    rank() OVER (ORDER BY w.points DESC, w.year, w.week, w.manager_id) AS high_rank,
    rank() OVER (ORDER BY w.points ASC, w.year, w.week, w.manager_id) AS low_rank
FROM week_scores w
JOIN seasons s ON s.year = w.year
JOIN managers m ON m.id = w.manager_id
WHERE s.through_week IS NULL OR w.week <= s.through_week;

CREATE VIEW v_record_matchups AS
SELECT
    g.matchup_id,
    g.year,
    g.week,
    g.kind,
    g.manager_id,
    hm.display_name AS manager_name,
    g.opponent_id,
    om.display_name AS opponent_name,
    g.points,
    g.opp_points,
    g.margin,
    abs(g.margin) AS abs_margin,
    g.result,
    rank() OVER (ORDER BY abs(g.margin) DESC, g.year, g.week, g.matchup_id) AS blowout_rank,
    rank() OVER (ORDER BY abs(g.margin) ASC, g.year, g.week, g.matchup_id) AS closest_rank
FROM v_games g
JOIN managers hm ON hm.id = g.manager_id
LEFT JOIN managers om ON om.id = g.opponent_id
WHERE g.kind = 'regular'
    AND g.opponent_id IS NOT NULL
    AND g.manager_id < g.opponent_id;

CREATE VIEW v_streaks AS
WITH ordered AS (
    SELECT
        manager_id,
        year,
        week,
        matchup_id,
        result,
        row_number() OVER (PARTITION BY manager_id ORDER BY year, week, matchup_id) AS rn
    FROM v_games
    WHERE kind = 'regular'
        AND result IN ('win', 'loss')
),
islands AS (
    SELECT
        manager_id,
        result,
        year,
        week,
        matchup_id,
        rn - row_number() OVER (
            PARTITION BY manager_id, result
            ORDER BY year, week, matchup_id
        ) AS island
    FROM ordered
),
summarized AS (
    SELECT
        manager_id,
        result,
        island,
        count(*) AS length,
        min(year * 100 + week) AS start_yw,
        max(year * 100 + week) AS end_yw
    FROM islands
    GROUP BY manager_id, result, island
),
last_game AS (
    SELECT DISTINCT ON (manager_id)
        manager_id,
        year * 100 + week AS last_yw
    FROM ordered
    ORDER BY manager_id, year DESC, week DESC, matchup_id DESC
)
SELECT
    s.manager_id,
    m.display_name,
    s.result,
    s.length,
    s.start_yw / 100 AS start_year,
    s.start_yw % 100 AS start_week,
    s.end_yw / 100 AS end_year,
    s.end_yw % 100 AS end_week,
    (l.last_yw = s.end_yw) AS is_current
FROM summarized s
JOIN managers m ON m.id = s.manager_id
LEFT JOIN last_game l ON l.manager_id = s.manager_id;

CREATE VIEW v_all_play AS
SELECT
    a.year,
    a.week,
    a.manager_id,
    m.display_name,
    a.points,
    count(*) FILTER (WHERE a.points > b.points) AS wins,
    count(*) FILTER (WHERE a.points < b.points) AS losses,
    count(*) FILTER (WHERE a.points = b.points) AS ties
FROM week_scores a
JOIN week_scores b
    ON a.year = b.year
    AND a.week = b.week
    AND a.manager_id <> b.manager_id
JOIN seasons s ON s.year = a.year
JOIN managers m ON m.id = a.manager_id
WHERE s.through_week IS NULL OR a.week <= s.through_week
GROUP BY a.year, a.week, a.manager_id, m.display_name, a.points;

CREATE VIEW v_all_play_season AS
SELECT
    year,
    manager_id,
    display_name,
    sum(wins) AS wins,
    sum(losses) AS losses,
    sum(ties) AS ties,
    CASE
        WHEN sum(wins + losses + ties) = 0 THEN NULL
        ELSE (sum(wins) + 0.5 * sum(ties)) / sum(wins + losses + ties)
    END AS win_pct
FROM v_all_play
GROUP BY year, manager_id, display_name;
