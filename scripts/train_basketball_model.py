"""
Entrena el modelo de prediccion de marcador NBA (Ridge regression dual).

Lee:   data/processed/basketball_features.csv
Guarda: data/models/basketball_score_v1.joblib

Split temporal: train hasta 2024-06-30, test desde 2024-10-01 (temporada 2024-25 en adelante).

Uso:
    venv\\Scripts\\activate
    python scripts/train_basketball_model.py
"""
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.basketball.models import (  # noqa: E402
    BasketballScoreModel,
    HOME_MODEL_FEATURES,
    AWAY_MODEL_FEATURES,
)


SPLIT_DATE = "2024-10-01"  # inicio temporada 2024-25


def main():
    root = Path(__file__).resolve().parent.parent
    features_path = root / "data" / "processed" / "basketball_features.csv"
    model_dir = root / "data" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "basketball_score_v1.joblib"

    if not features_path.exists():
        print(f"[ERR] No existe {features_path}")
        print("      Ejecuta antes: python scripts/build_basketball_features.py")
        return 1

    df = pd.read_csv(features_path, parse_dates=["date"])
    all_feats = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    df_clean = df[df[all_feats].notna().all(axis=1)].copy()

    df_train = df_clean[df_clean["date"] < SPLIT_DATE].copy()
    df_test = df_clean[df_clean["date"] >= SPLIT_DATE].copy()

    print(f"Filas totales: {len(df):,}")
    print(f"Con features completas: {len(df_clean):,}")
    print(f"TRAIN: {len(df_train):,} partidos (< {SPLIT_DATE})")
    print(f"TEST:  {len(df_test):,} partidos (>= {SPLIT_DATE})")

    if len(df_train) < 500 or len(df_test) < 50:
        print("[ERR] Datos insuficientes.")
        return 1

    print("\nEntrenando Ridge dual...")
    model = BasketballScoreModel().fit(df_train)
    print(f"[OK] Entrenado con {model.trained_rows:,} filas.")

    joblib.dump(model, model_path)
    print(f"[OK] Modelo guardado: {model_path}")

    # Evaluacion
    pred = model.predict_score(df_test)
    df_test["expected_home"] = pred["expected_home"].values
    df_test["expected_away"] = pred["expected_away"].values

    err_home = (df_test["expected_home"] - df_test["home_score"]).abs().mean()
    err_away = (df_test["expected_away"] - df_test["away_score"]).abs().mean()
    err_total = ((df_test["expected_home"] + df_test["expected_away"]) - (df_test["home_score"] + df_test["away_score"])).abs().mean()
    err_spread = ((df_test["expected_home"] - df_test["expected_away"]) - (df_test["home_score"] - df_test["away_score"])).abs().mean()

    print()
    print("=" * 70)
    print(f"  EVALUACION EN TEST")
    print("=" * 70)
    print(f"  MAE home_score:    {err_home:6.2f}  (referencia: ~9-11 puntos)")
    print(f"  MAE away_score:    {err_away:6.2f}")
    print(f"  MAE total points:  {err_total:6.2f}  (referencia: ~14-18 puntos)")
    print(f"  MAE spread:        {err_spread:6.2f}  (referencia: ~10-12 puntos)")

    print()
    print(f"  Mean predicted home: {df_test['expected_home'].mean():.2f}  vs real: {df_test['home_score'].mean():.2f}")
    print(f"  Mean predicted away: {df_test['expected_away'].mean():.2f}  vs real: {df_test['away_score'].mean():.2f}")

    # Coeficientes
    print()
    print("  COEFICIENTES MODELO HOME:")
    for name, coef in zip(["intercept"] + model.home_features, [model.home_model.intercept_] + list(model.home_model.coef_)):
        print(f"    {name:<15} {coef:+.4f}")

    print()
    print("[OK] Paso 6.3 (Modelo Ridge dual NBA) completado.")
    print("     Siguiente: backtest_basketball.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
