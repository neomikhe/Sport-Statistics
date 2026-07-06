"""
Test rapido de Four Factors NBA.

Busca un team NBA real (no usa team_id=1 que es de futbol) y calcula sus
Four Factors rolling de los ultimos 10 partidos.

Uso:
    venv\\Scripts\\activate
    python scripts/test_four_factors.py
    python scripts/test_four_factors.py "Boston Celtics"
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.basketball.four_factors import (  # noqa: E402
    compute_team_rolling_four_factors,
    four_factors_score,
)


def main():
    target_name = sys.argv[1] if len(sys.argv) > 1 else None
    engine = get_sqlalchemy_engine()

    teams = pd.read_sql(
        """
        SELECT id, name
        FROM entities
        WHERE sport_id = (SELECT id FROM sports WHERE code = 'basketball')
        ORDER BY name
        """,
        engine,
    )
    if teams.empty:
        print("[ERR] No hay equipos NBA en BD.")
        return 1

    print(f"Equipos NBA disponibles: {len(teams)}")

    if target_name:
        match = teams[teams["name"].str.lower() == target_name.lower()]
        if match.empty:
            # buscar parcial
            match = teams[teams["name"].str.contains(target_name, case=False)]
        if match.empty:
            print(f"[ERR] '{target_name}' no encontrado. Equipos disponibles:")
            for n in teams["name"]:
                print(f"  - {n}")
            return 1
        team = match.iloc[0]
    else:
        # Tomar Celtics, Lakers o el primero alfabetico
        for candidate in ("Boston Celtics", "Los Angeles Lakers", "Golden State Warriors"):
            match = teams[teams["name"] == candidate]
            if not match.empty:
                team = match.iloc[0]
                break
        else:
            team = teams.iloc[0]

    print(f"\nCalculando Four Factors para: {team['name']} (id={team['id']})")
    ff = compute_team_rolling_four_factors(engine, int(team["id"]), n_games=10)

    print("=" * 50)
    print(f"  FOUR FACTORS — {team['name']}")
    print("=" * 50)
    print(f"  eFG%   (Eff Field Goal):  {ff['efg']:.4f}   (~0.50 promedio liga)")
    print(f"  TOV%   (Turnover Rate):   {ff['tov_pct']:.4f}   (~0.13 promedio liga)")
    print(f"  ORB%   (Off Reb Rate):    {ff['orb_pct']:.4f}   (~0.25 promedio liga)")
    print(f"  FTR    (FT Rate):         {ff['ftr']:.4f}   (~0.25 promedio liga)")

    if ff["efg"] == 0.50 and ff["tov_pct"] == 0.14:
        print()
        print("  [WARN] Estos son los DEFAULTS. No hay datos rolling para este team.")
        print("        Probable causa: team sin suficientes partidos con FGA pobladas.")
        return 1

    # Tambien comparar contra otro team
    print()
    print("=" * 50)
    print("  COMPARACION vs media NBA")
    print("=" * 50)
    df_all = pd.read_sql(
        """
        SELECT
            AVG((home_fgm + 0.5 * home_fg3m)::float / NULLIF(home_fga, 0)) AS efg_h,
            AVG((away_fgm + 0.5 * away_fg3m)::float / NULLIF(away_fga, 0)) AS efg_a
        FROM basketball_games
        WHERE home_fga IS NOT NULL
        """,
        engine,
    )
    avg_efg = float((df_all["efg_h"].iloc[0] + df_all["efg_a"].iloc[0]) / 2)
    diff = ff["efg"] - avg_efg
    print(f"  Media liga eFG%:  {avg_efg:.4f}")
    print(f"  Diferencia:       {diff:+.4f}  ({team['name']} vs media)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
