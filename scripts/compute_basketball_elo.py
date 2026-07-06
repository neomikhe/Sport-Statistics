"""
Calcula Elo dinamico para todos los partidos de basketball_games en memoria
y muestra el top 10 actual de la NBA.

NOTA: el schema actual NO tiene tabla basketball_elo (a diferencia del fútbol).
Por simplicidad MVP, calculamos el Elo en memoria y solo lo mostramos.
Si quieres persistirlo, anyade la tabla basketball_elo al schema.

Uso:
    venv\\Scripts\\activate
    python scripts/compute_basketball_elo.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.basketball.elo import BasketballEloSystem  # noqa: E402


def main():
    engine = get_sqlalchemy_engine()

    print("Leyendo basketball_games...")
    df = pd.read_sql(
        """
        SELECT g.date, g.home_team_id, g.away_team_id,
               g.home_score, g.away_score,
               eh.name AS home_name, ea.name AS away_name
        FROM basketball_games g
        JOIN entities eh ON eh.id = g.home_team_id
        JOIN entities ea ON ea.id = g.away_team_id
        WHERE g.home_score IS NOT NULL AND g.away_score IS NOT NULL
        ORDER BY g.date
        """,
        engine,
        parse_dates=["date"],
    )

    if df.empty:
        print("[ERR] No hay partidos NBA en basketball_games.")
        print("      Ejecuta antes: python scripts/download_basketball_data.py")
        return 1

    print(f"Procesando {len(df):,} partidos NBA...")

    elo = BasketballEloSystem()

    def _date_to_nba_season(d):
        """Temporada NBA: si mes >= 10 (oct-dic) -> YYYY-YY+1; si no -> YYYY-1-YY."""
        if d.month >= 10:
            return f"{d.year}-{str(d.year + 1)[-2:]}"
        return f"{d.year - 1}-{str(d.year)[-2:]}"

    for _, r in df.iterrows():
        season = _date_to_nba_season(r["date"])
        elo.process_game(
            r["date"], season,
            int(r["home_team_id"]), int(r["away_team_id"]),
            int(r["home_score"]), int(r["away_score"]),
        )

    # Top 10 ratings actuales
    print()
    print("=" * 50)
    print("  TOP 10 EQUIPOS NBA POR ELO ACTUAL")
    print("=" * 50)

    # Get unique team names
    name_by_id = pd.concat([
        df[["home_team_id", "home_name"]].rename(columns={"home_team_id": "id", "home_name": "name"}),
        df[["away_team_id", "away_name"]].rename(columns={"away_team_id": "id", "away_name": "name"}),
    ]).drop_duplicates(subset="id")
    name_by_id = dict(zip(name_by_id["id"], name_by_id["name"]))

    rankings = sorted(
        [(tid, elo.get(tid)) for tid in name_by_id.keys()],
        key=lambda x: -x[1],
    )[:10]

    print(f"  {'#':<4}{'Equipo':<24}{'Elo':>8}")
    print(f"  {'-' * 4}{'-' * 24}{'-' * 8}")
    for i, (tid, e) in enumerate(rankings, 1):
        print(f"  {i:<4}{name_by_id[tid]:<24}{e:>8.1f}")

    print()
    print("[OK] Elo NBA calculado en memoria.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
