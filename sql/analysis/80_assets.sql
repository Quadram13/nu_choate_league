-- Asset value: draft/trade/waiver acquisitions graded by rest-of-season VORP.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_add_season,
    v_add_value,
    v_draft_manager,
    v_draft_grades,
    v_draft_round_avg,
    v_trade_grades,
    v_trade_sides,
    v_trade_assets
CASCADE;

DROP MATERIALIZED VIEW IF EXISTS v_asset_value CASCADE;
DROP VIEW IF EXISTS v_asset_value CASCADE;

DROP VIEW IF EXISTS
    v_asset_windows,
    v_acquisitions
CASCADE;

-- Draft / trade / waiver value: starter PF and VORP after the acquisition, on that manager's roster.
-- ROS = rest of that season, stopping at the next acquisition of the same player.
-- Tenure = any later week on that manager, including if they rostered him again next year.
-- Draft is week 0 so the whole drafted season counts until the player is added by someone else.
-- VORP is points minus the Nth starter at the position in the full (rostered + FA) pool.
CREATE VIEW v_acquisitions AS
SELECT
    'draft:' || d.year::text || ':' || d.overall::text AS acquisition_id,
    NULL::text AS transaction_id,
    d.year,
    0 AS week,
    'draft'::text AS type,
    d.manager_id,
    d.manager_name,
    d.player_id,
    d.player_name,
    d.position,
    NULL::bigint AS at,
    d.overall,
    d.round,
    d.keeper
FROM v_draft d
UNION ALL
SELECT
    mv.transaction_id || ':' || mv.player_id || ':' || mv.manager_id,
    mv.transaction_id,
    mv.year,
    mv.week,
    mv.type,
    mv.manager_id,
    mv.manager_name,
    mv.player_id,
    mv.player_name,
    mv.position,
    mv.at,
    NULL,
    NULL,
    NULL
FROM v_moves mv
WHERE mv.direction = 'add'
    AND mv.status = 'complete'
    AND mv.type IN ('trade', 'waiver', 'free_agent');

CREATE VIEW v_asset_windows AS
SELECT
    a.*,
    lead(a.year) OVER (
        PARTITION BY a.player_id
        ORDER BY a.year, a.week, coalesce(a.at, 0), a.acquisition_id
    ) AS next_year,
    lead(a.week) OVER (
        PARTITION BY a.player_id
        ORDER BY a.year, a.week, coalesce(a.at, 0), a.acquisition_id
    ) AS next_week
FROM v_acquisitions a;

-- Snapshot: page loads filter this by year. Computing it live is ~11s per season.
CREATE MATERIALIZED VIEW v_asset_value AS
SELECT
    w.acquisition_id,
    w.transaction_id,
    w.year,
    w.week,
    w.type,
    w.manager_id,
    w.manager_name,
    w.player_id,
    w.player_name,
    w.position,
    w.at,
    w.overall,
    w.round,
    w.keeper,
    w.next_year,
    w.next_week,
    coalesce(sum(pw.points) FILTER (
        WHERE pw.started
            AND pw.year = w.year
            AND (
                w.next_year IS NULL
                OR w.next_year > w.year
                OR (w.next_year = w.year AND pw.week < w.next_week)
            )
    ), 0) AS ros_starter,
    coalesce(sum(pw.points) FILTER (
        WHERE pw.year = w.year
            AND (
                w.next_year IS NULL
                OR w.next_year > w.year
                OR (w.next_year = w.year AND pw.week < w.next_week)
            )
    ), 0) AS ros_roster,
    count(*) FILTER (
        WHERE pw.started
            AND pw.year = w.year
            AND (
                w.next_year IS NULL
                OR w.next_year > w.year
                OR (w.next_year = w.year AND pw.week < w.next_week)
            )
    ) AS ros_starts,
    coalesce(sum(pw.points) FILTER (WHERE pw.started), 0) AS tenure_starter,
    coalesce(sum(pw.points - r.replacement) FILTER (
        WHERE pw.started
            AND r.replacement IS NOT NULL
            AND pw.year = w.year
            AND (
                w.next_year IS NULL
                OR w.next_year > w.year
                OR (w.next_year = w.year AND pw.week < w.next_week)
            )
    ), 0) AS ros_vorp,
    coalesce(sum(pw.points - r.replacement) FILTER (
        WHERE pw.started
            AND r.replacement IS NOT NULL
    ), 0) AS tenure_vorp
