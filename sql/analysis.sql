-- Derived record-book views. Facts stay in facts.sql.
-- Bye / unpaired Sleeper weeks have week_scores but often no lineup_slots.

DROP VIEW IF EXISTS
    v_all_league,
    v_player_career,
    v_bench,
    v_player_weeks,
    v_trades,
    v_moves,
    v_draft,
    v_all_play_season,
    v_all_play,
    v_streaks,
    v_record_matchups,
    v_record_weeks,
    v_h2h,
    v_career,
    v_standings_median,
    v_standings_h2h,
    v_standings_official,
    v_games
CASCADE;

-- One row per manager per scored matchup. vs_median away (Median) has no manager and is dropped.
-- Filter through_week the same way Python does: skip weeks after last_scored_leg.
CREATE VIEW v_games AS
SELECT
    m.id AS matchup_id,
    m.year,
    m.week,
    m.kind,
    m.home_manager_id AS manager_id,
    m.away_manager_id AS opponent_id,
    m.home_points AS points,
    m.away_points AS opp_points,
    m.home_points - m.away_points AS margin,
    CASE
        WHEN m.home_points > m.away_points THEN 'win'
        WHEN m.home_points < m.away_points THEN 'loss'
        ELSE 'tie'
    END AS result
FROM matchups m
JOIN seasons s ON s.year = m.year
WHERE m.home_manager_id IS NOT NULL
    AND (s.through_week IS NULL OR m.week <= s.through_week)
    AND (m.home_points <> 0 OR m.away_points <> 0)
UNION ALL
SELECT
    m.id,
    m.year,
    m.week,
    m.kind,
    m.away_manager_id,
    m.home_manager_id,
    m.away_points,
    m.home_points,
    m.away_points - m.home_points,
    CASE
        WHEN m.away_points > m.home_points THEN 'win'
        WHEN m.away_points < m.home_points THEN 'loss'
        ELSE 'tie'
    END
FROM matchups m
JOIN seasons s ON s.year = m.year
WHERE m.away_manager_id IS NOT NULL
    AND (s.through_week IS NULL OR m.week <= s.through_week)
    AND (m.home_points <> 0 OR m.away_points <> 0);

CREATE VIEW v_standings_official AS
SELECT
    r.year,
    r.manager_id,
    m.display_name,
    t.team_name,
    r.wins,
    r.losses,
    r.ties,
    r.points_for,
    CASE
        WHEN r.wins + r.losses + r.ties = 0 THEN NULL
        ELSE (r.wins + 0.5 * r.ties) / (r.wins + r.losses + r.ties)
    END AS win_pct,
    rank() OVER (
        PARTITION BY r.year
        ORDER BY
            CASE
                WHEN r.wins + r.losses + r.ties = 0 THEN 0
                ELSE (r.wins + 0.5 * r.ties) / (r.wins + r.losses + r.ties)
            END DESC,
            r.points_for DESC,
            r.wins DESC,
            r.manager_id
    ) AS rank
FROM official_records r
JOIN team_seasons t ON t.year = r.year AND t.manager_id = r.manager_id
JOIN managers m ON m.id = r.manager_id;

-- H2H-only regular season (never-median). PF/PA from those games.
CREATE VIEW v_standings_h2h AS
SELECT
    g.year,
    g.manager_id,
    m.display_name,
    count(*) FILTER (WHERE g.result = 'win') AS wins,
    count(*) FILTER (WHERE g.result = 'loss') AS losses,
    count(*) FILTER (WHERE g.result = 'tie') AS ties,
    sum(g.points) AS points_for,
    sum(g.opp_points) AS points_against,
    CASE
        WHEN count(*) = 0 THEN NULL
        ELSE (count(*) FILTER (WHERE g.result = 'win') + 0.5 * count(*) FILTER (WHERE g.result = 'tie'))
            / count(*)
    END AS win_pct,
    rank() OVER (
        PARTITION BY g.year
        ORDER BY
            (count(*) FILTER (WHERE g.result = 'win') + 0.5 * count(*) FILTER (WHERE g.result = 'tie'))
                / count(*) DESC,
            sum(g.points) DESC,
            count(*) FILTER (WHERE g.result = 'win') DESC,
            g.manager_id
    ) AS rank
