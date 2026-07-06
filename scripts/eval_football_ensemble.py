"""
Evalúa OUT-OF-SAMPLE si el ensemble GLM Poisson + XGBoost mejora el 1X2 de fútbol.

Ambos modelos se entrenan con season < 2024-2025, así que la temporada 2024-2025
es OOS para los dos. Barre el peso del GLM y reporta log-loss / Brier / MAE del 1X2
derivado (score_matrix Dixon-Coles, ρ=-0.10, igual que la app).

NO despliega nada: es solo medición para decidir con evidencia.

Uso:
    venv\\Scripts\\activate
    python scripts/eval_football_ensemble.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.football.models import HOME_MODEL_FEATURES, AWAY_MODEL_FEATURES  # noqa: E402
from sports.football.markets import score_matrix  # noqa: E402

TEST_SEASON = "2024-2025"
RHO = -0.10
WEIGHTS = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.0]   # peso del GLM


def one_x_two(lh, la, rho=RHO):
    m = score_matrix(lh, la, rho=rho)
    return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())


def _logloss(probs, outcomes):
    idx = {"H": 0, "D": 1, "A": 2}
    p = np.clip(probs, 1e-12, 1.0)
    return float(np.mean([-np.log(p[i, idx[o]]) for i, o in enumerate(outcomes)]))


def _brier(probs, outcomes):
    idx = {"H": 0, "D": 1, "A": 2}
    y = np.zeros_like(probs)
    for i, o in enumerate(outcomes):
        y[i, idx[o]] = 1.0
    return float(np.mean(np.sum((probs - y) ** 2, axis=1)))


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    feats = root / "data" / "processed" / "football_features.csv"
    glm_path = root / "data" / "models" / "football_poisson_v1.joblib"
    xgb_path = root / "data" / "models" / "football_xgboost_v1.joblib"
    for p in (feats, glm_path, xgb_path):
        if not p.exists():
            print(f"[ERR] Falta {p}")
            return 1

    df = pd.read_csv(feats, parse_dates=["date"])
    cols = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    df = df[df[cols].notna().all(axis=1) & (df["season"] == TEST_SEASON)].sort_values("date")
    print(f"Partidos OOS (TEST {TEST_SEASON}): {len(df):,}")

    glm = joblib.load(glm_path)
    xgb = joblib.load(xgb_path)
    g = glm.predict_lambda(df)
    x = xgb.predict_lambda(df)
    gh, ga = g["lambda_home"].values, g["lambda_away"].values
    xh, xa = x["lambda_home"].values, x["lambda_away"].values

    outcomes = np.where(df["home_goals"].values > df["away_goals"].values, "H",
                        np.where(df["home_goals"].values == df["away_goals"].values, "D", "A"))
    real_h, real_a = df["home_goals"].values, df["away_goals"].values

    print("=" * 66)
    print(f"  {'w_GLM':>6} | {'log-loss':>9} | {'Brier':>7} | {'MAE goles':>9}")
    print("-" * 66)
    best = None
    for w in WEIGHTS:
        lh = w * gh + (1 - w) * xh
        la = w * ga + (1 - w) * xa
        probs = np.array([one_x_two(a, b) for a, b in zip(lh, la)])
        ll = _logloss(probs, outcomes)
        br = _brier(probs, outcomes)
        mae = float((np.abs(lh - real_h).mean() + np.abs(la - real_a).mean()) / 2)
        tag = "  <- GLM puro (actual)" if w == 1.0 else ""
        print(f"  {w:>6.1f} | {ll:>9.4f} | {br:>7.4f} | {mae:>9.4f}{tag}")
        if best is None or ll < best[1]:
            best = (w, ll)
    print("=" * 66)
    base_ll = _logloss(np.array([one_x_two(a, b) for a, b in zip(gh, ga)]), outcomes)
    print(f"  Mejor peso GLM = {best[0]:.1f}  (log-loss {best[1]:.4f} vs GLM puro {base_ll:.4f}, "
          f"{best[1]-base_ll:+.4f})")
    if best[0] < 1.0 and best[1] < base_ll:
        print("  -> El ensemble MEJORA OOS. Merece integrarse (en la generación offline de picks).")
    else:
        print("  -> El ensemble NO mejora OOS. Quedarse con el GLM puro.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
