-- Córners y tarjetas en football_matches (migración idempotente).
-- El dato crudo de football-data.co.uk trae estas columnas; antes solo se
-- guardaban los goles. Se rellenan al re-ingestar (ON CONFLICT DO UPDATE).
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS home_corners INT;
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS away_corners INT;
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS home_yellows INT;
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS away_yellows INT;
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS home_reds INT;
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS away_reds INT;

-- Hits, jonrones y ponches en baseball_games (migración idempotente).
-- Los game logs de Retrosheet los traen; antes solo se guardaban las carreras.
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS home_hits INT;
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS away_hits INT;
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS home_hr INT;
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS away_hr INT;
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS home_so INT;
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS away_so INT;