FROM v_games g
JOIN managers m ON m.id = g.manager_id
WHERE g.kind = 'regular'
GROUP BY g.year, g.manager_id, m.display_name;

-- Always-median: W-L from regular + vs_median, PF/PA from H2H only (matches apply_records).
CREATE VIEW v_standings_median AS
SELECT
    w.year,
    w.manager_id,
    m.display_name,
    w.wins,
    w.losses,
    w.ties,
    coalesce(p.points_for, 0) AS points_for,
    coalesce(p.points_against, 0) AS points_against,
    CASE
        WHEN w.wins + w.losses + w.ties = 0 THEN NULL
        ELSE (w.wins + 0.5 * w.ties) / (w.wins + w.losses + w.ties)
    END AS win_pct,
    rank() OVER (
        PARTITION BY w.year
        ORDER BY
            CASE
                WHEN w.wins + w.losses + w.ties = 0 THEN 0
                ELSE (w.wins + 0.5 * w.ties) / (w.wins + w.losses + w.ties)
            END DESC,
            coalesce(p.points_for, 0) DESC,
            w.wins DESC,
            w.manager_id
    ) AS rank
FROM (
    SELECT
        year,
        manager_id,
        count(*) FILTER (WHERE result = 'win') AS wins,
        count(*) FILTER (WHERE result = 'loss') AS losses,
        count(*) FILTER (WHERE result = 'tie') AS ties
    FROM v_games
    WHERE kind IN ('regular', 'vs_median')
    GROUP BY year, manager_id
) w
LEFT JOIN (
    SELECT
        year,
        manager_id,
        sum(points) AS points_for,
        sum(opp_points) AS points_against
    FROM v_games
    WHERE kind = 'regular'
    GROUP BY year, manager_id
) p ON p.year = w.year AND p.manager_id = w.manager_id
JOIN managers m ON m.id = w.manager_id;

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

CREATE VIEW v_draft AS
SELECT
    d.year,
    d.overall,
    d.round,
    d.manager_id,
    m.display_name AS manager_name,
    d.player_id,
    coalesce(p.display_name, d.player_name) AS player_name,
    p.position,
    d.keeper
FROM draft_picks d
JOIN managers m ON m.id = d.manager_id
LEFT JOIN players p ON p.id = d.player_id;

CREATE VIEW v_moves AS
SELECT
    t.id AS transaction_id,
    t.year,
    t.week,
    t.type,
    t.status,
    t.at,
    mv.direction,
    mv.manager_id,
    m.display_name AS manager_name,
    mv.player_id,
    coalesce(p.display_name, mv.player_name) AS player_name,
    p.position
FROM transactions t
JOIN transaction_moves mv ON mv.transaction_id = t.id
JOIN managers m ON m.id = mv.manager_id
LEFT JOIN players p ON p.id = mv.player_id;

CREATE VIEW v_trades AS
SELECT
    t.id AS transaction_id,
    t.year,
    t.week,
    t.status,
    t.at,
    a.player_id,
    coalesce(p.display_name, a.player_name) AS player_name,
    p.position,
    d.manager_id AS from_manager_id,
    fm.display_name AS from_manager_name,
    a.manager_id AS to_manager_id,
    tm.display_name AS to_manager_name
FROM transactions t
JOIN transaction_moves a ON a.transaction_id = t.id AND a.direction = 'add'
LEFT JOIN transaction_moves d
    ON d.transaction_id = t.id
    AND d.direction = 'drop'
    AND d.player_id = a.player_id
LEFT JOIN managers fm ON fm.id = d.manager_id
JOIN managers tm ON tm.id = a.manager_id
LEFT JOIN players p ON p.id = a.player_id
WHERE t.type = 'trade';

CREATE VIEW v_player_weeks AS
SELECT
    mu.year,
    mu.week,
    mu.kind,
    mu.id AS matchup_id,
    CASE WHEN ls.side = 'home' THEN mu.home_manager_id ELSE mu.away_manager_id END AS manager_id,
    m.display_name AS manager_name,
    ls.player_id,
    coalesce(p.display_name, ls.player_name) AS player_name,
    p.position,
    ls.slot,
    ls.started,
    ls.points
