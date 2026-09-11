-- Luck: H2H result vs league-wide scoring rank (weekly, season, career).
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_luck_career,
    v_luck_season,
    v_luck_weeks
CASCADE;

-- Fantasy Genius luck: H2H result vs league-wide PF rank that week.
-- Top half = pf_rank <= teams/2 (10-team: ranks 1–5). Lucky win = won from 6th or worse.
-- Expected wins = sum of that week's all-play win% (random opponent).
-- Underdog/favorite: season-average PF vs opponent (not this week's points; those already decide H2H).
CREATE VIEW v_luck_weeks AS
SELECT
    g.year,
    g.week,
    g.matchup_id,
    g.manager_id,
    m.display_name,
    g.opponent_id,
    om.display_name AS opponent_name,
    g.result,
    g.points,
    g.opp_points,
    r.pf_rank,
    opp.pf_rank AS opp_pf_rank,
    r.teams,
    (g.result = 'win' AND r.pf_rank > r.teams / 2) AS lucky_win,
    (g.result = 'loss' AND r.pf_rank <= r.teams / 2) AS unlucky_loss,
    (g.result = 'win' AND my_avg.avg_pf < opp_avg.avg_pf) AS underdog_win,
    (g.result = 'loss' AND my_avg.avg_pf > opp_avg.avg_pf) AS favorite_loss,
    ap.wins AS all_play_wins,
    ap.losses AS all_play_losses,
    ap.ties AS all_play_ties,
    CASE
        WHEN ap.wins + ap.losses + ap.ties = 0 THEN NULL
        ELSE (ap.wins + 0.5 * ap.ties) / (ap.wins + ap.losses + ap.ties)
    END AS expected_win
FROM v_games g
JOIN managers m ON m.id = g.manager_id
LEFT JOIN managers om ON om.id = g.opponent_id
JOIN (
    SELECT
        year,
        week,
        manager_id,
        points,
        rank() OVER (
            PARTITION BY year, week
            ORDER BY points DESC, manager_id
        ) AS pf_rank,
        count(*) OVER (PARTITION BY year, week) AS teams
    FROM week_scores
) r ON r.year = g.year AND r.week = g.week AND r.manager_id = g.manager_id
LEFT JOIN (
    SELECT
        year,
        week,
        manager_id,
        rank() OVER (
            PARTITION BY year, week
            ORDER BY points DESC, manager_id
        ) AS pf_rank
    FROM week_scores
) opp ON opp.year = g.year AND opp.week = g.week AND opp.manager_id = g.opponent_id
LEFT JOIN (
    SELECT year, manager_id, avg(points) AS avg_pf
    FROM week_scores
    GROUP BY year, manager_id
) my_avg ON my_avg.year = g.year AND my_avg.manager_id = g.manager_id
LEFT JOIN (
    SELECT year, manager_id, avg(points) AS avg_pf
    FROM week_scores
    GROUP BY year, manager_id
) opp_avg ON opp_avg.year = g.year AND opp_avg.manager_id = g.opponent_id
LEFT JOIN v_all_play ap
    ON ap.year = g.year AND ap.week = g.week AND ap.manager_id = g.manager_id
WHERE g.kind = 'regular'
    AND g.opponent_id IS NOT NULL;

CREATE VIEW v_luck_season AS
SELECT
    year,
    manager_id,
    display_name,
    count(*) AS games,
    count(*) FILTER (WHERE result = 'win') AS wins,
    count(*) FILTER (WHERE result = 'loss') AS losses,
    count(*) FILTER (WHERE result = 'tie') AS ties,
    count(*) FILTER (WHERE lucky_win) AS lucky_wins,
    count(*) FILTER (WHERE unlucky_loss) AS unlucky_losses,
    count(*) FILTER (WHERE lucky_win) - count(*) FILTER (WHERE unlucky_loss) AS net_luck,
    count(*) FILTER (WHERE underdog_win) AS underdog_wins,
    count(*) FILTER (WHERE favorite_loss) AS favorite_losses,
    sum(expected_win) AS expected_wins,
    (count(*) FILTER (WHERE result = 'win') + 0.5 * count(*) FILTER (WHERE result = 'tie'))
        - sum(expected_win) AS wins_vs_expected
FROM v_luck_weeks
GROUP BY year, manager_id, display_name;

CREATE VIEW v_luck_career AS
SELECT
    manager_id,
    display_name,
    count(*) AS seasons,
    sum(games) AS games,
    sum(wins) AS wins,
    sum(losses) AS losses,
    sum(ties) AS ties,
    sum(lucky_wins) AS lucky_wins,
    sum(unlucky_losses) AS unlucky_losses,
    sum(net_luck) AS net_luck,
    sum(underdog_wins) AS underdog_wins,
    sum(favorite_losses) AS favorite_losses,
    sum(expected_wins) AS expected_wins,
    sum(wins_vs_expected) AS wins_vs_expected
FROM v_luck_season
GROUP BY manager_id, display_name;
