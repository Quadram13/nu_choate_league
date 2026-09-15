-- Power board, week-rank heat, points race, schedule desk.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_schedule_desk,
    v_points_race,
    v_power_board,
    v_all_play_running
CASCADE;

-- Cumulative all-play through each regular week.
CREATE VIEW v_all_play_running AS
SELECT
    year,
    week,
    manager_id,
    display_name,
    sum(wins) OVER (
        PARTITION BY year, manager_id
        ORDER BY week
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS wins,
    sum(losses) OVER (
        PARTITION BY year, manager_id
        ORDER BY week
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS losses,
    sum(ties) OVER (
        PARTITION BY year, manager_id
        ORDER BY week
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS ties
FROM v_all_play;

CREATE VIEW v_power_board AS
SELECT
    ranked.year,
    ranked.week,
    ranked.manager_id,
    ranked.display_name,
    ranked.wins,
    ranked.losses,
    ranked.ties,
    ranked.win_pct,
    ranked.power_rank,
    lag(ranked.power_rank) OVER (
        PARTITION BY ranked.year, ranked.manager_id
        ORDER BY ranked.week
    ) AS prev_rank
FROM (
    SELECT
        r.year,
        r.week,
        r.manager_id,
        r.display_name,
        r.wins,
        r.losses,
        r.ties,
        CASE
            WHEN r.wins + r.losses + r.ties = 0 THEN NULL
            ELSE (r.wins + 0.5 * r.ties) / (r.wins + r.losses + r.ties)
        END AS win_pct,
        rank() OVER (
            PARTITION BY r.year, r.week
            ORDER BY
                (r.wins + 0.5 * r.ties) / NULLIF(r.wins + r.losses + r.ties, 0) DESC NULLS LAST,
                r.wins DESC,
                r.manager_id
        ) AS power_rank
    FROM v_all_play_running r
) ranked;

CREATE VIEW v_points_race AS
SELECT
    w.year,
    w.week,
    w.manager_id,
    m.display_name,
    w.points,
    sum(w.points) OVER (
        PARTITION BY w.year, w.manager_id
        ORDER BY w.week
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative
FROM week_scores w
JOIN managers m ON m.id = w.manager_id
JOIN seasons s ON s.year = w.year
WHERE (s.through_week IS NULL OR w.week <= s.through_week)
    AND EXISTS (
        SELECT 1
        FROM matchups mu
        WHERE mu.year = w.year
            AND mu.week = w.week
            AND mu.kind = 'regular'
            AND (mu.home_points <> 0 OR mu.away_points <> 0)
    );

-- If manager had schedule_id's opponents each week.
CREATE VIEW v_schedule_desk AS
SELECT
    mine.year,
    mine.manager_id,
    mm.display_name AS manager_name,
    sched.manager_id AS schedule_id,
    sm.display_name AS schedule_name,
    count(*) AS games,
    count(*) FILTER (WHERE mine.points > sched.opp_points) AS wins,
    count(*) FILTER (WHERE mine.points < sched.opp_points) AS losses,
    count(*) FILTER (WHERE mine.points = sched.opp_points) AS ties,
    CASE
        WHEN count(*) = 0 THEN NULL
        ELSE (
            count(*) FILTER (WHERE mine.points > sched.opp_points)
            + 0.5 * count(*) FILTER (WHERE mine.points = sched.opp_points)
        ) / count(*)
    END AS win_pct
FROM week_scores mine
JOIN v_games sched
    ON sched.year = mine.year
    AND sched.week = mine.week
    AND sched.kind = 'regular'
    AND sched.opponent_id IS NOT NULL
JOIN managers mm ON mm.id = mine.manager_id
JOIN managers sm ON sm.id = sched.manager_id
JOIN seasons s ON s.year = mine.year
WHERE mine.manager_id <> sched.manager_id
    AND (s.through_week IS NULL OR mine.week <= s.through_week)
GROUP BY
    mine.year,
    mine.manager_id,
    mm.display_name,
    sched.manager_id,
    sm.display_name;
