"""
Salud del modelo de fútbol: log-loss / Brier 1X2 reutilizables.

Lo usan DOS piezas del mantenimiento automático:
  - El GATE de re-entrenamiento (scripts/retrain_all.py): comparar modelo nuevo vs
    viejo sobre el mismo hold-out y hacer rollback si empeora.
  - El MONITOR de deriva (scripts/monitor_drift.py): medir el log-loss del modelo
    DESPLEGADO sobre partidos recientes ya cerrados y avisar si se degrada.

Ambos necesitan lo mismo: dado (modelo, partidos con goles reales), el 1X2 y su
log-loss. Aquí vive esa lógica una sola vez (DRY).
"""
import numpy as np

from core.evaluation.metrics import (
    brier_score_multiclass,
    log_loss_multiclass,
    outcomes_from_goals,
)

RHO = -0.10  # Dixon-Coles, idéntico al analizador y al pipeline de picks.


def football_1x2_probs(model, df):
    """Array (n, 3) con [P(H), P(D), P(A)] del modelo para cada fila de `df`.

    `df` debe tener las columnas de features que espera `model.predict_lambda`.
    """
    from sports.football.markets import score_matrix

    pred = model.predict_lambda(df)
    lh = pred["lambda_home"].values
    la = pred["lambda_away"].values
    out = np.empty((len(lh), 3), dtype=float)
    for i, (a, b) in enumerate(zip(lh, la)):
        m = score_matrix(a, b, rho=RHO)
        out[i] = (float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum()))
    return out


def football_health(model, df) -> dict:
    """Salud del modelo sobre `df` (que debe traer home_goals/away_goals reales).

    Devuelve {n, log_loss, brier}. Menor log-loss/Brier = mejor.
    """
    probs = football_1x2_probs(model, df)
    outcomes = outcomes_from_goals(df["home_goals"].values, df["away_goals"].values)
    # Descarta filas que el modelo no puede predecir (features incompletas → λ NaN).
    valid = ~np.isnan(probs).any(axis=1)
    probs, outcomes = probs[valid], outcomes[valid]
    return {
        "n": int(valid.sum()),
        "log_loss": log_loss_multiclass(probs, outcomes),
        "brier": brier_score_multiclass(probs, outcomes),
    }
