"""
Calcula Elo dinamico MLB desde baseball_games (populado por Retrosheet).

Imprime el top 10 actual de equipos MLB por Elo.

Uso:
    venv\\Scripts\\activate
    python scripts/compute_baseball_elo.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.baseball.elo import BaseballEloSystem  # noqa: E402


def _date_to_mlb_season(d) -> str:
    """Temporada MLB = anio del partido (mayoria son abril-octubre)."""
    return str(d.year)


def main():
    engine = get_sqlalchemy_engine()
    print("Leyendo baseball_games...")
    df = pd.read_sql(
        """
        SELECT g.date, g.home_team_id, g.away_team_id, g.home_runs, g.away_runs,
               eh.name AS home_name, ea.name AS away_name
        FROM baseball_games g
        JOIN entities eh ON eh.id = g.home_team_id
        JOIN entities ea ON ea.id = g.away_team_id
        WHERE g.home_runs IS NOT NULL AND g.away_runs IS NOT NULL
        ORDER BY g.date
        """,
        engine,
        parse_dates=["date"],
    )

    if df.empty:
        print("[ERR] No hay partidos MLB en baseball_games.")
        print("      Ejecuta antes: python scripts/download_retrosheet_data.py")
        return 1

    print(f"Procesando {len(df):,} partidos MLB...")

    elo = BaseballEloSystem()
    for _, r in df.iterrows():
        elo.process_game(
            r["date"], _date_to_mlb_season(r["date"]),
            int(r["home_team_id"]), int(r["away_team_id"]),
            int(r["home_runs"]), int(r["away_runs"]),
        )

    name_by_id = pd.concat([
        df[["home_team_id", "home_name"]].rename(columns={"home_team_id": "id", "home_name": "name"}),
        df[["away_team_id", "away_name"]].rename(columns={"away_team_id": "id", "away_name": "name"}),
    ]).drop_duplicates(subset="id")
    name_by_id = dict(zip(name_by_id["id"], name_by_id["name"]))

    rankings = sorted(
        [(tid, elo.get(tid)) for tid in name_by_id.keys()],
        key=lambda x: -x[1],
    )

    print()
    print("=" * 50)
    print("  TOP 10 EQUIPOS MLB POR ELO ACTUAL")
    print("=" * 50)
    print(f"  {'#':<4}{'Equipo':<10}{'Elo':>8}")
    for i, (tid, e) in enumerate(rankings[:10], 1):
        print(f"  {i:<4}{name_by_id[tid]:<10}{e:>8.1f}")

    print()
    print("=" * 50)
    print("  BOTTOM 5 (peores Elos)")
    print("=" * 50)
    for i, (tid, e) in enumerate(rankings[-5:], 1):
        print(f"  {len(rankings) - 5 + i:<4}{name_by_id[tid]:<10}{e:>8.1f}")

    print()
    print("[OK] Elo MLB calculado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
