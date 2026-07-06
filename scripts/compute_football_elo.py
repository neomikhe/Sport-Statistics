"""
Calcula Elo dinamico para todos los partidos historicos y popula football_elo.

Procesa partidos en orden cronologico (por date, luego por id para desempate).
Para cada partido:
  1. Aplica regresion de temporada si el equipo cambia de temporada.
  2. Actualiza Elo de ambos equipos.
  3. Guarda snapshot POST-partido en football_elo.

Es idempotente: primero TRUNCA football_elo y luego recalcula desde cero.

Uso:
    venv\\Scripts\\activate
    python scripts/compute_football_elo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from psycopg2.extras import execute_values  # noqa: E402

from core.database.connection import get_pg_connection  # noqa: E402
from sports.football.elo import EloSystem  # noqa: E402


def main():
    conn = get_pg_connection()
    try:
        # 1. Leer todos los partidos jugados en orden cronologico
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT date, season, home_team_id, away_team_id,
                       home_goals, away_goals
                FROM football_matches
                WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
                ORDER BY date, id
                """
            )
            matches = cur.fetchall()

        if not matches:
            print("[ERR] No hay partidos jugados en la BD. Ejecuta primero ingest_football_history.py")
            return 1

        print(f"Procesando {len(matches):,} partidos historicos...")

        # 2. Procesar
        elo = EloSystem()
        for d, season, home_id, away_id, hg, ag in matches:
            elo.process_match(d, season, home_id, away_id, hg, ag)

        history = list(elo.history())
        print(f"Generados {len(history):,} snapshots de Elo.")

        # 3. Limpiar y volcar
        with conn.cursor() as cur:
            cur.execute("TRUNCATE football_elo")
            execute_values(
                cur,
                """
                INSERT INTO football_elo (team_id, date, elo)
                VALUES %s
                ON CONFLICT (team_id, date) DO UPDATE SET elo = EXCLUDED.elo
                """,
                history,
                page_size=2000,
            )
        conn.commit()
        print("[OK] football_elo actualizada.")

        # 4. Mostrar top 20 equipos por Elo actual
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH latest AS (
                    SELECT team_id, MAX(date) AS max_date
                    FROM football_elo
                    GROUP BY team_id
                )
                SELECT ent.name, ent.country, fe.elo, fe.date
                FROM football_elo fe
                JOIN latest ON latest.team_id = fe.team_id AND latest.max_date = fe.date
                JOIN entities ent ON ent.id = fe.team_id
                ORDER BY fe.elo DESC
                LIMIT 20
                """
            )
            rows = cur.fetchall()

        print()
        print("=" * 68)
        print("  TOP 20 EQUIPOS POR ELO (ultimo valor registrado)")
        print("=" * 68)
        print(f"  {'#':<4}{'Equipo':<26}{'Pais':<6}{'Elo':>8}   {'Ultima fecha'}")
        print(f"  {'-' * 4}{'-' * 26}{'-' * 6}{'-' * 8}   {'-' * 12}")
        for i, (name, country, elo_val, d) in enumerate(rows, 1):
            print(f"  {i:<4}{name:<26}{(country or ''):<6}{float(elo_val):>8.1f}   {d}")

    finally:
        conn.close()

    print()
    print("[OK] Paso 2.1 (Elo dinamico) completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
