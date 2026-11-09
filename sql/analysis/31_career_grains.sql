-- Career-board grains (issue #56).
--
-- v_winners_bracket_career counts a playoff game when both managers are in
-- season_playoff_managers. That is the same filter as v_h2h and the member
-- lede. A kind=playoff game in the losers bracket stays out.
-- v_playoff_career is unchanged: the records "most playoff wins" board
-- still reads it.
--
-- v_career_drought counts completed seasons the manager actually played
-- after the last title, and after the last winners-bracket appearance.
-- A season counts once its champion is stored. The open season does not
-- extend a drought, and a year with no official record does not either.
-- No title or no winners-bracket appearance leaves that drought NULL
-- ("never" on the page).
--
-- Reloading 05_posted_weeks.sql or 10_games.sql drops v_games CASCADE,
-- and reloading 06_finished_seasons.sql drops v_finished_seasons. Either
-- drop takes these views with it. Reapply this file afterward.

DROP VIEW IF EXISTS v_career_drought;
DROP VIEW IF EXISTS v_winners_bracket_career;

CREATE VIEW v_winners_bracket_career AS
SELECT
    g.manager_id,
    count(*)::integer AS games,
    count(*) FILTER (WHERE g.result = 'win')::integer AS wins,
    count(*) FILTER (WHERE g.result = 'loss')::integer AS losses,
    count(*) FILTER (WHERE g.result = 'tie')::integer AS ties
FROM v_games g
JOIN season_playoff_managers pm
    ON pm.year = g.year AND pm.manager_id = g.manager_id
JOIN season_playoff_managers po
    ON po.year = g.year AND po.manager_id = g.opponent_id
WHERE g.kind = 'playoff'
    AND g.opponent_id IS NOT NULL
GROUP BY g.manager_id;

COMMENT ON VIEW v_winners_bracket_career IS
    'Winners-bracket playoff games: kind=playoff and both managers in season_playoff_managers.';

CREATE VIEW v_career_drought AS
WITH played AS (
    SELECT r.manager_id, r.year
    FROM official_records r
    JOIN v_finished_seasons fin
        ON fin.year = r.year
        AND fin.champion_decided
    WHERE r.wins + r.losses + r.ties > 0
        OR r.points_for > 0
),
last_title AS (
    SELECT o.champion AS manager_id, max(o.year) AS year
    FROM season_outcomes o
    WHERE o.champion IS NOT NULL
    GROUP BY o.champion
),
last_playoff AS (
    SELECT p.manager_id, max(p.year) AS year
    FROM season_playoff_managers p
    GROUP BY p.manager_id
)
SELECT
    m.id AS manager_id,
    lt.year AS last_title,
    lp.year AS last_playoff,
    CASE
        WHEN lt.year IS NULL THEN NULL
        ELSE (
            SELECT count(*)::integer
            FROM played p
            WHERE p.manager_id = m.id
                AND p.year > lt.year
        )
    END AS title_drought,
    CASE
        WHEN lp.year IS NULL THEN NULL
        ELSE (
            SELECT count(*)::integer
            FROM played p
            WHERE p.manager_id = m.id
                AND p.year > lp.year
        )
    END AS playoff_drought
FROM managers m
LEFT JOIN last_title lt ON lt.manager_id = m.id
LEFT JOIN last_playoff lp ON lp.manager_id = m.id;

COMMENT ON VIEW v_career_drought IS
    'Completed seasons played after the last title and after the last winners-bracket appearance. NULL when that appearance does not exist. Open seasons and years with no official record are excluded.';
