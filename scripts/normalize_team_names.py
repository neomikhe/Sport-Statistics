"""
Actualiza nombres de equipos en `entities` para usar nombres completos.

Aplicable a futbol y beisbol. Para NBA hay que re-ingerir (los nombres se
extraen ahora de TEAM_NAME en lugar de TEAM_ABBREVIATION).

NO re-descarga datos: solo actualiza la columna `name` de la tabla entities.

Uso:
    venv\\Scripts\\activate
    python scripts/normalize_team_names.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402
from sports.football.team_names import FULL_NAMES as FOOTBALL_FULL_NAMES  # noqa: E402
from sports.baseball.team_names import RETROSHEET_TO_FULL  # noqa: E402


def normalize_football(conn) -> int:
    """Actualiza nombres de equipos de futbol usando short -> full mapping."""
    n_updated = 0
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM sports WHERE code = 'football'")
        sport_id = cur.fetchone()[0]
        cur.execute(
            "SELECT id, external_id, name FROM entities WHERE sport_id = %s",
            (sport_id,),
        )
        rows = cur.fetchall()

    print(f"\n[FOOTBALL] {len(rows)} entidades en BD")
    for entity_id, external_id, current_name in rows:
        # external_id es 'fd:<short_name>'. Extraemos el short.
        if external_id and external_id.startswith("fd:"):
            short = external_id[3:]
            full = FOOTBALL_FULL_NAMES.get(short, short)
            if full != current_name:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE entities SET name = %s WHERE id = %s",
                        (full, entity_id),
                    )
                n_updated += 1
    conn.commit()
    print(f"  Nombres actualizados: {n_updated}")
    return n_updated


def normalize_baseball(conn) -> int:
    """Actualiza nombres de equipos MLB de codigos Retrosheet a nombres completos."""
    n_updated = 0
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM sports WHERE code = 'baseball'")
        sport_id = cur.fetchone()[0]
        cur.execute(
            "SELECT id, external_id, name FROM entities WHERE sport_id = %s",
            (sport_id,),
        )
        rows = cur.fetchall()

    print(f"\n[BASEBALL] {len(rows)} entidades en BD")
    for entity_id, external_id, current_name in rows:
        if external_id and external_id.startswith("retro:"):
            code = external_id[6:]
            full = RETROSHEET_TO_FULL.get(code, code)
            if full != current_name:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE entities SET name = %s WHERE id = %s",
                        (full, entity_id),
                    )
                n_updated += 1
    conn.commit()
    print(f"  Nombres actualizados: {n_updated}")
    return n_updated


def main():
    conn = get_pg_connection()
    try:
        f = normalize_football(conn)
        b = normalize_baseball(conn)
        print()
        print("=" * 60)
        print(f"  TOTAL: {f + b} nombres actualizados a forma completa")
        print("=" * 60)
        print()
        print("Para NBA: ejecuta cleanup_basketball + download_basketball.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
