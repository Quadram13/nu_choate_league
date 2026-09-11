-- Standings: official, H2H-only (never-median), and always-median.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_standings_median,
    v_vs_median_effective,
    v_standings_h2h,
    v_standings_official
CASCADE;

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

-- Stored vs-median games, or synthesized from that week's regular H2H scores
-- when the season never played vs-median (matches alternate._synthesize_median).
CREATE VIEW v_vs_median_effective AS
SELECT
    year,
    week,
    manager_id,
    points,
    opp_points,
    result
FROM v_games
WHERE kind = 'vs_median'
UNION ALL
SELECT
    g.year,
    g.week,
    g.manager_id,
    g.points,
    med.median_points AS opp_points,
    CASE
        WHEN g.points > med.median_points THEN 'win'
        WHEN g.points < med.median_points THEN 'loss'
        ELSE 'tie'
    END AS result
FROM v_games g
JOIN (
    SELECT
        year,
        week,
        round((percentile_cont(0.5) WITHIN GROUP (ORDER BY points))::numeric, 2) AS median_points
    FROM v_games
    WHERE kind = 'regular'
    GROUP BY year, week
) med ON med.year = g.year AND med.week = g.week
WHERE g.kind = 'regular'
    AND g.year NOT IN (
        SELECT DISTINCT year
        FROM v_games
        WHERE kind = 'vs_median'
    );

-- Always-median: W-L from regular + effective vs-median, PF/PA from H2H only.
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
    FROM (
        SELECT year, manager_id, result
        FROM v_games
        WHERE kind = 'regular'
        UNION ALL
        SELECT year, manager_id, result
        FROM v_vs_median_effective
    ) games
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
