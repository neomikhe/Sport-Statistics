-- ============================================================
-- SportStatistics — Historial de predicciones (aciertos por partido)
-- ============================================================
-- Guarda las N situaciones más probables de cada partido ANTES de jugarse.
-- Cuando el partido termina, se resuelve cada situación (acierto/fallo) contra
-- el resultado real. Con esos datos se mide la fiabilidad por mercado y se pulen
-- los cálculos. Caducidad automática (se borran los partidos antiguos).
--
-- Idempotente. Ejecutar:
--   psql ... -f core/database/schema_history.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS match_predictions (
    id           BIGSERIAL PRIMARY KEY,
    sport        VARCHAR(20)  NOT NULL,        -- football | basketball | baseball | tennis
    match_key    VARCHAR(240) NOT NULL,        -- clave estable: sport:date:home:away
    match_date   DATE         NOT NULL,
    home         VARCHAR(120) NOT NULL,
    away         VARCHAR(120) NOT NULL,
    home_id      BIGINT,                       -- id en entities (para resolver por id, no por nombre)
    away_id      BIGINT,
    grupo        VARCHAR(60)  NOT NULL,
    mercado      VARCHAR(160) NOT NULL,
    probability  REAL         NOT NULL,        -- prob del modelo al predecir
    rank         SMALLINT,                     -- 1..N (posición en el top del partido)
    hit          BOOLEAN,                      -- NULL = pendiente; TRUE/FALSE = resuelto; (push = fila borrada)
    resolved_at  TIMESTAMP,
    created_at   TIMESTAMP    DEFAULT NOW()
);

-- Una fila por (partido, mercado): re-loguear no duplica.
CREATE UNIQUE INDEX IF NOT EXISTS ux_match_predictions
    ON match_predictions (match_key, grupo, mercado);

CREATE INDEX IF NOT EXISTS ix_match_predictions_date    ON match_predictions (match_date);
CREATE INDEX IF NOT EXISTS ix_match_predictions_pending ON match_predictions (hit) WHERE hit IS NULL;
CREATE INDEX IF NOT EXISTS ix_match_predictions_sport   ON match_predictions (sport, grupo);
