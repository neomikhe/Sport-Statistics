"""
Descarga los probable pitchers del dia desde MLB Stats API y los guarda en
mlb_starters.

Uso:
    venv\\Scripts\\activate
    python scripts/fetch_mlb_lineups.py                # hoy
    python scripts/fetch_mlb_lineups.py 2024-09-15     # fecha especifica
"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402
from sports.baseball.lineups import fetch_starters_for_date, store_to_db  # noqa: E402


def main():
    if len(sys.argv) > 1:
        try:
            target = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print("[ERR] Fecha debe ser YYYY-MM-DD")
            return 1
    else:
        target = date.today()

    print(f"Descargando probable pitchers MLB para {target}...")
    try:
        starters = fetch_starters_for_date(target)
    except Exception as e:
        print(f"[ERR] {type(e).__name__}: {e}")
        return 1

    if not starters:
        print(f"[INFO] Sin partidos programados para {target}.")
        return 0

    print(f"\nPartidos del dia: {len(starters)}")
    for s in starters:
        h = s["home_starter_name"] or "TBD"
        a = s["away_starter_name"] or "TBD"
        print(f"  {s['away_team']:<28} ({a:<25}) @ {s['home_team']:<28} ({h})")

    conn = get_pg_connection()
    try:
        n = store_to_db(starters, conn)
        print(f"\n[OK] {n} partidos guardados en mlb_starters.")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
