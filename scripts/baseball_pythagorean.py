"""
Analisis Pythagorean (Bill James) calculado desde baseball_games (Retrosheet).

NO depende de Lahman: agregamos W/L/RS/RA directamente desde los partidos
ingestados por Retrosheet en PostgreSQL.

Pythagorean expectation:
    WinRate = RS^1.83 / (RS^1.83 + RA^1.83)

Equipos con (real - pyth) >> 0 fueron 'afortunados'; << 0, 'desafortunados'.

Uso:
    venv\\Scripts\\activate
    python scripts/baseball_pythagorean.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.baseball.models import pythagorean_expectation  # noqa: E402


def main():
    engine = get_sqlalchemy_engine()
    print("Leyendo baseball_games...")
    df = pd.read_sql(
        """
        SELECT g.date, g.home_team_id, g.away_team_id,
               g.home_runs, g.away_runs,
               eh.name AS home_team, ea.name AS away_team
        FROM baseball_games g
        JOIN entities eh ON eh.id = g.home_team_id
        JOIN entities ea ON ea.id = g.away_team_id
        WHERE g.home_runs IS NOT NULL AND g.away_runs IS NOT NULL
        """,
        engine,
        parse_dates=["date"],
    )

    if df.empty:
        print("[ERR] baseball_games vacio. Ejecuta antes:")
        print("      python scripts/download_retrosheet_data.py")
        return 1

    print(f"Partidos cargados: {len(df):,}")
    df["year"] = df["date"].dt.year

    # Agregar por (year, team) usando ambas perspectivas (home + away)
    home = df[["year", "home_team", "home_runs", "away_runs"]].rename(
        columns={"home_team": "team", "home_runs": "RS", "away_runs": "RA"}
    )
    away = df[["year", "away_team", "away_runs", "home_runs"]].rename(
        columns={"away_team": "team", "away_runs": "RS", "home_runs": "RA"}
    )
    combined = pd.concat([home, away], ignore_index=True)
    combined["W"] = (combined["RS"] > combined["RA"]).astype(int)
    combined["L"] = (combined["RS"] < combined["RA"]).astype(int)

    teams = combined.groupby(["year", "team"]).agg(
        W=("W", "sum"),
        L=("L", "sum"),
        RS=("RS", "sum"),
        RA=("RA", "sum"),
    ).reset_index()

    teams["pyth_winrate"] = teams.apply(
        lambda r: pythagorean_expectation(r["RS"], r["RA"]), axis=1
    )
    teams["actual_winrate"] = teams["W"] / (teams["W"] + teams["L"])
    teams["luck_delta"] = teams["actual_winrate"] - teams["pyth_winrate"]

    print(f"Team-seasons agregados: {len(teams):,}")

    # Top 15 por Pyth
    print()
    print("=" * 92)
    print("  TOP 15 EQUIPOS POR PYTH WINRATE")
    print("=" * 92)
    top = teams.sort_values("pyth_winrate", ascending=False).head(15)
    print(f"  {'year':<5}{'team':<8}{'W':>4}{'L':>4}{'RS':>5}{'RA':>5}{'pyth':>9}{'real':>9}{'luck':>9}")
    print(f"  {'-' * 5}{'-' * 8}{'-' * 4}{'-' * 4}{'-' * 5}{'-' * 5}{'-' * 9}{'-' * 9}{'-' * 9}")
    for _, r in top.iterrows():
        print(f"  {int(r['year']):<5}{r['team']:<8}{int(r['W']):>4}{int(r['L']):>4}"
              f"{int(r['RS']):>5}{int(r['RA']):>5}{r['pyth_winrate']:>9.3f}"
              f"{r['actual_winrate']:>9.3f}{r['luck_delta']:>+9.3f}")

    # Mas afortunados
    print()
    print("=" * 92)
    print("  10 EQUIPOS MAS AFORTUNADOS (real >> pyth)")
    print("=" * 92)
    luckiest = teams.sort_values("luck_delta", ascending=False).head(10)
    print(f"  {'year':<5}{'team':<8}{'pyth':>9}{'real':>9}{'luck':>9}")
    print(f"  {'-' * 5}{'-' * 8}{'-' * 9}{'-' * 9}{'-' * 9}")
    for _, r in luckiest.iterrows():
        print(f"  {int(r['year']):<5}{r['team']:<8}{r['pyth_winrate']:>9.3f}"
              f"{r['actual_winrate']:>9.3f}{r['luck_delta']:>+9.3f}")

    # Mas desafortunados
    print()
    print("=" * 92)
    print("  10 EQUIPOS MAS DESAFORTUNADOS (real << pyth)")
    print("=" * 92)
    unluckiest = teams.sort_values("luck_delta").head(10)
    print(f"  {'year':<5}{'team':<8}{'pyth':>9}{'real':>9}{'luck':>9}")
    print(f"  {'-' * 5}{'-' * 8}{'-' * 9}{'-' * 9}{'-' * 9}")
    for _, r in unluckiest.iterrows():
        print(f"  {int(r['year']):<5}{r['team']:<8}{r['pyth_winrate']:>9.3f}"
              f"{r['actual_winrate']:>9.3f}{r['luck_delta']:>+9.3f}")

    # Estadisticas
    mae = teams["luck_delta"].abs().mean()
    std = teams["luck_delta"].std()
    print()
    print("=" * 92)
    print("  ESTADISTICAS")
    print("=" * 92)
    print(f"  Error absoluto medio (|real - pyth|): {mae:.4f}")
    print(f"  Desviacion estandar: {std:.4f}")
    print(f"  Pythagorean predice winrate dentro de +-{std*2:.3f} ({std*200:.1f} %) el 95 % del tiempo")

    # Guardar
    output = Path(__file__).resolve().parent.parent / "data" / "processed" / "baseball_pythagorean.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    teams.to_csv(output, index=False)
    print()
    print(f"[OK] Guardado en: {output}")
    print()
    print("[OK] Paso 7.1 (Pythagorean baseball) completado.")
    print("     Datos desde Retrosheet (no Lahman, que tiene su repo caido).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
