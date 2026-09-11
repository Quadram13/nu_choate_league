-- Games: one row per manager per scored matchup (base for most views).
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_games
CASCADE;

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
