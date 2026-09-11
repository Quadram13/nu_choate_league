-- Draft picks and transactions with resolved player/manager names.
-- Facts/tables live in sql/facts.sql.

DROP VIEW IF EXISTS
    v_trades,
    v_moves,
    v_draft
CASCADE;

CREATE VIEW v_draft AS
SELECT
    d.year,
    d.overall,
    d.round,
    d.manager_id,
    m.display_name AS manager_name,
    d.player_id,
    coalesce(p.display_name, d.player_name) AS player_name,
    p.position,
    d.keeper
FROM draft_picks d
JOIN managers m ON m.id = d.manager_id
LEFT JOIN players p ON p.id = d.player_id;

CREATE VIEW v_moves AS
SELECT
    t.id AS transaction_id,
    t.year,
    t.week,
    t.type,
    t.status,
    t.at,
    mv.direction,
    mv.manager_id,
    m.display_name AS manager_name,
    mv.player_id,
    coalesce(p.display_name, mv.player_name) AS player_name,
    p.position,
    t.seq,
    t.priority,
    t.bid,
    t.note
FROM transactions t
JOIN transaction_moves mv ON mv.transaction_id = t.id
JOIN managers m ON m.id = mv.manager_id
LEFT JOIN players p ON p.id = mv.player_id;

CREATE VIEW v_trades AS
SELECT
    t.id AS transaction_id,
    t.year,
    t.week,
    t.status,
    t.at,
    a.player_id,
    coalesce(p.display_name, a.player_name) AS player_name,
    p.position,
    d.manager_id AS from_manager_id,
    fm.display_name AS from_manager_name,
    a.manager_id AS to_manager_id,
    tm.display_name AS to_manager_name
FROM transactions t
JOIN transaction_moves a ON a.transaction_id = t.id AND a.direction = 'add'
LEFT JOIN transaction_moves d
    ON d.transaction_id = t.id
    AND d.direction = 'drop'
    AND d.player_id = a.player_id
LEFT JOIN managers fm ON fm.id = d.manager_id
JOIN managers tm ON tm.id = a.manager_id
LEFT JOIN players p ON p.id = a.player_id
WHERE t.type = 'trade';
