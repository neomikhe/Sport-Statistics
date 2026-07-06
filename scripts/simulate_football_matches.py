"""
Demuestra la simulacion Monte Carlo del modelo Poisson sobre partidos de test.

Para 10 partidos aleatorios de la temporada de test (2024-2025) con cuotas
Pinnacle de cierre:
  1. Calcula lambdas con el modelo GLM Poisson entrenado.
  2. Simula 10.000 partidos por evento (Poisson independiente).
  3. Extrae probabilidades 1X2, Over/Under 2.5, BTTS.
  4. Compara con el calculo analitico exacto (sanity check: MC converge).
  5. Compara con probabilidades implicitas de Pinnacle (sin margen).
  6. Muestra los 5 marcadores mas probables.
  7. Agrega al final: |MC - exacto| y |modelo - mercado| promedios.

Uso:
    venv\\Scripts\\activate
    python scripts/simulate_football_matches.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.football.simulation import (  # noqa: E402
    simulate_match,
    probabilities_from_sims,
    top_scorelines,
    exact_probabilities,
)


TEST_SEASON = "2024-2025"
N_SIMS = 10_000
SAMPLE_SIZE = 10
RANDOM_SEED = 42


def normalize_implied(odds_h, odds_d, odds_a):
    """Elimina el margen del bookmaker: devuelve probabilidades 1X2 sumando 1."""
    raw_h = 1.0 / float(odds_h)
    raw_d = 1.0 / float(odds_d)
    raw_a = 1.0 / float(odds_a)
    total = raw_h + raw_d + raw_a
    return raw_h / total, raw_d / total, raw_a / total


def main():
    root = Path(__file__).resolve().parent.parent
    features_path = root / "data" / "processed" / "football_features.csv"
    model_path = root / "data" / "models" / "football_poisson_v1.joblib"

    if not features_path.exists() or not model_path.exists():
        print("[ERR] Faltan archivos requeridos. Ejecuta primero:")
        print("      python scripts/build_football_features.py")
        print("      python scripts/train_football_model.py")
        return 1

    print("Cargando features y modelo...")
    df = pd.read_csv(features_path, parse_dates=["date"])
    model = joblib.load(model_path)

    # Nombres de equipos
    engine = get_sqlalchemy_engine()
    ent = pd.read_sql("SELECT id, name FROM entities WHERE sport_id = 1", engine)
    name_by_id = dict(zip(ent["id"].tolist(), ent["name"].tolist()))

    # Filtrar test con cuotas completas
    eligible = df[
        (df["season"] == TEST_SEASON)
        & df["odds_home_close"].notna()
        & df["odds_draw_close"].notna()
        & df["odds_away_close"].notna()
    ].copy()
    print(f"Partidos elegibles en {TEST_SEASON} con cuotas Pinnacle: {len(eligible):,}")

    if len(eligible) < SAMPLE_SIZE:
        print(f"[WARN] Menos de {SAMPLE_SIZE} partidos disponibles.")

    sample = eligible.sample(
        n=min(SAMPLE_SIZE, len(eligible)), random_state=RANDOM_SEED
    ).sort_values("date")

    # Lambdas
    pred = model.predict_lambda(sample)
    sample = sample.copy()
    sample["lambda_home"] = pred["lambda_home"].values
    sample["lambda_away"] = pred["lambda_away"].values

    # Agregados para comparacion final
    mc_vs_exact_l1 = []
    model_vs_market_l1 = []

    rng = np.random.default_rng(RANDOM_SEED)

    print()
    print(f"Simulando {N_SIMS:,} partidos por evento (seed={RANDOM_SEED})...")
    print()
    print("=" * 86)
    print(f"  {SAMPLE_SIZE} PARTIDOS DE TEST - MC vs EXACTO vs MERCADO")
    print("=" * 86)

    for _, r in sample.iterrows():
        home_name = name_by_id.get(r["home_team_id"], f"id={r['home_team_id']}")
        away_name = name_by_id.get(r["away_team_id"], f"id={r['away_team_id']}")

        lh = float(r["lambda_home"])
        la = float(r["lambda_away"])

        hg, ag = simulate_match(lh, la, n_sims=N_SIMS, rng=rng)
        mc = probabilities_from_sims(hg, ag)
        exact = exact_probabilities(lh, la)

        impl_h, impl_d, impl_a = normalize_implied(
            r["odds_home_close"], r["odds_draw_close"], r["odds_away_close"]
        )

        real = (
            f"{int(r['home_goals'])}-{int(r['away_goals'])}"
            if pd.notna(r["home_goals"]) and pd.notna(r["away_goals"])
            else "pending"
        )

        print()
        print(f"  {r['date'].date()} | {r['league']:<16} | {home_name} vs {away_name}")
        print(f"    Resultado real: {real}   |   lambdas H/A: {lh:.3f} / {la:.3f}")
        print(f"                     HOME   DRAW   AWAY    |   O>2.5   U<2.5    BTTS")
        print(f"    Monte Carlo:    {mc['prob_home']:.3f}  {mc['prob_draw']:.3f}  {mc['prob_away']:.3f}   |   "
              f"{mc['prob_over_2_5']:.3f}   {mc['prob_under_2_5']:.3f}   {mc['prob_btts']:.3f}")
        print(f"    Poisson exacto: {exact['prob_home']:.3f}  {exact['prob_draw']:.3f}  {exact['prob_away']:.3f}   |   "
              f"{exact['prob_over_2_5']:.3f}   {exact['prob_under_2_5']:.3f}   {exact['prob_btts']:.3f}")
        print(f"    Mercado (imp):  {impl_h:.3f}  {impl_d:.3f}  {impl_a:.3f}")

        mc_vs_exact_l1.append(
            abs(mc["prob_home"] - exact["prob_home"])
            + abs(mc["prob_draw"] - exact["prob_draw"])
            + abs(mc["prob_away"] - exact["prob_away"])
        )
        model_vs_market_l1.append(
            abs(exact["prob_home"] - impl_h)
            + abs(exact["prob_draw"] - impl_d)
            + abs(exact["prob_away"] - impl_a)
        )

        top = top_scorelines(hg, ag, n=5)
        top_str = "  ".join(f"{h}-{a}:{p:.3f}" for h, a, p in top)
        print(f"    Top marcadores: {top_str}")

    avg_mc_ex = float(np.mean(mc_vs_exact_l1))
    avg_model_market = float(np.mean(model_vs_market_l1))

    print()
    print("=" * 86)
    print("  RESUMEN AGREGADO")
    print("=" * 86)
    print(f"  |MC - Exacto| medio en 1X2 (L1):      {avg_mc_ex:.4f}")
    print(f"     Referencia: con {N_SIMS:,} sims debe ser <0.03. Mayor = bug.")
    print()
    print(f"  |Modelo - Mercado| medio en 1X2 (L1): {avg_model_market:.4f}")
    print(f"     Referencia tipica: 0.05 - 0.15. No tiene que ser cero.")
    print(f"     Lo que importa es batir al mercado en CLV, no igualarlo. Eso es Paso 2.5.")

    print()
    print("[OK] Paso 2.4 (Simulacion Monte Carlo) completado.")
    print("     Siguiente: Paso 2.5 (backtest walk-forward + log-loss vs naive).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
