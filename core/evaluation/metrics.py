import numpy as np
import pandas as pd


OUTCOME_INDEX = {"H": 0, "D": 1, "A": 2}
OUTCOME_LABELS = ["H", "D", "A"]


def outcomes_from_goals(home_goals, away_goals):
    hg = np.asarray(home_goals)
    ag = np.asarray(away_goals)
    out = np.empty(len(hg), dtype="<U1")
    out[hg > ag] = "H"
    out[hg == ag] = "D"
    out[hg < ag] = "A"
    return out


def log_loss_multiclass(probs, outcomes, eps=1e-15):
    probs = np.clip(np.asarray(probs, dtype=float), eps, 1 - eps)
    outcomes = np.asarray(outcomes)
    true_idx = np.array([OUTCOME_INDEX[o] for o in outcomes])
    true_probs = probs[np.arange(len(outcomes)), true_idx]
    return float(-np.log(true_probs).mean())


def brier_score_multiclass(probs, outcomes):
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes)
    one_hot = np.zeros((len(outcomes), 3))
    true_idx = np.array([OUTCOME_INDEX[o] for o in outcomes])
    one_hot[np.arange(len(outcomes)), true_idx] = 1.0
    return float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))


def accuracy(probs, outcomes):
    probs = np.asarray(probs)
    outcomes = np.asarray(outcomes)
    preds = np.argmax(probs, axis=1)
    true_idx = np.array([OUTCOME_INDEX[o] for o in outcomes])
    return float((preds == true_idx).mean())


def naive_probabilities(outcomes_train):
    outcomes_train = np.asarray(outcomes_train)
    n = len(outcomes_train)
    return np.array([
        (outcomes_train == "H").sum() / n,
        (outcomes_train == "D").sum() / n,
        (outcomes_train == "A").sum() / n,
    ])


def implied_probabilities(odds_h, odds_d, odds_a):
    raw = np.stack(
        [1.0 / np.asarray(odds_h, dtype=float),
         1.0 / np.asarray(odds_d, dtype=float),
         1.0 / np.asarray(odds_a, dtype=float)],
        axis=1,
    )
    total = raw.sum(axis=1, keepdims=True)
    return raw / total


def calibration_table(probs, outcomes, n_bins=10):
    probs = np.asarray(probs)
    outcomes = np.asarray(outcomes)
    rows = []
    for k, label in enumerate(OUTCOME_LABELS):
        p_k = probs[:, k]
        is_true = (outcomes == label).astype(float)
        bins = np.linspace(0, 1, n_bins + 1)
        for i in range(n_bins):
            if i < n_bins - 1:
                mask = (p_k >= bins[i]) & (p_k < bins[i + 1])
            else:
                mask = (p_k >= bins[i]) & (p_k <= bins[i + 1])
            if mask.sum() == 0:
                continue
            rows.append({
                "outcome": label,
                "bin_low": float(bins[i]),
                "bin_high": float(bins[i + 1]),
                "mean_pred": float(p_k[mask].mean()),
                "freq_obs": float(is_true[mask].mean()),
                "n": int(mask.sum()),
            })
    return pd.DataFrame(rows)
