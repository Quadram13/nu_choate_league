-- Canonical facts. Derived stats (standings, career, VORP) come later.

CREATE TABLE IF NOT EXISTS managers (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manager_platform_ids (
    manager_id TEXT NOT NULL REFERENCES managers (id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    platform_id TEXT NOT NULL,
    PRIMARY KEY (platform, platform_id)
);

CREATE TABLE IF NOT EXISTS seasons (
    year INTEGER PRIMARY KEY,
    platform TEXT NOT NULL,
    league_id TEXT NOT NULL,
    name TEXT NOT NULL,
    vs_median BOOLEAN NOT NULL,
    through_week INTEGER
);

CREATE TABLE IF NOT EXISTS team_seasons (
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    manager_id TEXT NOT NULL REFERENCES managers (id),
    team_name TEXT NOT NULL,
    platform_team_id TEXT NOT NULL,
    PRIMARY KEY (year, manager_id)
);

CREATE TABLE IF NOT EXISTS official_records (
    year INTEGER NOT NULL,
    manager_id TEXT NOT NULL,
    wins INTEGER NOT NULL,
    losses INTEGER NOT NULL,
    ties INTEGER NOT NULL,
    points_for DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (year, manager_id),
    FOREIGN KEY (year, manager_id) REFERENCES team_seasons (year, manager_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS matchups (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    week INTEGER NOT NULL,
    kind TEXT NOT NULL,
    home_manager_id TEXT REFERENCES managers (id),
    away_manager_id TEXT REFERENCES managers (id),
    home_team_name TEXT NOT NULL,
    away_team_name TEXT NOT NULL,
    home_platform_team_id TEXT,
    away_platform_team_id TEXT,
    home_points DOUBLE PRECISION NOT NULL,
    away_points DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS lineup_slots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    matchup_id TEXT NOT NULL REFERENCES matchups (id) ON DELETE CASCADE,
    side TEXT NOT NULL CHECK (side IN ('home', 'away')),
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    slot TEXT NOT NULL,
    points DOUBLE PRECISION NOT NULL,
    started BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS draft_picks (
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    overall INTEGER NOT NULL,
    round INTEGER NOT NULL,
    manager_id TEXT NOT NULL REFERENCES managers (id),
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    keeper BOOLEAN NOT NULL,
    PRIMARY KEY (year, overall)
);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    week INTEGER NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    at BIGINT,
    seq INTEGER,
    priority INTEGER,
    bid INTEGER,
    note TEXT
);

ALTER TABLE transactions ADD COLUMN IF NOT EXISTS seq INTEGER;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS priority INTEGER;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS bid INTEGER;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS note TEXT;

CREATE TABLE IF NOT EXISTS transaction_moves (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id TEXT NOT NULL REFERENCES transactions (id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('add', 'drop')),
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    manager_id TEXT NOT NULL REFERENCES managers (id)
);

CREATE TABLE IF NOT EXISTS week_scores (
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    week INTEGER NOT NULL,
    manager_id TEXT NOT NULL REFERENCES managers (id),
    points DOUBLE PRECISION NOT NULL,
    paired BOOLEAN NOT NULL,
    PRIMARY KEY (year, week, manager_id)
);

CREATE TABLE IF NOT EXISTS season_outcomes (
    year INTEGER PRIMARY KEY REFERENCES seasons (year) ON DELETE CASCADE,
    champion TEXT REFERENCES managers (id),
    runner_up TEXT REFERENCES managers (id),
    regular_season_champion TEXT REFERENCES managers (id),
    most_points TEXT REFERENCES managers (id),
    playoff_teams INTEGER,
    playoff_start_week INTEGER
);

CREATE TABLE IF NOT EXISTS season_playoff_managers (
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    manager_id TEXT NOT NULL REFERENCES managers (id),
    PRIMARY KEY (year, manager_id)
);

CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    position TEXT,
    espn_id INTEGER
);

CREATE INDEX IF NOT EXISTS matchups_year_week_idx ON matchups (year, week);
CREATE INDEX IF NOT EXISTS lineup_slots_matchup_idx ON lineup_slots (matchup_id);
CREATE INDEX IF NOT EXISTS lineup_slots_player_idx ON lineup_slots (player_id);
CREATE INDEX IF NOT EXISTS transactions_year_week_idx ON transactions (year, week);
CREATE INDEX IF NOT EXISTS week_scores_year_week_idx ON week_scores (year, week);

CREATE TABLE IF NOT EXISTS player_week_scores (
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    week INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    position TEXT,
    points DOUBLE PRECISION NOT NULL,
    rostered BOOLEAN NOT NULL,
    started BOOLEAN NOT NULL,
    manager_id TEXT REFERENCES managers (id),
    PRIMARY KEY (year, week, player_id)
);

CREATE INDEX IF NOT EXISTS player_week_scores_pos_idx
    ON player_week_scores (year, week, position);
CREATE INDEX IF NOT EXISTS player_week_scores_player_idx
    ON player_week_scores (player_id, year, week);
-- v_asset_value joins pool weeks by player + manager + week range (ROS windows).
CREATE INDEX IF NOT EXISTS player_week_scores_roster_idx
    ON player_week_scores (player_id, manager_id, year, week);
-- v_moves / v_trades join transaction_moves back to transactions.
CREATE INDEX IF NOT EXISTS transaction_moves_transaction_idx
    ON transaction_moves (transaction_id);
