-- v2: lesiones NBA, abridores MLB y xG de fútbol (idempotente).

CREATE TABLE IF NOT EXISTS nba_injuries (
    id BIGSERIAL PRIMARY KEY,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    player_name VARCHAR(200) NOT NULL,
    team_name VARCHAR(100),
    update_date DATE,
    status VARCHAR(50),
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_nba_injuries_team ON nba_injuries(team_name, fetched_at);
CREATE INDEX IF NOT EXISTS idx_nba_injuries_player ON nba_injuries(player_name, fetched_at);

CREATE TABLE IF NOT EXISTS mlb_starters (
    id BIGSERIAL PRIMARY KEY,
    game_date DATE NOT NULL,
    game_pk BIGINT,
    home_team VARCHAR(100) NOT NULL,
    away_team VARCHAR(100) NOT NULL,
    home_starter_name VARCHAR(200),
    away_starter_name VARCHAR(200),
    home_starter_id BIGINT,
    away_starter_id BIGINT,
    home_starter_throws CHAR(1),
    away_starter_throws CHAR(1),
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (game_date, home_team, away_team)
);
CREATE INDEX IF NOT EXISTS idx_mlb_starters_date ON mlb_starters(game_date);

CREATE TABLE IF NOT EXISTS mlb_pitcher_stats (
    id BIGSERIAL PRIMARY KEY,
    season INT NOT NULL,
    pitcher_name VARCHAR(200) NOT NULL,
    pitcher_id BIGINT,
    team VARCHAR(50),
    ip NUMERIC(6,1),
    era NUMERIC(5,3),
    fip NUMERIC(5,3),
    xfip NUMERIC(5,3),
    k_pct NUMERIC(5,3),
    bb_pct NUMERIC(5,3),
    whip NUMERIC(5,3),
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (season, pitcher_name)
);
CREATE INDEX IF NOT EXISTS idx_mlb_pitcher_stats_name ON mlb_pitcher_stats(pitcher_name);

CREATE TABLE IF NOT EXISTS football_xg (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT REFERENCES football_matches(id) ON DELETE CASCADE,
    statsbomb_match_id BIGINT,
    home_xg NUMERIC(4,2),
    away_xg NUMERIC(4,2),
    home_xa NUMERIC(4,2),
    away_xa NUMERIC(4,2),
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (match_id)
);
CREATE INDEX IF NOT EXISTS idx_football_xg_match ON football_xg(match_id);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO betstats_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO betstats_app;
