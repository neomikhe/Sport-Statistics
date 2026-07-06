"""
Sonda OOS: ¿la calibración isotónica mejora los mercados Over 2.5 y BTTS de fútbol?

El 1X2 ya estaba bien calibrado (calibrarlo empeoraba OOS). Pero los picks premium
salen sobre todo de Over/Under y BTTS, que pueden tener sesgo sistemático distinto.
Mide OOS (ajusta 70% / evalúa 30%) sobre la temporada 2024-2025 (OOS del modelo base).

Solo medición; no despliega nada.

Uso:
    venv\\Scripts\\activate
    python scripts/eval_football_markets_calibration.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.football.models import HOME_MODEL_FEATURES, AWAY_MODEL_FEATURES  # noqa: E402
from sports.football.markets import score_matrix  # noqa: E402
from core.calibration.isotonic import BinaryIsotonicCalibrator  # noqa: E402

TEST_SEASON = "2024-2025"
RHO = -0.10


def _logloss(p, y):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _brier(p, y):
    return float(np.mean((p - y) ** 2))


def _probe(name, p_model, y):
    cut = int(len(p_model) * 0.70)
    cal = BinaryIsotonicCalibrator().fit(p_model[:cut], y[:cut])
    ev_raw, ev_y = p_model[cut:], y[cut:]
    ev_cal = cal.transform(ev_raw)
    ll0, ll1 = _logloss(ev_raw, ev_y), _logloss(ev_cal, ev_y)
    br0, br1 = _brier(ev_raw, ev_y), _brier(ev_cal, ev_y)
    verdict = "MEJORA" if ll1 < ll0 else "no mejora"
    print(f"  {name:<12} log-loss {ll0:.4f} -> {ll1:.4f} | Brier {br0:.4f} -> {br1:.4f}  [{verdict}]")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    feats = root / "data" / "processed" / "football_features.csv"
    glm_path = root / "data" / "models" / "football_poisson_v1.joblib"
    df = pd.read_csv(feats, parse_dates=["date"])
    cols = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    df = df[df[cols].notna().all(axis=1) & (df["season"] == TEST_SEASON)].sort_values("date")
    glm = joblib.load(glm_path)
    pred = glm.predict_lambda(df)
    lh, la = pred["lambda_home"].values, pred["lambda_away"].values

    over25, btts = [], []
    for a, b in zip(lh, la):
        m = score_matrix(a, b, rho=RHO)
        n = m.shape[0]
        h = np.arange(n)[:, None] * np.ones((1, n), dtype=int)
        aw = np.ones((n, 1), dtype=int) * np.arange(n)[None, :]
        over25.append(float(m[(h + aw) >= 3].sum()))
        btts.append(float(m[(h >= 1) & (aw >= 1)].sum()))
    over25, btts = np.array(over25), np.array(btts)

    rh, ra = df["home_goals"].values, df["away_goals"].values
    y_over = ((rh + ra) >= 3).astype(float)
    y_btts = ((rh >= 1) & (ra >= 1)).astype(float)

    print(f"Partidos OOS (TEST {TEST_SEASON}): {len(df):,}")
    print("=" * 68)
    _probe("Over 2.5", over25, y_over)
    _probe("BTTS", btts, y_btts)
    print("=" * 68)
    print("  Si algún mercado MEJORA, merece un calibrador propio (con gate OOS).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
