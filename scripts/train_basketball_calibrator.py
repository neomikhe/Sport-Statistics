"""
Entrena el calibrador isotónico binario del moneyline NBA.

Corrige el sesgo del modelo sobre P(gana el local), sin cambiar el orden.

Lee:    data/processed/basketball_features.csv
        data/models/basketball_score_v1.joblib
Guarda: data/models/basketball_calibrator_v1.joblib  (numpy puro, sin sklearn al cargar)

p_home se reproduce igual que la app: marcador ~ Normal(E, σ=11) ->
p_home = Φ((E_local - E_visit) / (√2 · σ)).  Se calibra sobre el ÚLTIMO 30%
temporal (out-of-sample).

Uso:
    venv\\Scripts\\activate
    python scripts/train_basketball_calibrator.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.basketball.markets import SIGMA_TEAM  # noqa: E402
from core.calibration.isotonic import BinaryIsotonicCalibrator  # noqa: E402

VAL_FRACTION = 0.30


def _logloss(p, y) -> float:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _brier(p, y) -> float:
    return float(np.mean((p - y) ** 2))


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    feats_path = root / "data" / "processed" / "basketball_features.csv"
    model_path = root / "data" / "models" / "basketball_score_v1.joblib"
    out_path = root / "data" / "models" / "basketball_calibrator_v1.joblib"

    if not feats_path.exists() or not model_path.exists():
        print("[ERR] Faltan features o modelo NBA. Ejecuta el pipeline de baloncesto primero.")
        return 1

    df = pd.read_csv(feats_path, parse_dates=["date"]).sort_values("date")
    model = joblib.load(model_path)

    needed = list(set(model.home_features) | set(model.away_features)
                  | {"home_score", "away_score"})
    df = df.dropna(subset=needed).reset_index(drop=True)
    if len(df) < 500:
        print(f"[ERR] Pocos partidos con features completas: {len(df)}.")
        return 1

    pred = model.predict_score(df)
    diff = pred["expected_home"].values - pred["expected_away"].values
    p_home = norm.cdf(diff / (np.sqrt(2.0) * SIGMA_TEAM))
    y_home = (df["home_score"].values > df["away_score"].values).astype(float)

    cut = int(len(df) * (1 - VAL_FRACTION))
    ph_val, y_val = p_home[cut:], y_home[cut:]
    print(f"Partidos de calibración (último {int(VAL_FRACTION*100)}% temporal): {len(ph_val):,}")

    # --- Evaluación OUT-OF-SAMPLE dentro de la ventana de validación ---
    icut = int(len(ph_val) * 0.70)
    oos = BinaryIsotonicCalibrator().fit(ph_val[:icut], y_val[:icut])
    ev_raw, ev_y = ph_val[icut:], y_val[icut:]
    ev_cal = oos.transform(ev_raw)
    print("=" * 60)
    print("  CALIBRACIÓN MONEYLINE NBA — evaluación OUT-OF-SAMPLE (últ. 30%)")
    print("=" * 60)
    print(f"  Log-loss : {_logloss(ev_raw, ev_y):.4f}  ->  {_logloss(ev_cal, ev_y):.4f}")
    print(f"  Brier    : {_brier(ev_raw, ev_y):.4f}  ->  {_brier(ev_cal, ev_y):.4f}")

    # --- Gate: solo se despliega si MEJORA out-of-sample ---
    if _logloss(ev_cal, ev_y) < _logloss(ev_raw, ev_y):
        BinaryIsotonicCalibrator().fit(ph_val, y_val).save(out_path)
        print(f"[OK] Mejora OOS confirmada -> calibrador guardado: {out_path}")
        print("     El analizador lo aplicará al moneyline NBA automáticamente.")
    else:
        if out_path.exists():
            out_path.unlink()
        print("[SKIP] La calibración NO mejora OOS -> no se despliega (se usa prob cruda).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
