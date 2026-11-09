-- Finished seasons for all-time season boards and earned hardware.
--
-- Distinct from v_posted_weeks. A posted week is one completed leg. A
-- finished regular season is every week before playoff_start_week posted,
-- or a champion already stored. 2026 starts playoffs at week 15 and weeks
-- 9-14 are not posted (week 9 is the live leg), so it stays open.
--
-- playoff_field_set is season_playoff_managers having any row. The loader
-- writes that table only once a champion exists, so the median-tax playoff
-- cell stays blank through an open season. Regular-season champ and most
-- points can be earned as soon as regular_season_complete flips, before
-- the title game.
--
-- Reloading 05_posted_weeks.sql drops this view (CASCADE on v_posted_weeks).
-- This file recreates it. Apply it on its own; do not reapply 05 to refresh it.

DROP VIEW IF EXISTS v_finished_seasons;

CREATE VIEW v_finished_seasons AS
SELECT
    s.year,
    (o.champion IS NOT NULL) AS champion_decided,
    (
        o.champion IS NOT NULL
        OR (
            o.playoff_start_week IS NOT NULL
            AND o.playoff_start_week > 1
            AND NOT EXISTS (
                SELECT 1
                FROM generate_series(1, o.playoff_start_week - 1) AS g(week)
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM v_posted_weeks pw
                    WHERE pw.year = s.year
                        AND pw.week = g.week
                )
            )
        )
    ) AS regular_season_complete,
    EXISTS (
        SELECT 1
        FROM season_playoff_managers p
        WHERE p.year = s.year
    ) AS playoff_field_set
FROM seasons s
LEFT JOIN season_outcomes o ON o.year = s.year;

COMMENT ON VIEW v_finished_seasons IS
    'regular_season_complete when a champion is stored or every week before playoff_start_week is posted. playoff_field_set when season_playoff_managers has a row.';
