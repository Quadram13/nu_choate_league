-- Waiver claims: scored bids, missed claims, lucky dodges.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_waiver_dodges,
    v_waiver_misses
CASCADE;

DROP MATERIALIZED VIEW IF EXISTS v_waiver_claims CASCADE;
DROP VIEW IF EXISTS v_waiver_claims CASCADE;

-- Waiver claims include failed bids. league_ros is that player's starter PF in the league
-- from the claim week on (whoever rostered him). claim_seq is Sleeper settings.seq
-- (0 = that team's first claim that period) or ESPN process order when seq is missing.
-- Snapshot: misses, dodges, and week-wire read this. Computing it live is ~0.6s per season.
CREATE MATERIALIZED VIEW v_waiver_claims AS
WITH claims AS (
    SELECT
        mv.transaction_id,
        mv.year,
        mv.week,
        mv.status,
        mv.manager_id,
        mv.manager_name,
        mv.player_id,
        mv.player_name,
        mv.position,
        mv.seq,
        mv.priority,
        mv.bid,
        mv.note,
        mv.at,
        coalesce(
            mv.seq,
            row_number() OVER (
                PARTITION BY mv.year, mv.week, mv.manager_id
                ORDER BY mv.at NULLS LAST, mv.transaction_id
            ) - 1
        ) AS claim_seq
    FROM v_moves mv
    WHERE mv.type = 'waiver'
        AND mv.direction = 'add'
),
scored AS (
    SELECT
        c.transaction_id,
        c.year,
        c.week,
        c.status,
        c.manager_id,
        c.manager_name,
        c.player_id,
        c.player_name,
        c.position,
        c.seq,
        c.priority,
        c.bid,
        c.note,
        c.at,
        c.claim_seq,
        coalesce(sum(pw.points) FILTER (
            WHERE pw.started
                AND pw.year = c.year
                AND pw.week >= c.week
        ), 0) AS league_ros,
        count(*) FILTER (
            WHERE pw.started
                AND pw.year = c.year
                AND pw.week >= c.week
        ) AS league_starts,
        coalesce(sum(pw.points - r.replacement) FILTER (
            WHERE r.replacement IS NOT NULL
                AND pw.year = c.year
                AND pw.week >= c.week
        ), 0) AS league_vorp
    FROM claims c
    LEFT JOIN v_pool_weeks pw
        ON pw.player_id = c.player_id
    LEFT JOIN v_replacement_weeks r
        ON r.year = pw.year
        AND r.week = pw.week
        AND r.position = pw.position
    GROUP BY
        c.transaction_id,
        c.year,
        c.week,
        c.status,
        c.manager_id,
        c.manager_name,
        c.player_id,
        c.player_name,
        c.position,
        c.seq,
        c.priority,
        c.bid,
        c.note,
        c.at,
        c.claim_seq
)
SELECT
    scored.*,
    dense_rank() OVER (
        PARTITION BY year, week, manager_id
        ORDER BY claim_seq, transaction_id
    ) AS local_seq
FROM scored
WITH NO DATA;

CREATE INDEX v_waiver_claims_year_week ON v_waiver_claims (year, week);
CREATE INDEX v_waiver_claims_year_manager ON v_waiver_claims (year, manager_id, status);

-- Self-join + row_number instead of a correlated LATERAL: v_waiver_claims is
-- evaluated once, not re-scanned per failed claim.
CREATE VIEW v_waiver_misses AS
WITH pairs AS (
    SELECT
        f.year,
        f.week,
        f.manager_id,
        f.manager_name,
        f.transaction_id AS missed_transaction_id,
        f.local_seq AS missed_seq,
        f.player_id AS missed_player_id,
        f.player_name AS missed_player,
        f.position AS missed_position,
        f.league_ros AS missed_ros,
        f.league_starts AS missed_starts,
        f.league_vorp AS missed_vorp,
        f.note,
        CASE
            WHEN f.note ILIKE '%too many players%'
                OR f.note = 'FAILED_ROSTERLIMIT'
                THEN 'own_claim_order'
            WHEN f.note ILIKE '%claimed by another%'
                OR f.note = 'FAILED_INVALIDPLAYERSOURCE'
                THEN 'lost_on_wire'
            ELSE 'other'
        END AS reason,
        w.local_seq AS won_seq,
        w.transaction_id AS won_transaction_id,
        w.player_id AS won_player_id,
        w.player_name AS won_player,
        w.league_ros AS won_ros,
        w.league_vorp AS won_vorp,
        f.league_ros - coalesce(w.league_ros, 0) AS ros_gap,
        f.league_vorp - coalesce(w.league_vorp, 0) AS vorp_gap,
        row_number() OVER (
            PARTITION BY f.transaction_id
            ORDER BY abs(w.claim_seq - f.claim_seq), w.claim_seq
        ) AS pick
    FROM v_waiver_claims f
    LEFT JOIN v_waiver_claims w
        ON w.year = f.year
        AND w.week = f.week
        AND w.manager_id = f.manager_id
        AND w.status = 'complete'
        AND w.transaction_id <> f.transaction_id
    WHERE f.status = 'failed'
)
SELECT
    year,
    week,
    manager_id,
    manager_name,
    missed_transaction_id,
    missed_seq,
    missed_player_id,
    missed_player,
    missed_position,
    missed_ros,
    missed_starts,
    missed_vorp,
    note,
    reason,
    won_seq,
    won_transaction_id,
    won_player_id,
    won_player,
    won_ros,
    won_vorp,
    ros_gap,
    vorp_gap
FROM pairs
WHERE pick = 1
    AND missed_vorp > coalesce(won_vorp, 0);

-- Inverse of a wire miss: a higher-priority claim was taken by someone else, and the
-- later claim this team actually processed scored more VORP than the one they lost.
CREATE VIEW v_waiver_dodges AS
WITH pairs AS (
    SELECT
        f.year,
        f.week,
        f.manager_id,
        f.manager_name,
        f.transaction_id AS lost_transaction_id,
        f.local_seq AS lost_seq,
        f.player_id AS lost_player_id,
        f.player_name AS lost_player,
        f.position AS lost_position,
        f.league_ros AS lost_ros,
        f.league_starts AS lost_starts,
        f.league_vorp AS lost_vorp,
        f.note,
        w.local_seq AS won_seq,
        w.transaction_id AS won_transaction_id,
        w.player_id AS won_player_id,
        w.player_name AS won_player,
        w.league_ros AS won_ros,
        w.league_vorp AS won_vorp,
        w.league_vorp - f.league_vorp AS vorp_gap,
        w.league_ros - f.league_ros AS ros_gap,
        row_number() OVER (
            PARTITION BY f.transaction_id
            ORDER BY w.claim_seq, w.transaction_id
        ) AS pick
    FROM v_waiver_claims f
    JOIN v_waiver_claims w
        ON w.year = f.year
        AND w.week = f.week
        AND w.manager_id = f.manager_id
        AND w.status = 'complete'
        AND w.claim_seq > f.claim_seq
    WHERE f.status = 'failed'
        AND (
            f.note ILIKE '%claimed by another%'
            OR f.note = 'FAILED_INVALIDPLAYERSOURCE'
        )
)
SELECT
    year,
    week,
    manager_id,
    manager_name,
    lost_transaction_id,
    lost_seq,
    lost_player_id,
    lost_player,
    lost_position,
    lost_ros,
    lost_starts,
    lost_vorp,
    note,
    won_seq,
    won_transaction_id,
    won_player_id,
    won_player,
    won_ros,
    won_vorp,
    vorp_gap,
    ros_gap
FROM pairs
WHERE pick = 1
    AND won_vorp > lost_vorp;
