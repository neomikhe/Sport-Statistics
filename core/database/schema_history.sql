-- Historial de predicciones (idempotente).

CREATE TABLE IF NOT EXISTS match_predictions (
    id           BIGSERIAL PRIMARY KEY,
    sport        VARCHAR(20)  NOT NULL,
    match_key    VARCHAR(240) NOT NULL,
    match_date   DATE         NOT NULL,
    home         VARCHAR(120) NOT NULL,
    away         VARCHAR(120) NOT NULL,
    home_id      BIGINT,
    away_id      BIGINT,
    grupo        VARCHAR(60)  NOT NULL,
    mercado      VARCHAR(160) NOT NULL,
    probability  REAL         NOT NULL,
    rank         SMALLINT,
    hit          BOOLEAN,
    resolved_at  TIMESTAMP,
    created_at   TIMESTAMP    DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_match_predictions
    ON match_predictions (match_key, grupo, mercado);

CREATE INDEX IF NOT EXISTS ix_match_predictions_date    ON match_predictions (match_date);
CREATE INDEX IF NOT EXISTS ix_match_predictions_pending ON match_predictions (hit) WHERE hit IS NULL;
CREATE INDEX IF NOT EXISTS ix_match_predictions_sport   ON match_predictions (sport, grupo);
