"""
Backtest del modelo de tenis (Elo por superficie + Barnett-Clarke).

Para cada partido en tennis_matches, calcula la probabilidad de victoria de player1
usando dos enfoques:
    1. Elo logistic (1 / (1 + 10^((e2-e1)/400)))
    2. Barnett-Clarke a partir de SPW/RPW estimadas desde Elo

Mide accuracy y log-loss vs naive (50%).

Uso:
    venv\\Scripts\\activate
    python scripts/backtest_tennis.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.tennis.features import build_features, DEFAULT_ELO  # noqa: E402
from sports.tennis.elo import expected_score  # noqa: E402
from sports.tennis.barnett_clarke import (  # noqa: E402
    prob_win_match,
    estimate_serve_return_from_elo,
)


SURFACE_AVG_SPW = {
    "hard": 0.62,
    "clay": 0.59,
    "grass": 0.66,
    "carpet": 0.63,
}


def _log_loss_binary(probs, outcomes, eps=1e-15):
    p = np.clip(np.asarray(probs, dtype=float), eps, 1 - eps)
    y = np.asarray(outcomes, dtype=int)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def main():
    engine = get_sqlalchemy_engine()
    print("Construyendo features de tenis...")
    df = build_features(engine)

    if df.empty:
        print("[ERR] tennis_matches vacio. Ejecuta antes:")
        print("      python scripts/ingest_tennis_data.py")
        print("      python scripts/compute_tennis_elo.py")
        return 1

    print(f"Partidos con features: {len(df):,}")

    # Filtrar a partidos con Elo distinto del default (ie. con historia previa)
    df_eval = df[
        (df["p1_elo_surface"] != DEFAULT_ELO) | (df["p2_elo_surface"] != DEFAULT_ELO)
    ].copy()
    print(f"Tras filtrar partidos con historia Elo: {len(df_eval):,}")

    # Probabilidad via Elo logistico (superficie)
    df_eval["prob_elo"] = df_eval.apply(
        lambda r: expected_score(r["p1_elo_surface"], r["p2_elo_surface"]),
        axis=1,
    )

    # Probabilidad via Barnett-Clarke (estimar SPW/RPW desde Elo, simular partido)
    def _bc_prob(row):
        avg_spw = SURFACE_AVG_SPW.get(row["surface"], 0.62)
        ps, pr = estimate_serve_return_from_elo(
            row["p1_elo_surface"], row["p2_elo_surface"], surface_avg_spw=avg_spw,
        )
        bo = int(row["best_of"]) if pd.notna(row.get("best_of")) else 3
        return prob_win_match(ps, pr, best_of=bo)

    df_eval["prob_bc"] = df_eval.apply(_bc_prob, axis=1)
    df_eval["prob_naive"] = 0.5

    # Metricas
    y = df_eval["p1_won"].values

    pred_elo = (df_eval["prob_elo"] > 0.5).astype(int)
    pred_bc = (df_eval["prob_bc"] > 0.5).astype(int)
    pred_naive = np.zeros_like(y)  # naive predice player2 siempre

    acc_elo = float((pred_elo == y).mean())
    acc_bc = float((pred_bc == y).mean())
    acc_naive = float((pred_naive == y).mean())

    ll_elo = _log_loss_binary(df_eval["prob_elo"].values, y)
    ll_bc = _log_loss_binary(df_eval["prob_bc"].values, y)
    ll_naive = _log_loss_binary(df_eval["prob_naive"].values, y)

    print()
    print("=" * 70)
    print("  RESULTADOS DEL BACKTEST")
    print("=" * 70)
    print(f"  Partidos evaluados: {len(df_eval):,}")
    print()
    print(f"  Modelo               Accuracy    log-loss")
    print(f"  {'-' * 20}  {'-' * 8}    {'-' * 8}")
    print(f"  Elo logistico        {acc_elo*100:>6.2f} %   {ll_elo:>8.4f}")
    print(f"  Barnett-Clarke       {acc_bc*100:>6.2f} %   {ll_bc:>8.4f}")
    print(f"  Naive (50%)          {acc_naive*100:>6.2f} %   {ll_naive:>8.4f}")

    print()
    if acc_elo > acc_naive and ll_elo < ll_naive:
        print("  [OK] Modelo Elo bate al naive en accuracy y log-loss.")
    else:
        print("  [WARN] Modelo Elo no supera al naive consistentemente.")

    # Por superficie
    print()
    print("=" * 70)
    print("  ACCURACY POR SUPERFICIE (modelo Elo)")
    print("=" * 70)
    for surface in df_eval["surface"].dropna().unique():
        sub = df_eval[df_eval["surface"] == surface]
        if sub.empty:
            continue
        pred = (sub["prob_elo"] > 0.5).astype(int)
        acc = float((pred == sub["p1_won"].values).mean())
        print(f"  {surface:<8}  {len(sub):>6} partidos   accuracy: {acc*100:.2f} %")

    print()
    print("[OK] Backtest tenis completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
