"""
Limpieza de basketball_games y entities baloncesto.

Elimina TODOS los partidos NBA y entidades baloncesto. Tras esto, re-ejecuta:
    python scripts/download_basketball_data.py

Necesario para purgar la contaminacion previa (selecciones, exhibiciones).

Uso:
    venv\\Scripts\\activate
    python scripts/cleanup_basketball_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402


def main():
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM sports WHERE code = 'basketball'")
            sport_id = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM basketball_games")
            n_games = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM entities WHERE sport_id = %s", (sport_id,))
            n_entities = cur.fetchone()[0]

            print(f"Antes de limpiar:")
            print(f"  basketball_games: {n_games:,} filas")
            print(f"  entities (sport=basketball): {n_entities} filas")

            print()
            print("Eliminando basketball_games...")
            cur.execute("DELETE FROM basketball_games")

            print("Eliminando entities baloncesto...")
            cur.execute("DELETE FROM entities WHERE sport_id = %s", (sport_id,))

            cur.execute("SELECT COUNT(*) FROM basketball_games")
            n_games_after = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM entities WHERE sport_id = %s", (sport_id,))
            n_entities_after = cur.fetchone()[0]
        conn.commit()

        print()
        print(f"Despues de limpiar:")
        print(f"  basketball_games: {n_games_after}")
        print(f"  entities: {n_entities_after}")
        print()
        print("[OK] Limpieza completada. Ahora ejecuta:")
        print("     python scripts/download_basketball_data.py")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
