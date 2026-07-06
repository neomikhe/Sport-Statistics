"""
Calcula Elo por superficie para todos los partidos de tennis_matches y popula tennis_elo.

Procesa los partidos en orden cronologico:
  1. Para cada partido, obtiene Elo pre-partido (pre, por superficie) de ambos jugadores.
  2. Actualiza Elo segun el resultado.
  3. Guarda snapshots POST-partido en tennis_elo.

Idempotente: TRUNCATE + recompute.

Uso:
    venv\\Scripts\\activate
    python scripts/compute_tennis_elo.py
"""
import sys
from pathlib import Path

import pandas as pd
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection, get_sqlalchemy_engine  # noqa: E402
from sports.tennis.elo import TennisEloSystem, SURFACES  # noqa: E402


def main():
    engine = get_sqlalchemy_engine()
    print("Leyendo partidos de tenis...")
    df = pd.read_sql(
        """
        SELECT m.date, m.surface, m.player1_id, m.player2_id, m.winner_id
        FROM tennis_matches m
        WHERE m.surface IS NOT NULL AND m.winner_id IS NOT NULL
        ORDER BY m.date
        """,
        engine,
        parse_dates=["date"],
    )

    if df.empty:
        print("[ERR] No hay partidos en tennis_matches.")
        print("      Ejecuta antes: python scripts/ingest_tennis_data.py")
        return 1

    print(f"Procesando {len(df):,} partidos...")

    # Normalizar superficie a lowercase
    df["surface"] = df["surface"].str.lower().str.strip()
    df = df[df["surface"].isin(SURFACES)]
    print(f"Tras filtrar superficies validas: {len(df):,}")

    elo = TennisEloSystem()
    for _, r in df.iterrows():
        elo.process_match(
            r["date"], r["surface"],
            int(r["player1_id"]), int(r["player2_id"]),
            int(r["winner_id"]),
        )

    history = list(elo.history())
    print(f"Generados {len(history):,} snapshots Elo.")

    # Deduplicar (player_id, date, surface) — un jugador puede tener varios
    # partidos el mismo dia misma superficie (torneo). Conservar el ultimo.
    deduped = {}
    for player_id, match_date, surface, elo_val in history:
        deduped[(player_id, match_date, surface)] = (player_id, match_date, surface, elo_val)
    history_clean = list(deduped.values())
    print(f"Tras deduplicar (player, date, surface): {len(history_clean):,} snapshots.")

    # Volcar a tennis_elo
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE tennis_elo")
            execute_values(
                cur,
                """
                INSERT INTO tennis_elo (player_id, date, surface, elo)
                VALUES %s
                """,
                history_clean,
                page_size=2000,
            )
        conn.commit()
    finally:
        conn.close()

    # Top 10 por superficie
    engine = get_sqlalchemy_engine()
    print()
    for surface in SURFACES:
        rk = pd.read_sql(
            f"""
            WITH latest AS (
                SELECT player_id, MAX(date) AS max_date
                FROM tennis_elo
                WHERE surface = '{surface}'
                GROUP BY player_id
            )
            SELECT ent.name, ent.country, te.elo
            FROM tennis_elo te
            JOIN latest ON latest.player_id = te.player_id AND latest.max_date = te.date
            JOIN entities ent ON ent.id = te.player_id
            WHERE te.surface = '{surface}'
            ORDER BY te.elo DESC
            LIMIT 10
            """,
            engine,
        )
        if rk.empty:
            continue
        print("=" * 60)
        print(f"  TOP 10 ELO en {surface.upper()}")
        print("=" * 60)
        for i, r in rk.iterrows():
            print(f"  {i+1:<3}{r['name']:<30}{r['country'] or '':<5}{float(r['elo']):>8.1f}")
        print()

    print("[OK] Elo tenis calculado y guardado en tennis_elo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