FROM lineup_slots ls
JOIN matchups mu ON mu.id = ls.matchup_id
LEFT JOIN managers m
    ON m.id = CASE WHEN ls.side = 'home' THEN mu.home_manager_id ELSE mu.away_manager_id END
LEFT JOIN players p ON p.id = ls.player_id
WHERE CASE WHEN ls.side = 'home' THEN mu.home_manager_id ELSE mu.away_manager_id END IS NOT NULL;

CREATE VIEW v_bench AS
SELECT
    year,
    week,
    manager_id,
    manager_name,
    sum(points) FILTER (WHERE started) AS started_points,
    sum(points) FILTER (WHERE NOT started) AS bench_points,
    sum(points) AS roster_points
FROM v_player_weeks
WHERE kind IN ('regular', 'playoff', 'consolation')
GROUP BY year, week, manager_id, manager_name;

CREATE VIEW v_player_career AS
SELECT
    pw.player_id,
    coalesce(p.display_name, max(pw.player_name)) AS player_name,
    p.position,
    count(*) FILTER (WHERE pw.started) AS starts,
    count(*) FILTER (WHERE NOT pw.started) AS bench_weeks,
    coalesce(sum(pw.points) FILTER (WHERE pw.started), 0) AS starter_points,
    count(DISTINCT pw.year) AS seasons,
    min(pw.year) AS first_year,
    max(pw.year) AS last_year,
    coalesce(d.times_drafted, 0) AS times_drafted,
    coalesce(mv.adds, 0) AS times_added,
    coalesce(mv.drops, 0) AS times_dropped,
    coalesce(tr.times_traded, 0) AS times_traded
FROM v_player_weeks pw
LEFT JOIN players p ON p.id = pw.player_id
LEFT JOIN (
    SELECT player_id, count(*) AS times_drafted
    FROM draft_picks
    GROUP BY player_id
) d ON d.player_id = pw.player_id
LEFT JOIN (
    SELECT
        player_id,
        count(*) FILTER (WHERE direction = 'add') AS adds,
        count(*) FILTER (WHERE direction = 'drop') AS drops
    FROM v_moves
    WHERE type <> 'trade'
    GROUP BY player_id
) mv ON mv.player_id = pw.player_id
LEFT JOIN (
    SELECT player_id, count(*) AS times_traded
    FROM v_trades
    GROUP BY player_id
) tr ON tr.player_id = pw.player_id
GROUP BY pw.player_id, p.display_name, p.position, d.times_drafted, mv.adds, mv.drops, tr.times_traded;

CREATE VIEW v_all_league AS
WITH started AS (
    SELECT
        year,
        week,
        position,
        player_id,
        player_name,
        manager_id,
        manager_name,
        points,
        rank() OVER (
            PARTITION BY year, week, position
            ORDER BY points DESC, player_id
        ) AS high_rank,
        rank() OVER (
            PARTITION BY year, week, position
            ORDER BY points ASC, player_id
        ) AS low_rank
    FROM v_player_weeks
    WHERE started
        AND position IS NOT NULL
        AND kind IN ('regular', 'playoff')
),
best AS (
    SELECT year, week, position, points AS best_points
    FROM started
    WHERE high_rank = 1
),
bench AS (
    SELECT
        pw.year,
        pw.week,
        pw.position,
        pw.player_id,
        pw.player_name,
        pw.manager_id,
        pw.manager_name,
        pw.points
    FROM v_player_weeks pw
    JOIN best b
        ON b.year = pw.year
        AND b.week = pw.week
        AND b.position = pw.position
    WHERE NOT pw.started
        AND pw.position IS NOT NULL
        AND pw.kind IN ('regular', 'playoff')
        AND pw.points > b.best_points
)
SELECT
    year,
    week,
    position,
    'all_league' AS kind,
    player_id,
    player_name,
    manager_id,
    manager_name,
    points
FROM started
WHERE high_rank = 1
UNION ALL
SELECT
    year,
    week,
    position,
    'busch',
    player_id,
    player_name,
    manager_id,
    manager_name,
    points
FROM started
WHERE low_rank = 1
UNION ALL
SELECT
    year,
    week,
    position,
    'benched_all_star',
    player_id,
    player_name,
    manager_id,
    manager_name,
    points
FROM bench;
