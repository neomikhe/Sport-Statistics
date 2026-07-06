"""
Construye features para el modelo NBA y los guarda en disco.

Lee:
    basketball_games (PostgreSQL) — populado por download_basketball_data.py

Genera:
    data/processed/basketball_features.csv

Imprime:
    - Resumen de cobertura
    - Sample de 5 partidos
    - Estadisticas descriptivas
    - Correlaciones con home_score y away_score

Uso:
    venv\\Scripts\\activate
    python scripts/build_basketball_features.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.basketball.features import build_features, FEATURE_COLS  # noqa: E402


def main():
    output_dir = Path(__file__).resolve().parent.parent / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "basketball_features.csv"

    print("Construyendo features NBA desde PostgreSQL...")
    engine = get_sqlalchemy_engine()
    df = build_features(engine)

    if df.empty:
        print("[ERR] basketball_games vacio. Ejecuta antes:")
        print("      python scripts/download_basketball_data.py")
        return 1

    total = len(df)
    complete_mask = df[FEATURE_COLS].notna().all(axis=1)
    complete = int(complete_mask.sum())

    print(f"[OK] Filas totales: {total:,}")
    print(f"     Con todas las features: {complete:,}  ({100.0 * complete / total:.1f} %)")

    df.to_csv(output_file, index=False)
    print(f"[OK] Guardado en: {output_file}")

    # Sample
    print()
    print("=" * 80)
    print("  SAMPLE: 5 PARTIDOS RECIENTES CON FEATURES")
    print("=" * 80)
    sample = df[complete_mask].sort_values("date").tail(5)
    for _, r in sample.iterrows():
        print(f"\n  {r['date'].date() if hasattr(r['date'], 'date') else r['date']}  "
              f"id={r['id']}  RESULTADO: {int(r['home_score'])}-{int(r['away_score'])}")
        print(f"    Elo H/A/diff: {r['home_elo']:7.1f} / {r['away_elo']:7.1f} ({r['elo_diff']:+7.1f})")
        print(f"    Pts 5/10 (H): {r['home_pts_5']:5.1f} / {r['home_pts_10']:5.1f}")
        print(f"    Pts 5/10 (A): {r['away_pts_5']:5.1f} / {r['away_pts_10']:5.1f}")
        print(f"    PA  5/10 (H): {r['home_pa_5']:5.1f} / {r['home_pa_10']:5.1f}")
        print(f"    PA  5/10 (A): {r['away_pa_5']:5.1f} / {r['away_pa_10']:5.1f}")
        print(f"    Rest (H/A) : {int(r['home_rest'])} / {int(r['away_rest'])} dias")

    # Stats
    print()
    print("=" * 80)
    print("  ESTADISTICAS DESCRIPTIVAS")
    print("=" * 80)
    stats = df[FEATURE_COLS].describe().T[["mean", "std", "min", "max"]].round(3)
    print(stats.to_string())

    # Correlations
    print()
    print("=" * 80)
    print("  CORRELACIONES CON home_score y away_score")
    print("=" * 80)
    corr = df[FEATURE_COLS + ["home_score", "away_score"]].corr()

    print()
    print("  Con home_score:")
    for name, val in corr["home_score"].loc[FEATURE_COLS].sort_values(ascending=False).items():
        print(f"    {name:<15} {val:+.3f}")

    print()
    print("  Con away_score:")
    for name, val in corr["away_score"].loc[FEATURE_COLS].sort_values(ascending=False).items():
        print(f"    {name:<15} {val:+.3f}")

    print()
    print("[OK] Paso 6.2 (Features baloncesto) completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
