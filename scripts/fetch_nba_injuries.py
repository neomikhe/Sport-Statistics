"""
Descarga el injury report NBA actual desde basketball-reference y lo guarda
en la tabla nba_injuries.

Uso:
    venv\\Scripts\\activate
    python scripts/fetch_nba_injuries.py

Idealmente ejecutado en una tarea programada cada 6 horas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402
from sports.basketball.injuries import fetch_injury_report, store_to_db  # noqa: E402


def main():
    print("Descargando NBA injury report (multi-source: BBR + ESPN fallback)...")
    try:
        df = fetch_injury_report()
    except Exception as e:
        print(f"[ERR] {type(e).__name__}: {e}")
        return 1

    if df.empty:
        print("[ERR] Ambas fuentes (BBR + ESPN) fallaron o devolvieron tabla vacia.")
        print("      Si BBR sigue dando 403, podemos anadir tercera fuente.")
        return 1

    source = df["source"].iloc[0] if "source" in df.columns else "?"
    print(f"  Fuente: {source}")
    print(f"  Lesiones reportadas: {len(df)}")

    # Resumen por status
    status_counts = df["status"].value_counts()
    print("\nDistribucion por status:")
    for status, count in status_counts.items():
        print(f"  {status:<20} {count}")

    # Top equipos con mas lesiones
    team_counts = df["team_name"].value_counts().head(10)
    print("\nTop 10 equipos con mas lesionados:")
    for team, count in team_counts.items():
        print(f"  {team:<25} {count}")

    # Guardar
    conn = get_pg_connection()
    try:
        n = store_to_db(df, conn)
        print(f"\n[OK] {n} lesiones guardadas en nba_injuries.")

        # Total snapshots historicos
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM nba_injuries")
            total = cur.fetchone()[0]
        print(f"     Total registros historicos en BD: {total:,}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
