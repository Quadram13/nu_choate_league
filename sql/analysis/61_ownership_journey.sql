-- Ownership journey (issue #35).
--
-- v_ownership_stints partitions every rostered player_week_scores row
-- into one run: same player, same manager, same year, consecutive weeks.
-- A missing week starts a new run, matching the player-page rule.
-- from_year and to_year are both stored. Week numbers reset each season
-- and the offseason is a gap, so a run does not cross years.
--
-- Acquisition is the draft (week 0) or the latest complete add of type
-- waiver, free_agent, or trade for that manager in that year with
-- transaction week <= the run's first week. A later run in the same
-- hold keeps that event when nothing newer landed. A blank type has no
-- such event. Commissioner rows are not one of the four types; the two
-- stored ones do not start a run. Every trade transaction is two
-- managers, so a trade add is the receiving manager's event.
--
-- v_player_managers is distinct managers on rostered weeks, career.
-- v_player_managers_season is the same count inside one year.
-- v_player_rings separates three championship grains:
--   champ_roster_weeks: rostered weeks on that year's champion, bench included
--   rings: seasons with any start for that champion
--   title_starts / title_points: a start on the champion in a playoff
--     week on or after playoff_start_week. The rows are lineup_slots
--     on matchups, which is the v_player_weeks grain the player page
--     uses. The view does not reference v_player_weeks, so reapplying
--     60_players.sql does not drop it.

DROP VIEW IF EXISTS v_player_rings;
DROP VIEW IF EXISTS v_player_managers_season;
DROP VIEW IF EXISTS v_player_managers;
DROP VIEW IF EXISTS v_ownership_stints;

CREATE VIEW v_ownership_stints AS
WITH rostered AS (
    SELECT
        s.year,
        s.week,
        s.player_id,
        s.player_name,
        s.manager_id,
        s.started,
        s.points,
        s.week - row_number() OVER (
            PARTITION BY s.player_id, s.manager_id, s.year
            ORDER BY s.week
        ) AS island
    FROM player_week_scores s
    WHERE s.rostered
        AND s.manager_id IS NOT NULL
),
stints AS (
    SELECT
        player_id,
        manager_id,
        year AS from_year,
        year AS to_year,
        min(week) AS from_week,
        max(week) AS to_week,
        count(*)::integer AS weeks,
        count(*) FILTER (WHERE started)::integer AS tenure_starts,
        coalesce(sum(points), 0)::double precision AS tenure_points,
        max(player_name) AS score_name
    FROM rostered
    GROUP BY player_id, manager_id, year, island
),
adds AS (
    SELECT
        d.player_id,
        d.manager_id,
        d.year,
        0 AS week,
        'draft'::text AS acquisition_type,
        NULL::text AS transaction_id,
        NULL::bigint AS at
    FROM draft_picks d
    UNION ALL
    SELECT
        mv.player_id,
        mv.manager_id,
        t.year,
        t.week,
        t.type AS acquisition_type,
        t.id AS transaction_id,
        t.at
    FROM transaction_moves mv
    JOIN transactions t ON t.id = mv.transaction_id
    WHERE mv.direction = 'add'
        AND t.status = 'complete'
        AND t.type IN ('draft', 'waiver', 'free_agent', 'trade')
)
SELECT
    st.player_id,
    coalesce(pl.display_name, st.score_name) AS player_name,
    pl.position,
    st.manager_id,
    m.display_name AS manager_name,
    st.from_year,
    st.from_week,
    st.to_year,
    st.to_week,
    acq.acquisition_type,
    acq.transaction_id,
    st.weeks,
    st.tenure_starts,
    st.tenure_points
FROM stints st
LEFT JOIN managers m ON m.id = st.manager_id
LEFT JOIN players pl ON pl.id = st.player_id
LEFT JOIN LATERAL (
    SELECT a.acquisition_type, a.transaction_id
    FROM adds a
    WHERE a.player_id = st.player_id
        AND a.manager_id = st.manager_id
        AND a.year = st.from_year
        AND a.week <= st.from_week
    ORDER BY a.week DESC, coalesce(a.at, 0) DESC, a.transaction_id DESC NULLS LAST
    LIMIT 1
) acq ON true;

COMMENT ON VIEW v_ownership_stints IS
    'Rostered runs of consecutive weeks for one manager in one year. Acquisition is the draft or the latest complete waiver, free-agent add, or trade on or before the run starts.';

CREATE VIEW v_player_managers AS
SELECT
    s.player_id,
    coalesce(max(pl.display_name), max(s.player_name)) AS player_name,
    max(pl.position) AS position,
    count(DISTINCT s.manager_id)::integer AS managers
FROM player_week_scores s
LEFT JOIN players pl ON pl.id = s.player_id
WHERE s.rostered
    AND s.manager_id IS NOT NULL
GROUP BY s.player_id;

COMMENT ON VIEW v_player_managers IS
    'Career distinct managers on rostered player_week_scores rows.';

CREATE VIEW v_player_managers_season AS
SELECT
    s.year,
    s.player_id,
    coalesce(max(pl.display_name), max(s.player_name)) AS player_name,
    max(pl.position) AS position,
    count(DISTINCT s.manager_id)::integer AS managers
FROM player_week_scores s
LEFT JOIN players pl ON pl.id = s.player_id
WHERE s.rostered
    AND s.manager_id IS NOT NULL
GROUP BY s.year, s.player_id;

COMMENT ON VIEW v_player_managers_season IS
    'Distinct managers on rostered weeks inside one season.';

CREATE VIEW v_player_rings AS
WITH lineup AS (
    SELECT
        mu.year,
        mu.week,
        mu.kind,
        ls.player_id,
        ls.started,
        ls.points,
        CASE
            WHEN ls.side = 'home' THEN mu.home_manager_id
            ELSE mu.away_manager_id
        END AS manager_id
    FROM lineup_slots ls
    JOIN matchups mu ON mu.id = ls.matchup_id
    WHERE CASE
        WHEN ls.side = 'home' THEN mu.home_manager_id
        ELSE mu.away_manager_id
    END IS NOT NULL
),
champ AS (
    SELECT
        s.player_id,
        count(*)::integer AS champ_roster_weeks
    FROM player_week_scores s
    JOIN season_outcomes o ON o.year = s.year AND o.champion = s.manager_id
    WHERE s.rostered
        AND s.manager_id IS NOT NULL
    GROUP BY s.player_id
),
started AS (
    SELECT
        pw.player_id,
        count(DISTINCT pw.year)::integer AS rings
    FROM lineup pw
    JOIN season_outcomes o ON o.year = pw.year AND o.champion = pw.manager_id
    WHERE pw.started
    GROUP BY pw.player_id
),
titles AS (
    SELECT
        pw.player_id,
        count(*)::integer AS title_starts,
        coalesce(sum(pw.points), 0)::double precision AS title_points
    FROM lineup pw
    JOIN season_outcomes o ON o.year = pw.year AND o.champion = pw.manager_id
    WHERE pw.started
        AND pw.kind = 'playoff'
        AND (o.playoff_start_week IS NULL OR pw.week >= o.playoff_start_week)
    GROUP BY pw.player_id
)
SELECT
    ids.player_id,
    coalesce(pl.display_name, ids.player_id) AS player_name,
    pl.position,
    coalesce(st.rings, 0) AS rings,
    coalesce(c.champ_roster_weeks, 0) AS champ_roster_weeks,
    coalesce(t.title_starts, 0) AS title_starts,
    coalesce(t.title_points, 0) AS title_points
FROM (
    SELECT player_id FROM champ
    UNION
    SELECT player_id FROM started
    UNION
    SELECT player_id FROM titles
) ids
LEFT JOIN players pl ON pl.id = ids.player_id
LEFT JOIN champ c ON c.player_id = ids.player_id
LEFT JOIN started st ON st.player_id = ids.player_id
LEFT JOIN titles t ON t.player_id = ids.player_id;

COMMENT ON VIEW v_player_rings IS
    'Championship-roster weeks, championship seasons with a start, and title-week starts with their points. Title week matches the player page: playoff kind, on or after playoff_start_week, started for the champion. Lineup rows stand in for v_player_weeks.';