FROM v_asset_windows w
LEFT JOIN v_pool_weeks pw
    ON pw.player_id = w.player_id
    AND pw.manager_id = w.manager_id
    AND (
        w.week = 0
        OR pw.year > w.year
        OR (pw.year = w.year AND pw.week >= w.week)
    )
LEFT JOIN v_replacement_weeks r
    ON r.year = pw.year
    AND r.week = pw.week
    AND r.position = pw.position
GROUP BY
    w.acquisition_id,
    w.transaction_id,
    w.year,
    w.week,
    w.type,
    w.manager_id,
    w.manager_name,
    w.player_id,
    w.player_name,
    w.position,
    w.at,
    w.overall,
    w.round,
    w.keeper,
    w.next_year,
    w.next_week
WITH NO DATA;

CREATE INDEX v_asset_value_year ON v_asset_value (year);
CREATE INDEX v_asset_value_year_type ON v_asset_value (year, type);

CREATE VIEW v_trade_assets AS
SELECT
    v.acquisition_id,
    v.transaction_id,
    v.year,
    v.week,
    v.player_id,
    v.player_name,
    v.position,
    tr.from_manager_id,
    tr.from_manager_name,
    v.manager_id AS to_manager_id,
    v.manager_name AS to_manager_name,
    v.ros_starter,
    v.ros_roster,
    v.ros_starts,
    v.tenure_starter,
    v.ros_vorp,
    v.tenure_vorp
FROM v_asset_value v
LEFT JOIN v_trades tr
    ON tr.transaction_id = v.transaction_id
    AND tr.player_id = v.player_id
    AND tr.to_manager_id = v.manager_id
WHERE v.type = 'trade';

CREATE VIEW v_trade_sides AS
SELECT
    transaction_id,
    year,
    week,
    to_manager_id AS manager_id,
    to_manager_name AS display_name,
    count(*) AS players,
    sum(ros_starter) AS ros_starter,
    sum(ros_roster) AS ros_roster,
    sum(tenure_starter) AS tenure_starter,
    sum(ros_vorp) AS ros_vorp,
    sum(tenure_vorp) AS tenure_vorp,
    string_agg(
        player_name || ' ' || round(ros_vorp::numeric, 1)::text,
        ', ' ORDER BY ros_vorp DESC, player_name
    ) AS received
FROM v_trade_assets
GROUP BY transaction_id, year, week, to_manager_id, to_manager_name;

-- Two-sided trades only. side_count via window so v_trade_sides is computed once;
-- a correlated COUNT subquery would re-evaluate the whole asset-value chain per row.
CREATE VIEW v_trade_grades AS
WITH sides AS (
    SELECT
        *,
        count(*) OVER (PARTITION BY transaction_id) AS side_count
    FROM v_trade_sides
)
SELECT
    a.transaction_id,
    a.year,
    a.week,
    a.manager_id AS left_id,
    a.display_name AS left_name,
    a.players AS left_players,
    a.ros_starter AS left_ros,
    a.ros_vorp AS left_vorp,
    a.tenure_starter AS left_tenure,
    a.received AS left_received,
    b.manager_id AS right_id,
    b.display_name AS right_name,
    b.players AS right_players,
    b.ros_starter AS right_ros,
    b.ros_vorp AS right_vorp,
    b.tenure_starter AS right_tenure,
    b.received AS right_received,
    a.ros_starter - b.ros_starter AS left_ros_edge,
    abs(a.ros_starter - b.ros_starter) AS ros_gap,
    a.ros_vorp - b.ros_vorp AS left_vorp_edge,
    abs(a.ros_vorp - b.ros_vorp) AS vorp_gap,
    a.tenure_starter - b.tenure_starter AS left_tenure_edge,
    CASE
        WHEN a.ros_vorp > b.ros_vorp THEN a.manager_id
        WHEN b.ros_vorp > a.ros_vorp THEN b.manager_id
    END AS winner_id,
    CASE
        WHEN a.ros_vorp > b.ros_vorp THEN a.display_name
        WHEN b.ros_vorp > a.ros_vorp THEN b.display_name
    END AS winner_name
