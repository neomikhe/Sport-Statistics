import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.football.features import build_features, FEATURE_COLS  # noqa: E402


def main():
    output_dir = Path(__file__).resolve().parent.parent / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "football_features.csv"

    print("Construyendo features desde PostgreSQL...")
    engine = get_sqlalchemy_engine()
    df = build_features(engine)

    total = len(df)
    complete_mask = df[FEATURE_COLS].notna().all(axis=1)
    complete = int(complete_mask.sum())
    print(f"[OK] Filas totales:                {total:,}")
    print(f"     Con todas las features:      {complete:,}  ({100.0 * complete / total:.1f} %)")
    print(f"     Filas con NaN (primeros partidos de cada equipo): {total - complete:,}")

    df.to_csv(output_file, index=False)
    size_kb = output_file.stat().st_size / 1024
    print(f"[OK] Guardado en: {output_file}  ({size_kb:,.1f} KB)")

    print()
    print("=" * 72)
    print("  SANITY CHECKS")
    print("=" * 72)

    home_elo_min, home_elo_max = df["home_elo"].min(), df["home_elo"].max()
    away_elo_min, away_elo_max = df["away_elo"].min(), df["away_elo"].max()
    rest_min, rest_max = df["home_rest"].min(), df["home_rest"].max()

    print(f"  home_elo rango: [{home_elo_min:.1f}, {home_elo_max:.1f}]  (esperado ~[1300, 1900])")
    print(f"  away_elo rango: [{away_elo_min:.1f}, {away_elo_max:.1f}]")
    print(f"  rest_days rango: [{rest_min}, {rest_max}]  (esperado [1, 30])")

    n_neg_rest = int((df[["home_rest", "away_rest"]] < 1).any(axis=1).sum())
    print(f"  rest_days < 1 (bug si no es cero): {n_neg_rest}")

    print()
    print("=" * 72)
    print("  SAMPLE: 5 PARTIDOS MAS RECIENTES (con features completas)")
    print("=" * 72)
    sample = df[complete_mask].sort_values("date").tail(5)
    for _, r in sample.iterrows():
        res = f"{int(r['home_goals'])}-{int(r['away_goals'])}"
        print()
        print(f"  {r['date'].date()} | {r['league']:<16} | id={r['id']}  RESULTADO: {res}")
        print(f"    Elo H/A/diff : {r['home_elo']:7.1f}  {r['away_elo']:7.1f}  ({r['elo_diff']:+7.1f})")
        print(f"    GF 5/10  (H) : {r['home_gf_5']:5.2f}   {r['home_gf_10']:5.2f}")
        print(f"    GA 5/10  (H) : {r['home_ga_5']:5.2f}   {r['home_ga_10']:5.2f}")
        print(f"    GF 5/10  (A) : {r['away_gf_5']:5.2f}   {r['away_gf_10']:5.2f}")
        print(f"    GA 5/10  (A) : {r['away_ga_5']:5.2f}   {r['away_ga_10']:5.2f}")
        print(f"    Forma 5 H/A  : {int(r['home_form_5']):>2}pt   {int(r['away_form_5']):>2}pt")
        print(f"    Rest H/A     : {int(r['home_rest'])} dias  {int(r['away_rest'])} dias")

    print()
    print("=" * 72)
    print("  ESTADISTICAS DESCRIPTIVAS DE FEATURES")
    print("=" * 72)
    stats = df[FEATURE_COLS].describe().T[["mean", "std", "min", "max"]].round(3)
    print(stats.to_string())

    print()
    print("=" * 72)
    print("  CORRELACIONES CON TARGETS (sanity check)")
    print("=" * 72)
    corr_cols = FEATURE_COLS + ["home_goals", "away_goals"]
    corr = df[corr_cols].corr()

    print()
    print("  Correlacion con home_goals (ordenada):")
    ch = corr["home_goals"].loc[FEATURE_COLS].sort_values(ascending=False)
    for name, val in ch.items():
        marker = ""
        if name == "home_elo" and val < 0.05:
            marker = "  <- SOSPECHOSO (home_elo deberia correlar >0 con home_goals)"
        if name == "elo_diff" and val < 0.05:
            marker = "  <- SOSPECHOSO (elo_diff deberia correlar >0)"
        print(f"    {name:<15} {val:+.3f}{marker}")

    print()
    print("  Correlacion con away_goals (ordenada):")
    ca = corr["away_goals"].loc[FEATURE_COLS].sort_values(ascending=False)
    for name, val in ca.items():
        marker = ""
        if name == "away_elo" and val < 0.05:
            marker = "  <- SOSPECHOSO (away_elo deberia correlar >0 con away_goals)"
        print(f"    {name:<15} {val:+.3f}{marker}")

    print()
    print("=" * 72)
    print("  [OK] Paso 2.2 (Feature engineering) completado.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
