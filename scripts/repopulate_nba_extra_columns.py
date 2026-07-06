"""
Si las columnas extras de basketball_games quedaron NULL tras el download,
este script las repuebla SIN cleanup completo.

Estrategia:
  - Para cada temporada, llama a fetch_season_games() y obtiene el DataFrame
    completo con FGM/FGA/etc.
  - Por cada partido, hace UPDATE basketball_games SET home_fgm=..., away_fgm=...
    matching (date, home_team_id, away_team_id) via team_map.

Mas rapido que un cleanup + download completo si solo faltan las extras.

Uso:
    venv\\Scripts\\activate
    python scripts/repopulate_nba_extra_columns.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402
from sports.basketball.data_loader import fetch_season_games, _NBA_TEAM_IDS  # noqa: E402


SEASONS = ["2019-20", "2020-21", "2021-22", "2022-23",
           "2023-24", "2024-25", "2025-26"]


EXTRA_COLS = ["fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "tov", "ast"]


def _get_team_map(conn) -> dict:
    """Mapeo nba_api TEAM_ID externo -> entity_id local."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT external_id, id FROM entities
            WHERE sport_id = (SELECT id FROM sports WHERE code='basketball')
            """
        )
        rows = cur.fetchall()
    return {ext.replace("nba:", "", 1): tid for ext, tid in rows}


def _safe_int(v):
    try:
        if v is None or pd.isna(v):
            return None
        return int(v)
    except (ValueError, TypeError):
        return None


def update_season(conn, season: str, team_map: dict) -> int:
    print(f"\n[{season}] Descargando via nba_api...")
    df = fetch_season_games(season)
    if df.empty:
        print("  [skip] sin datos")
        return 0

    df["date"] = pd.to_datetime(df["date"])

    # Verificar que las columnas extra estan presentes
    missing = [f"home_{c}" for c in EXTRA_COLS if f"home_{c}" not in df.columns]
    if missing:
        print(f"  [WARN] Columnas faltantes en API: {missing}")
        print(f"  Columnas disponibles: {list(df.columns)}")
        return 0

    rows_updated = 0
    rows_skipped = 0

    set_clause = ", ".join(
        [f"home_{c} = %s" for c in EXTRA_COLS]
        + [f"away_{c} = %s" for c in EXTRA_COLS]
    )
    sql = f"""
        UPDATE basketball_games SET {set_clause}
        WHERE date = %s AND home_team_id = %s AND away_team_id = %s
    """

    with conn.cursor() as cur:
        for _, r in df.iterrows():
            home_id = team_map.get(str(r["home_ext_id"]))
            away_id = team_map.get(str(r["away_ext_id"]))
            if home_id is None or away_id is None:
                rows_skipped += 1
                continue

            params = (
                *[_safe_int(r.get(f"home_{c}")) for c in EXTRA_COLS],
                *[_safe_int(r.get(f"away_{c}")) for c in EXTRA_COLS],
                r["date"].date(), home_id, away_id,
            )
            cur.execute(sql, params)
            rows_updated += cur.rowcount
    conn.commit()

    print(f"  [ok] Filas actualizadas: {rows_updated}  |  Saltadas: {rows_skipped}")
    return rows_updated


def main():
    conn = get_pg_connection()
    try:
        team_map = _get_team_map(conn)
        print(f"Equipos NBA en BD: {len(team_map)}")

        if not team_map:
            print("[ERR] No hay equipos NBA. Ejecuta antes:")
            print("      python scripts/download_basketball_data.py")
            return 1

        total = 0
        for season in SEASONS:
            try:
                n = update_season(conn, season, team_map)
                total += n
            except Exception as e:
                print(f"  [FAIL] {type(e).__name__}: {e}")

        # Verificacion final
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE home_fga IS NOT NULL) AS notnull_count,
                    COUNT(*) AS total
                FROM basketball_games
                """
            )
            notnull, total_db = cur.fetchone()

        print()
        print("=" * 60)
        print(f"  TOTAL filas con home_fga POBLADO: {notnull:,} / {total_db:,}")
        print("=" * 60)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
