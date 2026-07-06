"""
La prueba de fuego del proyecto: ¿la probabilidad del MODELO es más acertada que la
del MERCADO (línea de cierre, el mejor estimador de la probabilidad real disponible)?

Mide OOS sobre 2024-2025 (el modelo no se entrenó con ella):
  1. Log-loss / Brier del 1X2 del MODELO vs de la LÍNEA DE CIERRE (sin margen).
  2. ¿En qué % de partidos el modelo "acierta más" que el mercado?
  3. Value-betting: apuesta donde el modelo ve edge, stake por Kelly fraccional,
     y reporta ROI + CLV implícito medio (modelo vs cierre).

El modelo NUNCA usa cuotas para predecir; las cuotas solo se usan aquí para VALIDAR
y para dimensionar la apuesta. Es la mejor estadística aplicada a tu probabilidad.

Uso:
    venv\\Scripts\\activate
    python scripts/eval_probability_vs_market.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.football.models import HOME_MODEL_FEATURES, AWAY_MODEL_FEATURES  # noqa: E402
from sports.football.markets import score_matrix  # noqa: E402
from core.betting.kelly import kelly_fractional  # noqa: E402
from core.betting.ev import expected_value  # noqa: E402
from core.betting.clv import implied_clv  # noqa: E402

TEST_SEASON = "2024-2025"
RHO = -0.10
EDGE_MIN = 0.03            # solo apostar si prob_modelo - prob_cierre > 3 %
KELLY_FRACTION = 0.25
IDX = {"H": 0, "D": 1, "A": 2}


def model_1x2(lh, la):
    m = score_matrix(lh, la, rho=RHO)
    return np.array([np.tril(m, -1).sum(), np.trace(m), np.triu(m, 1).sum()])


def market_1x2(oh, od, oa):
    """Prob implícita del cierre, quitando el margen (normaliza a 1)."""
    inv = np.array([1.0 / oh, 1.0 / od, 1.0 / oa])
    return inv / inv.sum()


def _logloss(probs, outcomes):
    return float(np.mean([-np.log(max(probs[i, IDX[o]], 1e-12)) for i, o in enumerate(outcomes)]))


def _brier(probs, outcomes):
    Y = np.zeros_like(probs)
    for i, o in enumerate(outcomes):
        Y[i, IDX[o]] = 1.0
    return float(np.mean(np.sum((probs - Y) ** 2, axis=1)))


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    df = pd.read_csv(root / "data" / "processed" / "football_features.csv", parse_dates=["date"])
    model = joblib.load(root / "data" / "models" / "football_poisson_v1.joblib")

    feats = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    odds_cols = ["odds_home_close", "odds_draw_close", "odds_away_close"]
    df = df[df[feats].notna().all(axis=1) & df[odds_cols].notna().all(axis=1)
            & (df["season"] == TEST_SEASON)].copy()
    df = df[(df[odds_cols] > 1.0).all(axis=1)]
    print(f"Partidos OOS con cuotas de cierre ({TEST_SEASON}): {len(df):,}")

    pred = model.predict_lambda(df)
    lh, la = pred["lambda_home"].values, pred["lambda_away"].values
    oh, od, oa = (df[c].values for c in odds_cols)
    outcomes = np.where(df["home_goals"].values > df["away_goals"].values, "H",
                        np.where(df["home_goals"].values == df["away_goals"].values, "D", "A"))

    p_model = np.array([model_1x2(a, b) for a, b in zip(lh, la)])
    p_mkt = np.array([market_1x2(a, b, c) for a, b, c in zip(oh, od, oa)])

    print("=" * 66)
    print("  ¿QUÉ PROBABILIDAD ES MÁS ACERTADA?  (OOS, menor = mejor)")
    print("=" * 66)
    print(f"  Log-loss  MODELO : {_logloss(p_model, outcomes):.4f}")
    print(f"  Log-loss  CIERRE : {_logloss(p_mkt, outcomes):.4f}")
    print(f"  Brier     MODELO : {_brier(p_model, outcomes):.4f}")
    print(f"  Brier     CIERRE : {_brier(p_mkt, outcomes):.4f}")

    # --- Value-betting con Kelly + CLV implícito ---
    staked, returned, clvs, n = 0.0, 0.0, [], 0
    odds_arr = np.stack([oh, od, oa], axis=1)
    for i, o in enumerate(outcomes):
        for k in range(3):
            edge = p_model[i, k] - p_mkt[i, k]
            if edge <= EDGE_MIN:
                continue
            price = odds_arr[i, k]
            if expected_value(p_model[i, k], price) <= 0:
                continue
            f = kelly_fractional(p_model[i, k], price, KELLY_FRACTION)
            f = min(f, 0.05)
            if f <= 0:
                continue
            n += 1
            staked += f
            won = (IDX[o] == k)
            returned += f * price if won else 0.0
            clvs.append(implied_clv(p_model[i, k], price))   # modelo vs cierre
    roi = (returned - staked) / staked * 100 if staked > 0 else 0.0
    print("=" * 66)
    print(f"  VALUE-BETTING (edge>{EDGE_MIN:.0%}, Kelly 1/4, cap 5%)")
    print("-" * 66)
    print(f"  Apuestas de valor : {n:,}")
    print(f"  ROI               : {roi:+.2f} %")
    if clvs:
        print(f"  CLV implícito medio: {np.mean(clvs)*100:+.2f} %  (modelo vs cierre)")
    print("=" * 66)
    print("  Nota: el cierre suele ganar en log-loss global (es muy afilado); lo que")
    print("  importa es si el modelo encuentra VALOR donde discrepa (ROI/CLV > 0).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
