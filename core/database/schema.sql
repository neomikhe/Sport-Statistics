-- Esquema base: deportes, entidades y partidos (idempotente).

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO betstats_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO betstats_app;

CREATE TABLE IF NOT EXISTS sports (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(50) NOT NULL
);

INSERT INTO sports (code, name) VALUES
    ('football',   'Fútbol'),
    ('basketball', 'Baloncesto'),
    ('baseball',   'Béisbol'),
    ('tennis',     'Tenis')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS entities (
    id SERIAL PRIMARY KEY,
    sport_id INT NOT NULL REFERENCES sports(id) ON DELETE CASCADE,
    external_id VARCHAR(80),
    name VARCHAR(200) NOT NULL,
    country VARCHAR(3),
    metadata JSONB DEFAULT '{}'::jsonb,
    UNIQUE (sport_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_entities_sport_name ON entities(sport_id, name);

CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    sport_id INT NOT NULL REFERENCES sports(id),
    event_id BIGINT NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    model_version VARCHAR(50),
    probabilities JSONB NOT NULL,
    expected_values JSONB,
    raw_output JSONB
);
CREATE INDEX IF NOT EXISTS idx_predictions_sport_event ON predictions(sport_id, event_id);

CREATE TABLE IF NOT EXISTS picks (
    id BIGSERIAL PRIMARY KEY,
    prediction_id BIGINT REFERENCES predictions(id) ON DELETE SET NULL,
    market VARCHAR(50) NOT NULL,
    selection VARCHAR(50) NOT NULL,
    odds_taken NUMERIC(6,3) NOT NULL,
    odds_closing NUMERIC(6,3),
    ev NUMERIC(6,4),
    kelly_stake NUMERIC(6,4),
    status VARCHAR(20) DEFAULT 'pending',
    result_pnl NUMERIC(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_picks_status ON picks(status);

CREATE TABLE IF NOT EXISTS bankroll_history (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    balance NUMERIC(12,2) NOT NULL,
    delta NUMERIC(12,2),
    note TEXT
);

CREATE TABLE IF NOT EXISTS football_matches (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    league VARCHAR(50) NOT NULL,
    season VARCHAR(9) NOT NULL,
    home_team_id INT NOT NULL REFERENCES entities(id),
    away_team_id INT NOT NULL REFERENCES entities(id),
    home_goals INT,
    away_goals INT,
    home_xg NUMERIC(4,2),
    away_xg NUMERIC(4,2),
    home_corners INT,
    away_corners INT,
    home_yellows INT,
    away_yellows INT,
    home_reds INT,
    away_reds INT,
    odds_home_close NUMERIC(6,3),
    odds_draw_close NUMERIC(6,3),
    odds_away_close NUMERIC(6,3),
    odds_o25_close NUMERIC(6,3),
    odds_u25_close NUMERIC(6,3),
    source VARCHAR(50),
    UNIQUE (date, home_team_id, away_team_id)
);
CREATE INDEX IF NOT EXISTS idx_football_matches_date ON football_matches(date);
CREATE INDEX IF NOT EXISTS idx_football_matches_season ON football_matches(league, season);

CREATE TABLE IF NOT EXISTS football_elo (
    team_id INT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    elo NUMERIC(7,2) NOT NULL,
    PRIMARY KEY (team_id, date)
);

CREATE TABLE IF NOT EXISTS baseball_games (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    home_team_id INT NOT NULL REFERENCES entities(id),
    away_team_id INT NOT NULL REFERENCES entities(id),
    home_sp_id INT REFERENCES entities(id),
    away_sp_id INT REFERENCES entities(id),
    home_runs INT,
    away_runs INT,
    home_hits INT,
    away_hits INT,
    home_hr INT,
    away_hr INT,
    home_so INT,
    away_so INT,
    park_factor NUMERIC(4,3),
    weather JSONB,
    UNIQUE (date, home_team_id, away_team_id)
);
CREATE INDEX IF NOT EXISTS idx_baseball_games_date ON baseball_games(date);

CREATE TABLE IF NOT EXISTS basketball_games (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    home_team_id INT NOT NULL REFERENCES entities(id),
    away_team_id INT NOT NULL REFERENCES entities(id),
    home_score INT,
    away_score INT,
    pace NUMERIC(5,2),
    home_ortg NUMERIC(5,2),
    away_ortg NUMERIC(5,2),
    home_injuries JSONB,
    away_injuries JSONB,
    UNIQUE (date, home_team_id, away_team_id)
);
CREATE INDEX IF NOT EXISTS idx_basketball_games_date ON basketball_games(date);

CREATE TABLE IF NOT EXISTS tennis_matches (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    tournament VARCHAR(100),
    surface VARCHAR(10),
    round VARCHAR(20),
    best_of INT,
    player1_id INT NOT NULL REFERENCES entities(id),
    player2_id INT NOT NULL REFERENCES entities(id),
    winner_id INT REFERENCES entities(id),
    score VARCHAR(50),
    p1_aces INT,
    p1_df INT,
    p1_spw INT,
    p2_aces INT,
    p2_df INT,
    p2_spw INT
);
CREATE INDEX IF NOT EXISTS idx_tennis_matches_date ON tennis_matches(date);
CREATE INDEX IF NOT EXISTS idx_tennis_matches_players ON tennis_matches(player1_id, player2_id);

CREATE TABLE IF NOT EXISTS tennis_elo (
    player_id INT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    surface VARCHAR(10) NOT NULL,
    elo NUMERIC(7,2) NOT NULL,
    PRIMARY KEY (player_id, date, surface)
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO betstats_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO betstats_app;
