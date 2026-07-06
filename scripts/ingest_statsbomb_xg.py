"""
Descarga StatsBomb Open Data e ingiere xG en football_xg.

Por defecto procesa SOLO Champions League y Premier League (las que cubren mejor
nuestras ligas). Cada competition se procesa con todas sus temporadas.

Para anadir mas competiciones, ejecuta:
    python scripts/download_statsbomb_data.py
y mira el listado.

Uso:
    venv\\Scripts\\activate
    python scripts/ingest_statsbomb_xg.py            # default: Champions+PL
    python scripts/ingest_statsbomb_xg.py 16 4       # competition_id 16, season_id 4
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402
from sports.football.statsbomb_xg import (  # noqa: E402
    fetch_competitions, load_team_mapping, process_competition,
)


# (competition_id, season_id) por defecto
DEFAULT_TARGETS = [
    # Champions League 2015-16 (la mas completa de open-data hace tiempo)
    (16, 4),
    # Premier League 2015-16
    (2, 27),
]


def main():
    if len(sys.argv) > 2:
        try:
            targets = [(int(sys.argv[1]), int(sys.argv[2]))]
        except ValueError:
            print("[ERR] Argumentos: competition_id season_id")
            return 1
    else:
        targets = DEFAULT_TARGETS

    mapping = load_team_mapping()
    if not mapping:
        print("[ERR] team_mapping.json vacio. Edita data/raw/statsbomb/team_mapping.json")
        return 1
    print(f"Mapeo cargado: {len(mapping)} equipos StatsBomb -> football-data")

    print("Verificando competitions...")
    try:
        comps = fetch_competitions()
        print(f"  {len(comps)} competitions disponibles")
    except Exception as e:
        print(f"  [WARN] No se pudo verificar competitions: {e}")

    conn = get_pg_connection()
    try:
        total = 0
        for comp_id, season_id in targets:
            print(f"\n[{comp_id}/{season_id}] procesando...")
            try:
                n = process_competition(comp_id, season_id, mapping, conn)
                print(f"  [OK] {n} matches con xG insertados/actualizados")
                total += n
            except Exception as e:
                print(f"  [FAIL] {type(e).__name__}: {e}")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM football_xg")
            db_total = cur.fetchone()[0]

        print()
        print("=" * 60)
        print(f"  TOTAL xG en football_xg: {db_total:,}")
        print(f"  Insertados/actualizados ahora: {total}")
        print("=" * 60)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
