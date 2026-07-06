"""
Ingesta de los CSVs de Sackmann (data/raw/tennis/) a tennis_matches en PostgreSQL.

Procesa:
  - data/raw/tennis/atp_*.csv -> sport_id de tennis ATP
  - data/raw/tennis/wta_*.csv -> sport_id de tennis WTA

Mapea jugadores Sackmann (winner_id, loser_id) a entities con external_id
formato 'sack_atp:<id>' o 'sack_wta:<id>'.

Uso:
    venv\\Scripts\\activate
    python scripts/ingest_tennis_data.py
"""
import sys
from pathlib import Path

import pandas as pd
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402


def _get_tennis_sport_id(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM sports WHERE code = 'tennis'")
        return cur.fetchone()[0]


def _upsert_players(conn, sport_id: int, tour_prefix: str, df: pd.DataFrame) -> dict:
    """
    Inserta jugadores unicos de winner_id/loser_id como entities.
    Devuelve dict {sackmann_id -> entity_id}
    """
    rows = []
    seen = set()

    for _, r in df.iterrows():
        wid, wname = r.get("winner_id"), r.get("winner_name", "")
        lid, lname = r.get("loser_id"), r.get("loser_name", "")
        if pd.notna(wid) and wid not in seen:
            seen.add(int(wid))
            rows.append((sport_id, f"{tour_prefix}:{int(wid)}", str(wname),
                         (r.get("winner_ioc") or "")[:3]))
        if pd.notna(lid) and lid not in seen:
            seen.add(int(lid))
            rows.append((sport_id, f"{tour_prefix}:{int(lid)}", str(lname),
                         (r.get("loser_ioc") or "")[:3]))

    if not rows:
        return {}

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO entities (sport_id, external_id, name, country)
            VALUES %s
            ON CONFLICT (sport_id, external_id) DO UPDATE SET name = EXCLUDED.name
            """,
            rows,
        )
    conn.commit()

    # Releer ids
    ext_ids = [r[1] for r in rows]
    with conn.cursor() as cur:
        cur.execute(
            "SELECT external_id, id FROM entities WHERE sport_id = %s AND external_id = ANY(%s)",
            (sport_id, ext_ids),
        )
        ext_to_id = dict(cur.fetchall())

    return {
        int(ext.split(":")[1]): tid
        for ext, tid in ext_to_id.items()
    }


def _ingest_csv(conn, csv_path: Path, tour_prefix: str, sport_id: int) -> int:
    df = pd.read_csv(csv_path)
    df["tourney_date"] = pd.to_datetime(df["tourney_date"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["tourney_date", "winner_id", "loser_id"])
    if df.empty:
        return 0

    pmap = _upsert_players(conn, sport_id, tour_prefix, df)

    rows = []
    for _, r in df.iterrows():
        winner = pmap.get(int(r["winner_id"]))
        loser = pmap.get(int(r["loser_id"]))
        if winner is None or loser is None:
            continue

        # Asignacion DETERMINISTICA pero BALANCEADA: p1 = jugador con menor entity_id.
        # Asi en el dataset aproximadamente la mitad de partidos tiene p1=winner y la otra
        # mitad p1=loser, evitando sesgo de target en backtest/ML.
        if winner < loser:
            p1, p2 = winner, loser
            p1_aces, p1_df, p1_spw = r.get("w_ace"), r.get("w_df"), r.get("w_svpt")
            p2_aces, p2_df, p2_spw = r.get("l_ace"), r.get("l_df"), r.get("l_svpt")
        else:
            p1, p2 = loser, winner
            p1_aces, p1_df, p1_spw = r.get("l_ace"), r.get("l_df"), r.get("l_svpt")
            p2_aces, p2_df, p2_spw = r.get("w_ace"), r.get("w_df"), r.get("w_svpt")

        def _safe_int(v):
            return int(v) if pd.notna(v) else None

        rows.append((
            r["tourney_date"].date(),
            str(r.get("tourney_name", ""))[:100],
            str(r.get("surface", ""))[:10] if pd.notna(r.get("surface")) else None,
            str(r.get("round", ""))[:20] if pd.notna(r.get("round")) else None,
            int(r["best_of"]) if pd.notna(r.get("best_of")) else None,
            p1, p2,
            winner,  # winner_id real (independiente del orden p1/p2)
            str(r.get("score", ""))[:50] if pd.notna(r.get("score")) else None,
            _safe_int(p1_aces), _safe_int(p1_df), _safe_int(p1_spw),
            _safe_int(p2_aces), _safe_int(p2_df), _safe_int(p2_spw),
        ))

    if not rows:
        return 0

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO tennis_matches
                (date, tournament, surface, round, best_of,
                 player1_id, player2_id, winner_id, score,
                 p1_aces, p1_df, p1_spw,
                 p2_aces, p2_df, p2_spw)
            VALUES %s
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def main():
    raw_dir = Path(__file__).resolve().parent.parent / "data" / "raw" / "tennis"
    if not raw_dir.exists():
        print(f"[ERR] No existe {raw_dir}. Ejecuta antes: python scripts/download_tennis_data.py")
        return 1

    csv_files = sorted(raw_dir.glob("*.csv"))
    if not csv_files:
        print(f"[ERR] Sin CSVs en {raw_dir}")
        return 1

    conn = get_pg_connection()
    try:
        sport_id = _get_tennis_sport_id(conn)

        # Limpiar tabla antes (idempotente)
        print("Limpiando tennis_matches y entities tenis...")
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tennis_elo")
            cur.execute("DELETE FROM tennis_matches")
            cur.execute("DELETE FROM entities WHERE sport_id = %s", (sport_id,))
        conn.commit()

        total = 0
        for csv_path in csv_files:
            stem = csv_path.stem.lower()
            if stem.startswith("atp_"):
                tour = "sack_atp"
            elif stem.startswith("wta_"):
                tour = "sack_wta"
            else:
                print(f"  [skip] {csv_path.name}: no es atp_*/wta_*")
                continue
            try:
                n = _ingest_csv(conn, csv_path, tour, sport_id)
                print(f"  [ok] {csv_path.name}: {n} partidos")
                total += n
            except Exception as e:
                print(f"  [ERR] {csv_path.name}: {type(e).__name__}: {e}")
                conn.rollback()

        # Resumen
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tennis_matches")
            total_db = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM entities WHERE sport_id = %s", (sport_id,))
            n_players = cur.fetchone()[0]

        print()
        print(f"[OK] Total partidos en tennis_matches: {total_db:,}")
        print(f"     Jugadores unicos: {n_players:,}")
    finally:
        conn.close()

    print()
    print("[OK] Ingesta tenis completada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
