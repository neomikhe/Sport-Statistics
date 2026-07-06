"""
Backtest walk-forward temporal del modelo de futbol.

Para cada temporada i >= 4 en el dataset:
    Train: temporadas [0..i-1]
    Test:  temporada i
    Metricas: log-loss, Brier, accuracy
    Compara con: modelo naive (media historica 1X2) y mercado (cuotas Pinnacle).

Ademas evalua la calibracion isotonica sobre un fold interno del ultimo train.

Uso:
    venv\\Scripts\\activate
    python scripts/backtest_football.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluation.backtesting import walk_forward_backtest  # noqa: E402
from core.evaluation.metrics import (  # noqa: E402
    log_loss_multiclass,
    brier_score_multiclass,
    accuracy,
)
from core.calibration.isotonic import IsotonicCalibrator3way  # noqa: E402


def main():
    root = Path(__file__).resolve().parent.parent
    features_path = root / "data" / "processed" / "football_features.csv"
    output_path = root / "data" / "processed" / "football_backtest_predictions.csv"

    if not features_path.exists():
        print("[ERR] No existe football_features.csv")
        print("      Ejecuta: python scripts/build_football_features.py")
        return 1

    print("Cargando features...")
    df = pd.read_csv(features_path, parse_dates=["date"])
    df = df[df["season"] < "2025-2026"].copy()
    print(f"Filas (excluyendo temporada actual 2025-2026): {len(df):,}")

    print("\nEjecutando walk-forward backtest (puede tardar 1-3 min)...")
    per_season, all_preds = walk_forward_backtest(df, min_train_seasons=4)

    if per_season.empty:
        print("[ERR] Backtest sin resultados.")
        return 1

    all_preds.to_csv(output_path, index=False)
    print(f"\n[OK] Predicciones guardadas en: {output_path}")
    print(f"     {len(all_preds):,} predicciones totales")

    # ---------- Tabla por temporada ----------
    print()
    print("=" * 110)
    print("  METRICAS POR TEMPORADA")
    print("=" * 110)
    cols = [
        "season", "n_test",
        "ll_model", "ll_naive", "ll_market",
        "br_model", "br_naive",
        "acc_model", "acc_naive", "acc_market",
    ]
    print(per_season[cols].round(4).to_string(index=False))

    # ---------- Agregados ponderados ----------
    print()
    print("=" * 110)
    print("  AGREGADO GLOBAL (promedio ponderado por n_test)")
    print("=" * 110)

    def wavg(col):
        mask = per_season[col].notna()
        if mask.sum() == 0:
            return float("nan")
        return float(np.average(per_season.loc[mask, col],
                                weights=per_season.loc[mask, "n_test"]))

    ll_m = wavg("ll_model")
    ll_n = wavg("ll_naive")
    ll_mk = wavg("ll_market")
    ll_mvsmk = wavg("ll_model_vs_market")

    br_m = wavg("br_model")
    br_n = wavg("br_naive")

    ac_m = wavg("acc_model")
    ac_n = wavg("acc_naive")
    ac_mk = wavg("acc_market")

    print(f"  log-loss modelo:  {ll_m:.4f}")
    print(f"  log-loss naive:   {ll_n:.4f}")
    if not np.isnan(ll_n) and ll_n > 0:
        print(f"     mejora vs naive: {(ll_n - ll_m) / ll_n * 100:+.2f} %")
    if not np.isnan(ll_mk):
        print(f"  log-loss mercado: {ll_mk:.4f}  (sobre partidos con cuota)")
        print(f"  log-loss modelo (mismo subset): {ll_mvsmk:.4f}")
        gap = ll_mvsmk - ll_mk
        print(f"     gap modelo vs mercado: {gap:+.4f}   (mas negativo = modelo mejor que mercado)")
    print()
    print(f"  Brier modelo:     {br_m:.4f}")
    print(f"  Brier naive:      {br_n:.4f}")
    print()
    print(f"  Accuracy modelo:  {ac_m * 100:.2f} %")
    print(f"  Accuracy naive:   {ac_n * 100:.2f} %")
    if not np.isnan(ac_mk):
        print(f"  Accuracy mercado: {ac_mk * 100:.2f} %")

    # ---------- Calibracion isotonica ----------
    print()
    print("=" * 110)
    print("  EFECTO DE LA CALIBRACION ISOTONICA")
    print("=" * 110)
    print("  Split interno: primera mitad del backtest -> calibrador, segunda -> test.")
    mid = len(all_preds) // 2
    val = all_preds.iloc[:mid]
    tst = all_preds.iloc[mid:]

    val_probs = val[["prob_home", "prob_draw", "prob_away"]].values
    val_out = val["outcome"].values
    tst_probs = tst[["prob_home", "prob_draw", "prob_away"]].values
    tst_out = tst["outcome"].values

    cal = IsotonicCalibrator3way().fit(val_probs, val_out)
    tst_probs_cal = cal.transform(tst_probs)

    ll_raw = log_loss_multiclass(tst_probs, tst_out)
    ll_cal = log_loss_multiclass(tst_probs_cal, tst_out)
    br_raw = brier_score_multiclass(tst_probs, tst_out)
    br_cal = brier_score_multiclass(tst_probs_cal, tst_out)

    print(f"  log-loss sin calibrar: {ll_raw:.4f}")
    print(f"  log-loss calibrada:    {ll_cal:.4f}   (mejora: {(ll_raw - ll_cal):+.4f})")
    print(f"  Brier sin calibrar:    {br_raw:.4f}")
    print(f"  Brier calibrada:       {br_cal:.4f}   (mejora: {(br_raw - br_cal):+.4f})")

    # ---------- Checkpoint critico ----------
    print()
    print("=" * 110)
    print("  CHECKPOINT CRITICO")
    print("=" * 110)
    if ll_m < ll_n:
        pct = (ll_n - ll_m) / ll_n * 100
        print(f"  [OK] log-loss modelo ({ll_m:.4f}) < log-loss naive ({ll_n:.4f})")
        print(f"       Mejora de {pct:.2f} %. El modelo tiene senal real. LUZ VERDE.")
    else:
        print(f"  [FAIL] log-loss modelo ({ll_m:.4f}) >= log-loss naive ({ll_n:.4f})")
        print(f"         El modelo NO aporta valor. ACCION: revisar features.")

    if not np.isnan(ll_mk) and not np.isnan(ll_mvsmk):
        if ll_mvsmk < ll_mk:
            print(f"  [!!] Modelo bate al mercado. Verifica que no haya data leakage.")
        else:
            gap = ll_mvsmk - ll_mk
            print(f"  Gap mercado: {gap:+.4f}  (tipico 0.01-0.05 para modelo casero razonable)")

    print()
    print("[OK] Paso 2.5 (Backtest + metricas) completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
