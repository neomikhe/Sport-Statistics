"""
Debug: verifica si basketball_games tiene las columnas extendidas pobladas.

Reporta:
  - Total partidos en BD
  - Cuantos tienen home_fga NULL vs no-NULL
  - Si TODOS son NULL: inspecciona la salida de fetch_season_games para ver
    que columnas devuelve nba_api.

Uso:
    venv\\Scripts\\activate
    python scripts/debug_nba_columns.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection, get_sqlalchemy_engine  # noqa: E402


def check_db():
    engine = get_sqlalchemy_engine()
    df = pd.read_sql(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE home_fga IS NULL) AS null_fga,
            COUNT(*) FILTER (WHERE home_fga IS NOT NULL) AS notnull_fga,
            COUNT(*) FILTER (WHERE home_oreb IS NOT NULL) AS notnull_oreb,
            MIN(home_fga) AS min_fga,
            MAX(home_fga) AS max_fga
        FROM basketball_games
        """,
        engine,
    )
    print("=" * 60)
    print("  ESTADO basketball_games en BD")
    print("=" * 60)
    print(df.to_string(index=False))
    return df.iloc[0]


def inspect_fetch():
    print()
    print("=" * 60)
    print("  Inspeccionando fetch_season_games('2024-25')")
    print("=" * 60)
    from sports.basketball.data_loader import fetch_season_games

    df = fetch_season_games("2024-25")
    print(f"  Filas devueltas: {len(df):,}")
    print(f"  Columnas devueltas:")
    for col in df.columns:
        print(f"    - {col}")

    if not df.empty:
        first = df.iloc[0]
        print()
        print(f"  Primera fila (sample de campos clave):")
        for key in ["date", "home_abbr", "home_name", "home_score", "away_score",
                    "home_fgm", "home_fga", "home_oreb", "away_fgm", "away_fga"]:
            val = first.get(key, "<MISSING>")
            print(f"    {key:<15} = {val}")


def main():
    state = check_db()
    print()

    if state["notnull_fga"] == 0 and state["total"] > 0:
        print("[DIAGNOSIS] TODOS los partidos tienen home_fga NULL.")
        print("            La ingesta NO esta poblando las columnas extra.")
        print("            Voy a inspeccionar que devuelve la API:")
        try:
            inspect_fetch()
        except Exception as e:
            print(f"[ERR] {type(e).__name__}: {e}")
            return 1

        print()
        print("=" * 60)
        print("  PROXIMO PASO")
        print("=" * 60)
        print("  Si las columnas 'home_fgm', 'home_fga', etc. aparecen arriba")
        print("  con valores numericos, el problema es que la BD tenia datos")
        print("  viejos con ON CONFLICT DO NOTHING -> reinserta sin sobrescribir.")
        print("  Solucion:")
        print("      python scripts/cleanup_basketball_data.py")
        print("      python scripts/download_basketball_data.py")
        print()
        print("  Si NO aparecen, hay un bug real. Pegame el output.")
    elif state["notnull_fga"] > 0:
        print("[OK] Columnas extra estan pobladas.")
        print(f"     {state['notnull_fga']} partidos con home_fga, rango [{state['min_fga']}, {state['max_fga']}]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
