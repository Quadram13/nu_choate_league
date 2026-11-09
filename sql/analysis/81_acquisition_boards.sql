-- Acquisition career boards (issue #40).
--
-- Career draft sums, trade-partner series, waiver priority ROI, and
-- regular-season points by lineup slot.
--
-- Reads v_draft_manager, v_trade_grades, v_add_value, transactions,
-- seasons, and v_player_weeks. Applying 60_players.sql or 80_assets.sql
-- drops those with CASCADE and drops these views with them. This file
-- is reapplied by a full schema load because it sorts after both.

CREATE OR REPLACE VIEW v_draft_career AS
SELECT
    manager_id,
    max(manager_name) AS manager_name,
    count(*)::integer AS seasons,
    sum(picks)::integer AS picks,
    sum(hits)::integer AS hits,
    sum(hits)::double precision / nullif(sum(picks), 0)::double precision AS hit_rate,
    sum(ros_vorp) AS ros_vorp,
    sum(vs_round) AS vs_round,
    sum(vs_vorp) AS vs_vorp
FROM v_draft_manager
GROUP BY manager_id;

COMMENT ON VIEW v_draft_career IS
    'Career sums of v_draft_manager. Hit rate is career hits divided by career picks. Includes the in-progress season, whose rest-of-season numbers cover only the weeks played.';

-- One row per two-manager series. left_id is the lower manager id, the
-- same orientation as v_trade_grades. net_right_vorp is defined as the
-- negative of net_left_vorp, so gap_left + gap_right is 0.
-- The series winner is the positive sum of signed VORP edges
-- (left_vorp - right_vorp), which can disagree with the deal-win count.
-- A zero sum has no winner.
CREATE OR REPLACE VIEW v_trade_pairs AS
SELECT
    left_id,
    max(left_name) AS left_name,
    right_id,
    max(right_name) AS right_name,
    count(*)::integer AS deals,
    count(*) FILTER (WHERE winner_id = left_id)::integer AS left_wins,
    count(*) FILTER (WHERE winner_id = right_id)::integer AS right_wins,
    count(*) FILTER (WHERE winner_id IS NULL)::integer AS pushes,
    sum(left_vorp_edge) AS net_left_vorp,
    -sum(left_vorp_edge) AS net_right_vorp,
    CASE
        WHEN sum(left_vorp_edge) > 0 THEN left_id
        WHEN sum(left_vorp_edge) < 0 THEN right_id
    END AS series_winner_id,
    CASE
        WHEN sum(left_vorp_edge) > 0 THEN max(left_name)
        WHEN sum(left_vorp_edge) < 0 THEN max(right_name)
    END AS series_winner_name
FROM v_trade_grades
GROUP BY left_id, right_id;

COMMENT ON VIEW v_trade_pairs IS
    'Trade series between two managers. Net VORP on the right is the negative of net VORP on the left. Series winner is the positive signed edge, not the side with more deal wins.';

-- Completed waiver adds in the two seasons that stored a claim priority.
-- v_add_value is already status = complete. Priority 0 is the manager's
-- first claim in that waiver run. priority_units is priority + 1, the
-- same divisor the wire page uses for ROS VORP per priority.
-- Seq is the league processing order and is not the cost.
-- 2022-2023 have no priority. 2026 is FAAB and stays out of this view.
CREATE OR REPLACE VIEW v_waiver_priority_adds AS
SELECT
    v.acquisition_id,
    v.transaction_id,
    v.year,
    v.week,
    v.manager_id,
    v.manager_name,
    v.player_id,
    v.player_name,
    v.position,
    v.ros_starter,
    v.ros_vorp,
    t.priority,
    t.seq,
    (t.priority + 1)::integer AS priority_units,
    v.ros_vorp / (t.priority + 1) AS vorp_per_priority
FROM v_add_value v
JOIN transactions t ON t.id = v.transaction_id
WHERE v.type = 'waiver'
    AND v.year IN (2024, 2025)
    AND t.status = 'complete'
    AND t.priority IS NOT NULL;

COMMENT ON VIEW v_waiver_priority_adds IS
    'Completed 2024 and 2025 waiver adds that stored a claim priority. Cost unit is priority + 1. Seq is processing order, not the cost.';

CREATE OR REPLACE VIEW v_waiver_priority_season AS
SELECT
    year,
    manager_id,
    max(manager_name) AS manager_name,
    count(*)::integer AS claims,
    sum(priority_units)::integer AS priority_units,
    sum(ros_vorp) AS ros_vorp,
    sum(ros_starter) AS ros_starter,
    sum(ros_vorp) / nullif(sum(priority_units), 0) AS vorp_per_priority,
    avg(seq) AS avg_seq
FROM v_waiver_priority_adds
GROUP BY year, manager_id;

COMMENT ON VIEW v_waiver_priority_season IS
    'Manager-season waiver priority ROI. VORP per priority is the sum of rest-of-season VORP divided by the sum of priority units, not the average of the per-add ratios.';

CREATE OR REPLACE VIEW v_waiver_priority_career AS
SELECT
    manager_id,
    max(manager_name) AS manager_name,
    count(*)::integer AS claims,
    sum(priority_units)::integer AS priority_units,
    sum(ros_vorp) AS ros_vorp,
    sum(ros_starter) AS ros_starter,
    sum(ros_vorp) / nullif(sum(priority_units), 0) AS vorp_per_priority,
    count(DISTINCT year)::integer AS seasons
FROM v_waiver_priority_adds
GROUP BY manager_id;

COMMENT ON VIEW v_waiver_priority_career IS
    'Pooled 2024-2025 waiver priority ROI. The ratio is pooled VORP over pooled priority units.';

-- Coverage for the honest caveat. Counts are waiver transactions, including
-- failed claims, because that is the population priority was stored on.
CREATE OR REPLACE VIEW v_waiver_cost_coverage AS
SELECT
    s.year,
    s.platform,
    s.faab_budget,
    count(t.id) FILTER (WHERE t.type = 'waiver')::integer AS waiver_rows,
    count(t.id) FILTER (
        WHERE t.type = 'waiver' AND t.priority IS NOT NULL
    )::integer AS priority_rows,
    count(t.id) FILTER (
        WHERE t.type = 'waiver' AND t.status = 'complete' AND t.priority IS NOT NULL
    )::integer AS priority_complete,
    count(t.id) FILTER (
        WHERE t.type = 'waiver' AND t.status = 'failed' AND t.priority IS NOT NULL
    )::integer AS priority_failed,
    count(t.id) FILTER (
        WHERE t.type = 'waiver' AND t.status = 'complete' AND t.priority IS NULL
    )::integer AS complete_without_priority,
    count(t.id) FILTER (WHERE t.bid IS NOT NULL)::integer AS bid_rows,
    count(t.id) FILTER (WHERE t.bid = 0)::integer AS zero_bids,
    count(t.id) FILTER (
        WHERE t.type = 'waiver' AND t.bid IS NOT NULL AND t.bid <> 0
    )::integer AS nonzero_waiver_bids,
    count(t.id) FILTER (
        WHERE t.type = 'waiver' AND t.bid = 1
    )::integer AS waiver_bids_of_one,
    min(t.bid) FILTER (WHERE t.type = 'waiver') AS min_waiver_bid,
    max(t.bid) FILTER (WHERE t.type = 'waiver') AS max_waiver_bid
FROM seasons s
LEFT JOIN transactions t ON t.year = s.year
GROUP BY s.year, s.platform, s.faab_budget;

COMMENT ON VIEW v_waiver_cost_coverage IS
    'Per-season cost-signal coverage. ESPN seasons store bid 0 and no priority. 2024-2025 store priority on a subset of waiver rows. 2026 stores FAAB bids.';

-- shape_slot tags the rows that enter a roster profile.
-- IR is every IR slot, any week type.
-- The other tags are regular-season starts, which match official PF in a
-- finished season. FLEX is split by the catalog position on players.
-- FLEX_OTHER is a FLEX start catalogued outside RB, WR, and TE.
-- OTHER is any other regular-season start, so a new slot cannot vanish
-- from PF. Bench rows are untagged and stay out.
CREATE OR REPLACE VIEW v_roster_shape_rows AS
SELECT
    w.year,
    w.manager_id,
    w.manager_name,
    w.kind,
    w.slot,
    w.position,
    w.started,
    w.points,
    CASE
        WHEN w.slot = 'IR' THEN 'IR'
        WHEN w.started
            AND w.kind = 'regular'
            AND w.slot IN ('QB', 'RB', 'WR', 'TE', 'K', 'DEF') THEN w.slot
        WHEN w.started
            AND w.kind = 'regular'
            AND w.slot = 'FLEX'
            AND w.position = 'RB' THEN 'FLEX_RB'
        WHEN w.started
            AND w.kind = 'regular'
            AND w.slot = 'FLEX'
            AND w.position = 'WR' THEN 'FLEX_WR'
        WHEN w.started
            AND w.kind = 'regular'
            AND w.slot = 'FLEX'
            AND w.position = 'TE' THEN 'FLEX_TE'
        WHEN w.started
            AND w.kind = 'regular'
            AND w.slot = 'FLEX' THEN 'FLEX_OTHER'
        WHEN w.started AND w.kind = 'regular' THEN 'OTHER'
    END AS shape_slot
FROM v_player_weeks w;

COMMENT ON VIEW v_roster_shape_rows IS
    'Lineup rows tagged for roster shape. IR is every IR slot. Other tags are regular-season starts. FLEX is split by catalog position.';

CREATE OR REPLACE VIEW v_roster_shape_season AS
SELECT
    year,
    manager_id,
    manager_name,
    starter_points,
    qb_points,
    qb_points / nullif(starter_points, 0) AS qb_share,
    rb_points,
    rb_points / nullif(starter_points, 0) AS rb_share,
    wr_points,
    wr_points / nullif(starter_points, 0) AS wr_share,
    te_points,
    te_points / nullif(starter_points, 0) AS te_share,
    flex_points,
    flex_points / nullif(starter_points, 0) AS flex_share,
    flex_rb_points,
    flex_rb_points / nullif(starter_points, 0) AS flex_rb_share,
    flex_wr_points,
    flex_wr_points / nullif(starter_points, 0) AS flex_wr_share,
    flex_te_points,
    flex_te_points / nullif(starter_points, 0) AS flex_te_share,
    flex_other_points,
    flex_other_points / nullif(starter_points, 0) AS flex_other_share,
    k_points,
    k_points / nullif(starter_points, 0) AS k_share,
    def_points,
    def_points / nullif(starter_points, 0) AS def_share,
    other_points,
    other_points / nullif(starter_points, 0) AS other_share,
    ir_slots,
    ir_points
FROM (
    SELECT
        year,
        manager_id,
        max(manager_name) AS manager_name,
        coalesce(sum(points) FILTER (
            WHERE shape_slot IN (
                'QB', 'RB', 'WR', 'TE', 'K', 'DEF',
                'FLEX_RB', 'FLEX_WR', 'FLEX_TE', 'FLEX_OTHER', 'OTHER'
            )
        ), 0) AS starter_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'QB'), 0) AS qb_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'RB'), 0) AS rb_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'WR'), 0) AS wr_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'TE'), 0) AS te_points,
        coalesce(sum(points) FILTER (
            WHERE shape_slot IN ('FLEX_RB', 'FLEX_WR', 'FLEX_TE', 'FLEX_OTHER')
        ), 0) AS flex_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'FLEX_RB'), 0) AS flex_rb_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'FLEX_WR'), 0) AS flex_wr_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'FLEX_TE'), 0) AS flex_te_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'FLEX_OTHER'), 0) AS flex_other_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'K'), 0) AS k_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'DEF'), 0) AS def_points,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'OTHER'), 0) AS other_points,
        coalesce(count(*) FILTER (WHERE shape_slot = 'IR'), 0)::integer AS ir_slots,
        coalesce(sum(points) FILTER (WHERE shape_slot = 'IR'), 0) AS ir_points
    FROM v_roster_shape_rows
    WHERE shape_slot IS NOT NULL
    GROUP BY year, manager_id
) pts;

