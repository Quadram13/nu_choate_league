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

-- ---------------------------------------------------------------------------
-- NFL schedule + Sleeper roster extras (issue #26).
-- Schedule dumps are ESPN proTeamSchedules for 2022 and 2023 only.
-- The crosswalk is maps/dst.yaml: ESPN proTeamId -> Sleeper abbreviation,
-- the same codes stored on players.nfl_team (WAS, not ESPN's "Wsh").
-- Roster extras are season totals on official_records. ESPN years stay null.
-- points_against is Sleeper fpts_against + fpts_against_decimal/100.
-- ppts is Sleeper ppts + ppts_decimal/100.
-- ---------------------------------------------------------------------------

ALTER TABLE official_records ADD COLUMN IF NOT EXISTS points_against DOUBLE PRECISION;
ALTER TABLE official_records ADD COLUMN IF NOT EXISTS ppts DOUBLE PRECISION;
ALTER TABLE official_records ADD COLUMN IF NOT EXISTS waiver_position INTEGER;
ALTER TABLE official_records ADD COLUMN IF NOT EXISTS total_moves INTEGER;

CREATE TABLE IF NOT EXISTS nfl_team_crosswalk (
    espn_pro_team_id INTEGER PRIMARY KEY,
    abbr TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nfl_team_weeks (
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    week INTEGER NOT NULL,
    espn_pro_team_id INTEGER NOT NULL REFERENCES nfl_team_crosswalk (espn_pro_team_id),
    opponent_espn_pro_team_id INTEGER REFERENCES nfl_team_crosswalk (espn_pro_team_id),
    is_home BOOLEAN,
    is_bye BOOLEAN NOT NULL,
    PRIMARY KEY (year, week, espn_pro_team_id),
    CHECK (
        (is_bye AND opponent_espn_pro_team_id IS NULL AND is_home IS NULL)
        OR (NOT is_bye AND opponent_espn_pro_team_id IS NOT NULL AND is_home IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS nfl_team_weeks_opponent_idx
    ON nfl_team_weeks (year, week, opponent_espn_pro_team_id);

-- ---------------------------------------------------------------------------
-- Sleeper weekly context (issue #33). Own section so it stays clear of other
-- fact DDL. Source is data/sleeper/{year}/weeks/*/stats.json only.
--
-- ESPN 2022-2023 has no equivalent file. Those seasons get no rows. Ranks,
-- snaps, and gp/gs are not invented from boxscores.
--
-- Row rule: the player_week_counting_stats gate (a stat object whose fantasy
-- point buckets are not all zero) plus weeks where gp, gs, off_snp, def_snp,
-- or st_snp is greater than zero. Sleeper also stamps positional rank and
-- team snap totals on players who did not play; those objects are not rows.
-- The extra rows versus counting stats are played weeks that scored no
-- fantasy points. gp and gs are that week's flags, not season totals. The
-- dumps write each key only when the value is 1, so a null gp means the key
-- was absent and a null gs beside gp = 1 means the player did not start.
-- pos_rank_* of 999 is Sleeper's unranked sentinel and is stored as null.
-- Real ranks in these dumps stay well under 200.
-- TEAM_* ids are not in the player catalog. They are stored under that raw
-- id, the same resolution path as counting stats. Fantasy D/ST uses the
-- catalog id (PHI, not TEAM_PHI).
-- A player snap can exceed the team total by a few snaps in 2025 and 2026
-- (Sleeper's team total lags). The share view does not clamp that.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS player_week_sleeper_context (
    year INTEGER NOT NULL REFERENCES seasons (year) ON DELETE CASCADE,
    week INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    gp INTEGER,
    gs INTEGER,
    off_snp INTEGER,
    def_snp INTEGER,
    st_snp INTEGER,
    tm_off_snp INTEGER,
    tm_def_snp INTEGER,
    tm_st_snp INTEGER,
    pos_rank_ppr INTEGER,
    pos_rank_half_ppr INTEGER,
    pos_rank_std INTEGER,
    PRIMARY KEY (year, week, player_id)
);

CREATE INDEX IF NOT EXISTS player_week_sleeper_context_player_idx
    ON player_week_sleeper_context (player_id, year, week);

-- Snap share. A zero or missing team total is unknown, not a 0% share.
CREATE OR REPLACE VIEW v_player_week_snap_share AS
SELECT
    c.year,
    c.week,
    c.player_id,
    c.gp,
    c.gs,
    c.off_snp,
    c.def_snp,
    c.st_snp,
    c.tm_off_snp,
    c.tm_def_snp,
    c.tm_st_snp,
    c.pos_rank_ppr,
    c.pos_rank_half_ppr,
    c.pos_rank_std,
    CASE
        WHEN c.off_snp IS NULL OR c.tm_off_snp IS NULL OR c.tm_off_snp = 0 THEN NULL
        ELSE c.off_snp::double precision / c.tm_off_snp
    END AS off_snap_share,
    CASE
        WHEN c.def_snp IS NULL OR c.tm_def_snp IS NULL OR c.tm_def_snp = 0 THEN NULL
        ELSE c.def_snp::double precision / c.tm_def_snp
    END AS def_snap_share,
    CASE
        WHEN c.st_snp IS NULL OR c.tm_st_snp IS NULL OR c.tm_st_snp = 0 THEN NULL
        ELSE c.st_snp::double precision / c.tm_st_snp
    END AS st_snap_share
FROM player_week_sleeper_context c;
