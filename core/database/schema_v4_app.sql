-- v4: tablas de la app (selecciones y app_meta) (idempotente).

CREATE TABLE IF NOT EXISTS football_picks (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(9) NOT NULL,
    date DATE NOT NULL,
    league VARCHAR(50),
    home VARCHAR(200),
    away VARCHAR(200),
    selection VARCHAR(10),
    prob_model NUMERIC(6,4),
    odds NUMERIC(6,3),
    ev NUMERIC(7,4),
    kelly_frac NUMERIC(7,4),
    stake NUMERIC(10,2),
    real_result VARCHAR(10),
    generated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_football_picks_season ON football_picks(season);

CREATE TABLE IF NOT EXISTS app_meta (
    key VARCHAR(50) PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
