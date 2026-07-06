"""
Entrena el modelo XGBoost de futbol y lo combina con el GLM Poisson.

Lee:   data/processed/football_features.csv
Guarda: data/models/football_xgboost_v1.joblib

Reporta MAE en test (2024-2025) para:
  - GLM Poisson solo
  - XGBoost solo
  - Ensemble 50/50

Uso:
    venv\\Scripts\\activate
    python scripts/train_football_xgboost.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.football.models import (  # noqa: E402
    FootballPoissonModel, HOME_MODEL_FEATURES, AWAY_MODEL_FEATURES,
)
from sports.football.models_xgboost import (  # noqa: E402
    FootballXGBoostModel, FootballEnsembleModel,
)


SPLIT_SEASON = "2024-2025"


def main():
    root = Path(__file__).resolve().parent.parent
    features_path = root / "data" / "processed" / "football_features.csv"
    model_dir = root / "data" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    xgb_path = model_dir / "football_xgboost_v1.joblib"
    glm_path = model_dir / "football_poisson_v1.joblib"

    if not features_path.exists():
        print("[ERR] Falta football_features.csv. Ejecuta build_football_features.py")
        return 1

    print("Cargando features...")
    df = pd.read_csv(features_path, parse_dates=["date"])
    all_feats = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    df_clean = df[df[all_feats + ["home_goals", "away_goals"]].notna().all(axis=1)].copy()

    df_train = df_clean[df_clean["season"] < SPLIT_SEASON].copy()
    df_test = df_clean[df_clean["season"] == SPLIT_SEASON].copy()
    print(f"TRAIN: {len(df_train):,}  TEST: {len(df_test):,}")

    if len(df_train) < 1000 or len(df_test) < 100:
        print("[ERR] Datos insuficientes.")
        return 1

    # ---- Entrenar XGBoost ----
    print("\nEntrenando XGBoost (objetivo Poisson)...")
    xgb_model = FootballXGBoostModel().fit(df_train)
    joblib.dump(xgb_model, xgb_path)
    print(f"  [OK] Guardado: {xgb_path}")

    # ---- Cargar GLM si existe ----
    if glm_path.exists():
        glm_model = joblib.load(glm_path)
        print(f"  [OK] GLM cargado: {glm_path}")
    else:
        print("  [INFO] GLM no encontrado, entrenando ahora...")
        glm_model = FootballPoissonModel().fit(df_train)
        joblib.dump(glm_model, glm_path)

    # ---- Ensemble ----
    ensemble = FootballEnsembleModel(glm_model, xgb_model, glm_weight=0.5)

    # ---- Evaluacion ----
    print("\n" + "=" * 70)
    print("  COMPARACION EN TEST (temporada 2024-2025)")
    print("=" * 70)

    for name, model in [
        ("GLM Poisson",         glm_model),
        ("XGBoost (Poisson)",   xgb_model),
        ("Ensemble 50/50",      ensemble),
    ]:
        pred = model.predict_lambda(df_test)
        mae_h = float((pred["lambda_home"].values - df_test["home_goals"].values).__abs__().mean())
        mae_a = float((pred["lambda_away"].values - df_test["away_goals"].values).__abs__().mean())
        # Predicted vs real means (calibration check)
        mean_pred_h = float(pred["lambda_home"].mean())
        mean_pred_a = float(pred["lambda_away"].mean())
        print(f"  {name:<22}  MAE H={mae_h:.3f}  MAE A={mae_a:.3f}  "
              f"mean pred H/A: {mean_pred_h:.3f}/{mean_pred_a:.3f}")

    print()
    print("[OK] Entrenamiento XGBoost completado.")
    print("     Para usar el ensemble en picks, ver `core/calibration/market_blend.py`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
