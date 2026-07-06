"""
Calibra el alpha optimo para mezclar probabilidades del modelo con cuotas Pinnacle.

Lee:
    data/processed/football_backtest_predictions.csv (modelo)
    Cuotas Pinnacle de las mismas filas (joining con football_matches)

Encuentra alpha que minimiza log-loss del blend modelo+mercado.

Uso:
    venv\\Scripts\\activate
    python scripts/calibrate_with_market.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from core.calibration.market_blend import (  # noqa: E402
    market_implied_probs_1x2, blend_probs, fit_alpha,
)
from core.evaluation.metrics import log_loss_multiclass  # noqa: E402


def main():
    root = Path(__file__).resolve().parent.parent
    preds_path = root / "data" / "processed" / "football_backtest_predictions.csv"

    if not preds_path.exists():
        print("[ERR] Falta football_backtest_predictions.csv")
        print("      Ejecuta antes: python scripts/backtest_football.py")
        return 1

    print("Cargando predicciones del backtest...")
    df = pd.read_csv(preds_path, parse_dates=["date"])

    # Filtrar a partidos con cuotas Pinnacle
    has_odds = (
        df["odds_home_close"].notna()
        & df["odds_draw_close"].notna()
        & df["odds_away_close"].notna()
    )
    df = df[has_odds].copy()
    print(f"  Filas con cuotas Pinnacle: {len(df):,}")

    if len(df) < 1000:
        print("[ERR] Pocas filas para calibracion confiable.")
        return 1

    # Probs del modelo
    model_probs = df[["prob_home", "prob_draw", "prob_away"]].values

    # Probs implicitas del mercado
    market_probs = market_implied_probs_1x2(
        df["odds_home_close"].values,
        df["odds_draw_close"].values,
        df["odds_away_close"].values,
    )

    outcomes = df["outcome"].values

    # Split val/test (50/50 cronologico)
    df = df.sort_values("date").reset_index(drop=True)
    mid = len(df) // 2
    val_idx = slice(0, mid)
    tst_idx = slice(mid, len(df))

    # Fit alpha en val
    alpha_opt, ll_val = fit_alpha(
        model_probs[val_idx], market_probs[val_idx], outcomes[val_idx], n_grid=21,
    )

    # Evaluar en test
    blended_test = blend_probs(model_probs[tst_idx], market_probs[tst_idx], alpha_opt)
    ll_blend_test = log_loss_multiclass(blended_test, outcomes[tst_idx])
    ll_model_test = log_loss_multiclass(model_probs[tst_idx], outcomes[tst_idx])
    ll_market_test = log_loss_multiclass(market_probs[tst_idx], outcomes[tst_idx])

    print()
    print("=" * 68)
    print(f"  RESULTADOS CALIBRACION BAYESIANA")
    print("=" * 68)
    print(f"  Alpha optimo (peso modelo, 1-alpha = peso mercado): {alpha_opt:.3f}")
    print()
    print(f"  Log-loss en VALIDACION:  {ll_val:.4f}")
    print()
    print(f"  Log-loss en TEST:")
    print(f"    Modelo solo:           {ll_model_test:.4f}")
    print(f"    Mercado solo:          {ll_market_test:.4f}")
    print(f"    Blended (alpha={alpha_opt:.2f}): {ll_blend_test:.4f}")

    # Mejora vs modelo solo
    mejora = (ll_model_test - ll_blend_test) / ll_model_test * 100
    print()
    if ll_blend_test < ll_model_test:
        print(f"  [OK] Blend mejora al modelo solo en {mejora:+.2f} %")
    else:
        print(f"  [WARN] Blend NO supera al modelo solo (mejora: {mejora:+.2f} %)")

    if ll_blend_test < ll_market_test:
        gap = (ll_market_test - ll_blend_test) / ll_market_test * 100
        print(f"  [OK] Blend mejora al mercado solo en {gap:+.2f} %")

    # Guardar alpha optimo
    out_dir = root / "data" / "models"
    out_dir.mkdir(parents=True, exist_ok=True)
    config_path = out_dir / "blend_alpha.txt"
    config_path.write_text(f"{alpha_opt:.6f}\n")
    print()
    print(f"  Alpha guardado en {config_path}")
    print(f"  Para aplicarlo a picks futuros: blend_probs(model, market, alpha={alpha_opt:.3f})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
