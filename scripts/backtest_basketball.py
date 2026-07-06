"""
Backtest walk-forward del modelo NBA, temporada por temporada.

Para cada temporada NBA con suficiente historial previo (>=2 temporadas):
    Train: todas las temporadas anteriores
    Test:  la temporada en cuestion
    Metricas: MAE de marcador, total, spread + accuracy de moneyline

Compara con baseline naive (siempre predice marcador medio histórico).

Uso:
    venv\\Scripts\\activate
    python scripts/backtest_basketball.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.basketball.models import (  # noqa: E402
    BasketballScoreModel,
    HOME_MODEL_FEATURES,
    AWAY_MODEL_FEATURES,
)


def _date_to_nba_season(d) -> str:
    if d.month >= 10:
        return f"{d.year}-{str(d.year + 1)[-2:]}"
    return f"{d.year - 1}-{str(d.year)[-2:]}"


def main():
    root = Path(__file__).resolve().parent.parent
    features_path = root / "data" / "processed" / "basketball_features.csv"

    if not features_path.exists():
        print("[ERR] Ejecuta antes: python scripts/build_basketball_features.py")
        return 1

    df = pd.read_csv(features_path, parse_dates=["date"])
    all_feats = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    df = df[df[all_feats].notna().all(axis=1)].copy()
    df["season"] = df["date"].apply(_date_to_nba_season)

    seasons = sorted(df["season"].unique())
    print(f"Temporadas detectadas: {seasons}")

    if len(seasons) < 3:
        print(f"[ERR] Necesito >=3 temporadas, hay {len(seasons)}.")
        return 1

    rows = []
    for i in range(2, len(seasons)):
        test_s = seasons[i]
        train_seasons = seasons[:i]

        df_train = df[df["season"].isin(train_seasons)]
        df_test = df[df["season"] == test_s]

        if len(df_train) < 500 or len(df_test) < 50:
            continue

        print(f"  [fold] train {train_seasons[0]}..{train_seasons[-1]} ({len(df_train):,})  ->  test {test_s} ({len(df_test):,})")

        model = BasketballScoreModel().fit(df_train)
        pred = model.predict_score(df_test)

        e_home = pred["expected_home"].values
        e_away = pred["expected_away"].values
        a_home = df_test["home_score"].values
        a_away = df_test["away_score"].values

        # Modelo
        mae_home = float(np.abs(e_home - a_home).mean())
        mae_away = float(np.abs(e_away - a_away).mean())
        mae_total = float(np.abs((e_home + e_away) - (a_home + a_away)).mean())
        mae_spread = float(np.abs((e_home - e_away) - (a_home - a_away)).mean())
        ml_acc = float(((e_home > e_away) == (a_home > a_away)).mean())

        # Naive: predice la media de train
        naive_home = float(df_train["home_score"].mean())
        naive_away = float(df_train["away_score"].mean())
        n_mae_home = float(np.abs(naive_home - a_home).mean())
        n_mae_away = float(np.abs(naive_away - a_away).mean())
        n_ml_acc = float((True == (a_home > a_away)).mean())  # naive siempre predice local

        rows.append({
            "season": test_s,
            "n_test": len(df_test),
            "mae_home": mae_home,
            "mae_away": mae_away,
            "mae_total": mae_total,
            "mae_spread": mae_spread,
            "ml_acc": ml_acc,
            "naive_mae_home": n_mae_home,
            "naive_mae_away": n_mae_away,
            "naive_ml_acc": n_ml_acc,
        })

    if not rows:
        print("[ERR] Backtest sin folds validos.")
        return 1

    df_res = pd.DataFrame(rows)
    print()
    print("=" * 100)
    print("  RESULTADOS POR TEMPORADA")
    print("=" * 100)
    print(df_res.round(3).to_string(index=False))

    # Agregado
    print()
    print("=" * 100)
    print("  AGREGADO PONDERADO")
    print("=" * 100)
    def w(col):
        return float(np.average(df_res[col], weights=df_res["n_test"]))

    print(f"  MAE home (modelo):  {w('mae_home'):.3f}   |  naive: {w('naive_mae_home'):.3f}")
    print(f"  MAE away (modelo):  {w('mae_away'):.3f}   |  naive: {w('naive_mae_away'):.3f}")
    print(f"  MAE total:          {w('mae_total'):.3f}")
    print(f"  MAE spread:         {w('mae_spread'):.3f}")
    print(f"  ML accuracy modelo: {w('ml_acc') * 100:.2f} %")
    print(f"  ML accuracy naive:  {w('naive_ml_acc') * 100:.2f} %")

    # Checkpoint
    print()
    if w("mae_home") < w("naive_mae_home") and w("ml_acc") > w("naive_ml_acc"):
        print("  [OK] Modelo NBA bate al naive en MAE y ML accuracy.")
    else:
        print("  [WARN] Modelo NBA no supera al naive consistentemente.")

    print()
    print("[OK] Paso 6.4 (Backtest baloncesto) completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
