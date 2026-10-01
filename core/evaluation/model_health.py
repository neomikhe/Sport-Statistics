import numpy as np

from core.evaluation.metrics import (
    brier_score_multiclass,
    log_loss_multiclass,
    outcomes_from_goals,
)

RHO = -0.10


def football_1x2_probs(model, df):
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
    probs = football_1x2_probs(model, df)
    outcomes = outcomes_from_goals(df["home_goals"].values, df["away_goals"].values)
    valid = ~np.isnan(probs).any(axis=1)
    probs, outcomes = probs[valid], outcomes[valid]
    return {
        "n": int(valid.sum()),
        "log_loss": log_loss_multiclass(probs, outcomes),
        "brier": brier_score_multiclass(probs, outcomes),
    }
