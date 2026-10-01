-- Columnas de córners, tarjetas y estadísticas MLB (idempotente).

ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS home_corners INT;
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS away_corners INT;
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS home_yellows INT;
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS away_yellows INT;
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS home_reds INT;
ALTER TABLE football_matches ADD COLUMN IF NOT EXISTS away_reds INT;

ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS home_hits INT;
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS away_hits INT;
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS home_hr INT;
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS away_hr INT;
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS home_so INT;
ALTER TABLE baseball_games ADD COLUMN IF NOT EXISTS away_so INT;
