-- Posted weeks. One predicate for every surface that should ignore a live leg.
--
-- seasons.through_week is the current NFL week, not the last completed one.
-- 2026 week 9 is stored while it is in progress (median team total 2.10).
-- Every other counted week in 2022-2026 has a median of at least 89.95.
-- A week is posted when that median is at least 40, the same gap the
-- volatility sample uses, and the week is not past through_week.
--
-- Record weeks, games, all-play, marks, the schedule desk, replacement,
-- lineup aggregates, player counting, and lineup stacks join this view.
-- v_player_weeks
-- stays unfiltered so a week page can still open the in-progress leg.
-- v_volatility_posted_weeks is this set under the original name.

DROP VIEW IF EXISTS v_posted_weeks CASCADE;

CREATE VIEW v_posted_weeks AS
SELECT
    w.year,
    w.week
FROM week_scores w
JOIN seasons s ON s.year = w.year
WHERE s.through_week IS NULL OR w.week <= s.through_week
GROUP BY w.year, w.week
HAVING percentile_cont(0.5) WITHIN GROUP (ORDER BY w.points) >= 40;

COMMENT ON VIEW v_posted_weeks IS
    'Weeks whose median team total is at least 40, and not past seasons.through_week. Drops the live leg before scores post.';
