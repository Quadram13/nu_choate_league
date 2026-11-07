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

ALTER TABLE seasons ADD COLUMN IF NOT EXISTS scoring_settings JSONB;
ALTER TABLE seasons ADD COLUMN IF NOT EXISTS faab_budget INTEGER;

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

ALTER TABLE players ADD COLUMN IF NOT EXISTS nfl_team TEXT;
ALTER TABLE players ADD COLUMN IF NOT EXISTS college TEXT;
ALTER TABLE players ADD COLUMN IF NOT EXISTS years_exp INTEGER;
ALTER TABLE players ADD COLUMN IF NOT EXISTS jersey_number TEXT;

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

CREATE TABLE IF NOT EXISTS player_week_stat_lines (
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    week INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    pass_points DOUBLE PRECISION NOT NULL DEFAULT 0,
    rush_points DOUBLE PRECISION NOT NULL DEFAULT 0,
    rec_points DOUBLE PRECISION NOT NULL DEFAULT 0,
    misc_points DOUBLE PRECISION NOT NULL DEFAULT 0,
    PRIMARY KEY (year, week, player_id)
);

-- Counting box score beside player_week_stat_lines. Same player-weeks: a row
-- exists only when fantasy point buckets are not all zero (byes and other
-- all-zero stat objects are omitted). Columns are the fan box score, not
-- every source key. Sleeper reads stats.json. ESPN reads boxscore `stats`
-- (counts); `appliedStats` is fantasy points and only feeds the bucket gate.
-- ESPN has no red-zone stat id, so those three columns stay 0. def_int stores
-- Sleeper's `int` and ESPN stat 95.
CREATE TABLE IF NOT EXISTS player_week_counting_stats (
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    week INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    pass_cmp INTEGER NOT NULL DEFAULT 0,
    pass_att INTEGER NOT NULL DEFAULT 0,
    pass_yd INTEGER NOT NULL DEFAULT 0,
    pass_td INTEGER NOT NULL DEFAULT 0,
    pass_int INTEGER NOT NULL DEFAULT 0,
    rush_att INTEGER NOT NULL DEFAULT 0,
    rush_yd INTEGER NOT NULL DEFAULT 0,
    rush_td INTEGER NOT NULL DEFAULT 0,
    rec INTEGER NOT NULL DEFAULT 0,
    rec_yd INTEGER NOT NULL DEFAULT 0,
    rec_td INTEGER NOT NULL DEFAULT 0,
    rec_tgt INTEGER NOT NULL DEFAULT 0,
    fum_lost INTEGER NOT NULL DEFAULT 0,
    pass_2pt INTEGER NOT NULL DEFAULT 0,
    rush_2pt INTEGER NOT NULL DEFAULT 0,
    rec_2pt INTEGER NOT NULL DEFAULT 0,
    pass_fd INTEGER NOT NULL DEFAULT 0,
    rush_fd INTEGER NOT NULL DEFAULT 0,
    rec_fd INTEGER NOT NULL DEFAULT 0,
    pass_rz_att INTEGER NOT NULL DEFAULT 0,
    rush_rz_att INTEGER NOT NULL DEFAULT 0,
    rec_rz_tgt INTEGER NOT NULL DEFAULT 0,
    fgm INTEGER NOT NULL DEFAULT 0,
    fga INTEGER NOT NULL DEFAULT 0,
    xpm INTEGER NOT NULL DEFAULT 0,
    xpa INTEGER NOT NULL DEFAULT 0,
    fgm_50p INTEGER NOT NULL DEFAULT 0,
    sack INTEGER NOT NULL DEFAULT 0,
    def_int INTEGER NOT NULL DEFAULT 0,
    fum_rec INTEGER NOT NULL DEFAULT 0,
    def_td INTEGER NOT NULL DEFAULT 0,
    st_td INTEGER NOT NULL DEFAULT 0,
    blk_kick INTEGER NOT NULL DEFAULT 0,
    safe INTEGER NOT NULL DEFAULT 0,
    pts_allow INTEGER NOT NULL DEFAULT 0,
    yds_allow INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (year, week, player_id)
);
-- v_moves / v_trades join transaction_moves back to transactions.
CREATE INDEX IF NOT EXISTS transaction_moves_transaction_idx
    ON transaction_moves (transaction_id);

-- ---------------------------------------------------------------------------
-- ESPN market (issue #25). Own section so it stays clear of other fact DDL.
-- Side table of player-card ownership fields, joined through players.espn_id.
-- Carded players who never appear in this league are not in `players`, so
-- there is no foreign key to that table.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS espn_market (
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    espn_id INTEGER NOT NULL,
    average_draft_position DOUBLE PRECISION,
    percent_owned DOUBLE PRECISION,
    percent_started DOUBLE PRECISION,
    auction_value_average DOUBLE PRECISION,
    PRIMARY KEY (year, espn_id)
);

CREATE INDEX IF NOT EXISTS espn_market_espn_id_idx ON espn_market (espn_id);
