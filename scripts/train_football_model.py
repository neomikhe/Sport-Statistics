"""
Entrena el modelo GLM Poisson de futbol.

Lee:   data/processed/football_features.csv
Guarda: data/models/football_poisson_v1.joblib

Split temporal (obligatorio - walk-forward viene en Paso 2.5):
    Train: todas las temporadas anteriores a 2024-2025
    Test:  2024-2025 (ultima temporada completa)
    Holdout live (no se toca): 2025-2026 (temporada actual en curso)

Evaluacion basica en el test set:
    - MAE de lambda vs goles reales
    - Media predicha vs media real (check de calibracion global)
    - Coeficientes + p-values de ambos modelos
    - 5 predicciones de ejemplo

Uso:
    venv\\Scripts\\activate
    python scripts/train_football_model.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.football.models import (  # noqa: E402
    FootballPoissonModel,
    HOME_MODEL_FEATURES,
    AWAY_MODEL_FEATURES,
)


TEST_SEASON = "2024-2025"
HOLDOUT_SEASON = "2025-2026"


def main():
    root = Path(__file__).resolve().parent.parent
    features_path = root / "data" / "processed" / "football_features.csv"
    model_dir = root / "data" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "football_poisson_v1.joblib"

    if not features_path.exists():
        print(f"[ERR] No existe {features_path}")
        print("      Ejecuta primero: python scripts/build_football_features.py")
        return 1

    print(f"Leyendo features desde: {features_path}")
    df = pd.read_csv(features_path, parse_dates=["date"])
    print(f"Total de filas: {len(df):,}")

    all_feats = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    complete = df[all_feats].notna().all(axis=1)
    df_clean = df[complete].copy()
    print(f"Filas con features completas: {len(df_clean):,}")

    # --- Split temporal ---
    df_train = df_clean[df_clean["season"] < TEST_SEASON].copy()
    df_test = df_clean[df_clean["season"] == TEST_SEASON].copy()
    df_holdout = df_clean[df_clean["season"] == HOLDOUT_SEASON].copy()

    print()
    print(f"TRAIN:   {len(df_train):>5,} partidos  ({df_train['season'].min()} a {df_train['season'].max()})")
    print(f"TEST:    {len(df_test):>5,} partidos  ({TEST_SEASON})")
    print(f"HOLDOUT: {len(df_holdout):>5,} partidos  ({HOLDOUT_SEASON}, no tocado)")

    if len(df_train) < 1000 or len(df_test) < 100:
        print("[ERR] Datos insuficientes para entrenar/evaluar.")
        return 1

    # --- Entrenar ---
    print()
    print("Entrenando modelos GLM Poisson...")
    model = FootballPoissonModel().fit(df_train)
    print(f"[OK] Entrenado con {model.trained_rows:,} filas de {len(model.trained_seasons)} temporadas.")

    # --- Guardar ---
    joblib.dump(model, model_path)
    print(f"[OK] Modelo guardado: {model_path}")

    # --- Evaluar en test ---
    pred = model.predict_lambda(df_test)
    df_test["lambda_home"] = pred["lambda_home"].values
    df_test["lambda_away"] = pred["lambda_away"].values

    mae_home = (df_test["lambda_home"] - df_test["home_goals"]).abs().mean()
    mae_away = (df_test["lambda_away"] - df_test["away_goals"]).abs().mean()

    mean_pred_h = df_test["lambda_home"].mean()
    mean_pred_a = df_test["lambda_away"].mean()
    mean_real_h = df_test["home_goals"].mean()
    mean_real_a = df_test["away_goals"].mean()

    print()
    print("=" * 72)
    print(f"  EVALUACION EN TEST (temporada {TEST_SEASON})")
    print("=" * 72)
    print(f"  MAE goles local      : {mae_home:.3f}   (benchmark bajo: <=1.00 razonable)")
    print(f"  MAE goles visitante  : {mae_away:.3f}")
    print()
    print(f"  Media predicha local : {mean_pred_h:.3f}   vs real: {mean_real_h:.3f}   (diff: {mean_pred_h - mean_real_h:+.3f})")
    print(f"  Media predicha visit : {mean_pred_a:.3f}   vs real: {mean_real_a:.3f}   (diff: {mean_pred_a - mean_real_a:+.3f})")
    print()
    print("  Una diferencia de medias > 0.05 indica mala calibracion global.")

    # --- Coeficientes ---
    print()
    print("=" * 72)
    print("  COEFICIENTES MODELO home_goals")
    print("=" * 72)
    print(model.summary_home)

    print()
    print("=" * 72)
    print("  COEFICIENTES MODELO away_goals")
    print("=" * 72)
    print(model.summary_away)

    # --- Ejemplos ---
    print()
    print("=" * 72)
    print("  5 PREDICCIONES DE EJEMPLO (test aleatorio)")
    print("=" * 72)
    sample = df_test.sample(n=min(5, len(df_test)), random_state=42).sort_values("date")
    for _, r in sample.iterrows():
        lh, la = r["lambda_home"], r["lambda_away"]
        gh, ga = int(r["home_goals"]), int(r["away_goals"])
        diff_h = lh - gh
        diff_a = la - ga
        print(f"  {r['date'].date()}  {r['league']:<16}  "
              f"lambda H/A: {lh:5.2f}/{la:5.2f}   real: {gh}-{ga}   "
              f"error: {diff_h:+.2f}/{diff_a:+.2f}")

    # --- Distribucion de lambda ---
    print()
    print("=" * 72)
    print("  DISTRIBUCION DE LAMBDAS PREDICHAS (test)")
    print("=" * 72)
    for col in ["lambda_home", "lambda_away"]:
        desc = df_test[col].describe().round(3)
        print(f"  {col}: min={desc['min']} mean={desc['mean']} max={desc['max']} std={desc['std']}")

    print()
    print("[OK] Paso 2.3 (GLM Poisson) completado.")
    print("     Siguiente: Paso 2.4 (simulacion Monte Carlo -> probabilidades 1X2).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