FROM sides a
JOIN sides b
    ON b.transaction_id = a.transaction_id
    AND b.manager_id > a.manager_id
WHERE a.side_count = 2;

CREATE VIEW v_draft_round_avg AS
SELECT
    year,
    round,
    avg(ros_starter) AS round_avg,
    avg(ros_vorp) AS round_vorp,
    count(*) AS picks
FROM v_asset_value
WHERE type = 'draft'
GROUP BY year, round;

CREATE VIEW v_draft_grades AS
SELECT
    v.year,
    v.round,
    v.overall,
    v.manager_id,
    v.manager_name,
    v.player_id,
    v.player_name,
    v.position,
    v.keeper,
    v.ros_starter,
    v.ros_roster,
    v.ros_starts,
    v.tenure_starter,
    v.ros_vorp,
    v.tenure_vorp,
    r.round_avg,
    r.round_vorp,
    v.ros_starter - r.round_avg AS vs_round,
    v.ros_vorp - r.round_vorp AS vs_vorp,
    a.adp,
    a.times_drafted,
    v.overall - a.adp AS pick_vs_adp,
    (v.ros_starts >= 8) AS hit
FROM v_asset_value v
JOIN v_draft_round_avg r ON r.year = v.year AND r.round = v.round
LEFT JOIN (
    SELECT
        player_id,
        avg(overall::numeric) AS adp,
        count(*) AS times_drafted
    FROM v_draft
    GROUP BY player_id
) a ON a.player_id = v.player_id
WHERE v.type = 'draft';

CREATE VIEW v_draft_manager AS
SELECT
    year,
    manager_id,
    manager_name,
    count(*) AS picks,
    count(*) FILTER (WHERE keeper) AS keepers,
    sum(ros_starter) AS ros_starter,
    sum(ros_vorp) AS ros_vorp,
    sum(vs_round) AS vs_round,
    sum(vs_vorp) AS vs_vorp,
    count(*) FILTER (WHERE hit) AS hits,
    max(ros_vorp) AS best_vorp
FROM v_draft_grades
GROUP BY year, manager_id, manager_name;

CREATE VIEW v_add_value AS
SELECT
    acquisition_id,
    transaction_id,
    year,
    week,
    type,
    manager_id,
    manager_name,
    player_id,
    player_name,
    position,
    ros_starter,
    ros_roster,
    ros_starts,
    tenure_starter,
    ros_vorp,
    tenure_vorp
FROM v_asset_value
WHERE type IN ('waiver', 'free_agent');

CREATE VIEW v_add_season AS
SELECT
    year,
    manager_id,
    manager_name,
    count(*) AS adds,
    count(*) FILTER (WHERE type = 'waiver') AS waivers,
    count(*) FILTER (WHERE type = 'free_agent') AS free_agents,
    sum(ros_starter) AS ros_starter,
    sum(ros_vorp) AS ros_vorp,
    sum(ros_starter) FILTER (WHERE type = 'waiver') AS waiver_starter,
    sum(ros_vorp) FILTER (WHERE type = 'waiver') AS waiver_vorp,
    sum(ros_starter) FILTER (WHERE type = 'free_agent') AS fa_starter,
    sum(ros_vorp) FILTER (WHERE type = 'free_agent') AS fa_vorp,
    max(ros_vorp) AS best_vorp
FROM v_add_value
GROUP BY year, manager_id, manager_name;