COMMENT ON VIEW v_roster_shape_season IS
    'Manager-season roster shape. Shares are regular-season starter points. FLEX RB/WR/TE/other are a split of flex_points. IR slots are counted and kept out of starter points.';

CREATE OR REPLACE VIEW v_roster_shape_career AS
SELECT
    manager_id,
    max(manager_name) AS manager_name,
    sum(starter_points) AS starter_points,
    sum(qb_points) AS qb_points,
    sum(qb_points) / nullif(sum(starter_points), 0) AS qb_share,
    sum(rb_points) AS rb_points,
    sum(rb_points) / nullif(sum(starter_points), 0) AS rb_share,
    sum(wr_points) AS wr_points,
    sum(wr_points) / nullif(sum(starter_points), 0) AS wr_share,
    sum(te_points) AS te_points,
    sum(te_points) / nullif(sum(starter_points), 0) AS te_share,
    sum(flex_points) AS flex_points,
    sum(flex_points) / nullif(sum(starter_points), 0) AS flex_share,
    sum(flex_rb_points) AS flex_rb_points,
    sum(flex_rb_points) / nullif(sum(starter_points), 0) AS flex_rb_share,
    sum(flex_wr_points) AS flex_wr_points,
    sum(flex_wr_points) / nullif(sum(starter_points), 0) AS flex_wr_share,
    sum(flex_te_points) AS flex_te_points,
    sum(flex_te_points) / nullif(sum(starter_points), 0) AS flex_te_share,
    sum(flex_other_points) AS flex_other_points,
    sum(flex_other_points) / nullif(sum(starter_points), 0) AS flex_other_share,
    sum(k_points) AS k_points,
    sum(k_points) / nullif(sum(starter_points), 0) AS k_share,
    sum(def_points) AS def_points,
    sum(def_points) / nullif(sum(starter_points), 0) AS def_share,
    sum(other_points) AS other_points,
    sum(other_points) / nullif(sum(starter_points), 0) AS other_share,
    sum(ir_slots)::integer AS ir_slots,
    sum(ir_points) AS ir_points
FROM v_roster_shape_season
GROUP BY manager_id;

COMMENT ON VIEW v_roster_shape_career IS
    'Career roster shape. Shares divide career starter points, not the average of seasonal shares. IR slots sum the seasonal counts.';
