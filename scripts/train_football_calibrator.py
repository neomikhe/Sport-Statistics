"""
Entrena el calibrador isotónico 1X2 de fútbol (mejora de PRECISIÓN, no visual).

Corrige el sesgo sistemático del modelo (p. ej. sobrepredecir al local) sobre las
probabilidades 1X2 que muestra el analizador, sin cambiar el orden relativo.

Lee:    data/processed/football_features.csv   (mismo que train_football_model.py)
        data/models/football_poisson_v1.joblib  (modelo ya entrenado)
Guarda: data/models/football_calibrator_v1.joblib   (numpy puro, sin sklearn al cargar)

Se calibra sobre la temporada TEST (out-of-sample: el modelo NO se entrenó con ella),
usando EXACTAMENTE el mismo generador de probabilidades que la app: score_matrix
Dixon-Coles con rho = -0.10.

Uso:
    venv\\Scripts\\activate
    python scripts/train_football_calibrator.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.football.models import (  # noqa: E402
    HOME_MODEL_FEATURES, AWAY_MODEL_FEATURES,
)
from sports.football.markets import score_matrix  # noqa: E402
from core.calibration.isotonic import IsotonicCalibrator3way  # noqa: E402

TEST_SEASON = "2024-2025"      # mismo split que train_football_model.py
RHO = -0.10                    # DEBE coincidir con el RHO del analizador


def one_x_two(lh: float, la: float, rho: float = RHO):
    """P(H), P(D), P(A) desde la matriz Dixon-Coles (idéntico a la app)."""
    m = score_matrix(lh, la, rho=rho)
    p_home = float(np.tril(m, -1).sum())   # filas(home) > cols(away)
    p_draw = float(np.trace(m))
    p_away = float(np.triu(m, 1).sum())
    return p_home, p_draw, p_away


def _logloss(probs, outcomes) -> float:
    idx = {"H": 0, "D": 1, "A": 2}
    p = np.clip(probs, 1e-12, 1.0)
    return float(np.mean([-np.log(p[i, idx[o]]) for i, o in enumerate(outcomes)]))


def _brier(probs, outcomes) -> float:
    idx = {"H": 0, "D": 1, "A": 2}
    y = np.zeros_like(probs)
    for i, o in enumerate(outcomes):
        y[i, idx[o]] = 1.0
    return float(np.mean(np.sum((probs - y) ** 2, axis=1)))


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    features_path = root / "data" / "processed" / "football_features.csv"
    model_path = root / "data" / "models" / "football_poisson_v1.joblib"
    out_path = root / "data" / "models" / "football_calibrator_v1.joblib"

    if not features_path.exists():
        print(f"[ERR] No existe {features_path}. Ejecuta build_football_features.py primero.")
        return 1
    if not model_path.exists():
        print(f"[ERR] No existe {model_path}. Ejecuta train_football_model.py primero.")
        return 1

    df = pd.read_csv(features_path, parse_dates=["date"])
    model = joblib.load(model_path)

    feats = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    complete = df[feats].notna().all(axis=1)
    val = df[complete & (df["season"] == TEST_SEASON)].sort_values("date").copy()
    print(f"Partidos de calibración (TEST {TEST_SEASON}): {len(val):,}")
    if len(val) < 200:
        print("[ERR] Muy pocos partidos para calibrar de forma fiable (>=200).")
        return 1

    pred = model.predict_lambda(val)
    val["lh"] = pred["lambda_home"].values
    val["la"] = pred["lambda_away"].values

    probs = np.array([one_x_two(lh, la) for lh, la in zip(val["lh"], val["la"])])
    outcomes = np.where(
        val["home_goals"].values > val["away_goals"].values, "H",
        np.where(val["home_goals"].values == val["away_goals"].values, "D", "A"),
    )

    # --- Evaluación OUT-OF-SAMPLE: ajusta en 70% y mide en el 30% más reciente ---
    cut = int(len(probs) * 0.70)
    oos = IsotonicCalibrator3way().fit(probs[:cut], outcomes[:cut])
    ev_raw, ev_y = probs[cut:], outcomes[cut:]
    ev_cal = oos.transform(ev_raw)
    print("=" * 60)
    print("  CALIBRACIÓN 1X2 — evaluación OUT-OF-SAMPLE (últ. 30% del TEST)")
    print("=" * 60)
    print(f"  Log-loss : {_logloss(ev_raw, ev_y):.4f}  ->  {_logloss(ev_cal, ev_y):.4f}")
    print(f"  Brier    : {_brier(ev_raw, ev_y):.4f}  ->  {_brier(ev_cal, ev_y):.4f}")
    print("  (menor es mejor; si baja aquí, la mejora es real)")

    # --- Gate: solo se despliega si MEJORA out-of-sample ---
    if _logloss(ev_cal, ev_y) < _logloss(ev_raw, ev_y):
        IsotonicCalibrator3way().fit(probs, outcomes).save(out_path)
        print(f"[OK] Mejora OOS confirmada -> calibrador guardado: {out_path}")
        print("     El analizador lo aplicará automáticamente al 1X2 de fútbol.")
    else:
        if out_path.exists():
            out_path.unlink()
        print("[SKIP] La calibración NO mejora OOS -> no se despliega (se usa prob cruda).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
