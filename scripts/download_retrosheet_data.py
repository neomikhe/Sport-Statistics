import io
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402
from sports.baseball.team_names import to_full as _team_full  # noqa: E402


DEFAULT_YEARS = list(range(2018, 2025))
SPORT_CODE = "baseball"

COL_DATE = 0
COL_GAME_NUM = 1
COL_VISITING_TEAM = 3
COL_HOME_TEAM = 6
COL_VISITING_SCORE = 9
COL_HOME_SCORE = 10
COL_VISITING_HITS = 22
COL_VISITING_HR = 25
COL_VISITING_SO = 32
COL_HOME_HITS = 50
COL_HOME_HR = 53
COL_HOME_SO = 60


def _get_sport_id(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM sports WHERE code = %s", (SPORT_CODE,))
        return cur.fetchone()[0]


def _upsert_team(conn, sport_id: int, abbr: str) -> int:
    full_name = _team_full(abbr)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entities (sport_id, external_id, name, country)
            VALUES (%s, %s, %s, 'USA')
            ON CONFLICT (sport_id, external_id) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (sport_id, f"retro:{abbr}", full_name),
        )
        return cur.fetchone()[0]


def download_year(year: int) -> pd.DataFrame:
    url = f"https://www.retrosheet.org/gamelogs/gl{year}.zip"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        candidates = [n for n in z.namelist() if n.lower().endswith(".txt")]
        if not candidates:
            raise RuntimeError(f"ZIP de {year} sin .txt dentro")
        with z.open(candidates[0]) as f:
            df = pd.read_csv(f, header=None, dtype=str, encoding="latin-1")
    return df


def ingest_year(conn, sport_id: int, year: int) -> int:
    df = download_year(year)
    if df.empty:
        return 0

    if df.shape[1] < 11:
        return 0

    df["date_parsed"] = pd.to_datetime(df[COL_DATE], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["date_parsed"])
    df["v_score"] = pd.to_numeric(df[COL_VISITING_SCORE], errors="coerce")
    df["h_score"] = pd.to_numeric(df[COL_HOME_SCORE], errors="coerce")
    df = df.dropna(subset=["v_score", "h_score"])

    has_stats = df.shape[1] > COL_HOME_SO
    for col in (COL_VISITING_HITS, COL_VISITING_HR, COL_VISITING_SO,
                COL_HOME_HITS, COL_HOME_HR, COL_HOME_SO):
        df[f"n{col}"] = pd.to_numeric(df[col], errors="coerce") if has_stats else None

    teams_seen = set(df[COL_VISITING_TEAM].dropna().unique()) | set(df[COL_HOME_TEAM].dropna().unique())
    team_map = {abbr: _upsert_team(conn, sport_id, abbr) for abbr in teams_seen}
    conn.commit()

    def _si(v):
        return None if pd.isna(v) else int(v)

    rows = []
    for _, r in df.iterrows():
        h_team = r[COL_HOME_TEAM]
        v_team = r[COL_VISITING_TEAM]
        if pd.isna(h_team) or pd.isna(v_team):
            continue
        rows.append((
            r["date_parsed"].date(),
            team_map[h_team],
            team_map[v_team],
            None, None,
            int(r["h_score"]),
            int(r["v_score"]),
            _si(r[f"n{COL_HOME_HITS}"]), _si(r[f"n{COL_VISITING_HITS}"]),
            _si(r[f"n{COL_HOME_HR}"]),   _si(r[f"n{COL_VISITING_HR}"]),
            _si(r[f"n{COL_HOME_SO}"]),   _si(r[f"n{COL_VISITING_SO}"]),
            None,
            None,
        ))

    if not rows:
        return 0

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO baseball_games
                (date, home_team_id, away_team_id, home_sp_id, away_sp_id,
                 home_runs, away_runs,
                 home_hits, away_hits, home_hr, away_hr, home_so, away_so,
                 park_factor, weather)
            VALUES %s
            ON CONFLICT (date, home_team_id, away_team_id) DO UPDATE SET
                home_hits = COALESCE(EXCLUDED.home_hits, baseball_games.home_hits),
                away_hits = COALESCE(EXCLUDED.away_hits, baseball_games.away_hits),
                home_hr   = COALESCE(EXCLUDED.home_hr,   baseball_games.home_hr),
                away_hr   = COALESCE(EXCLUDED.away_hr,   baseball_games.away_hr),
                home_so   = COALESCE(EXCLUDED.home_so,   baseball_games.home_so),
                away_so   = COALESCE(EXCLUDED.away_so,   baseball_games.away_so)
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def main():
    if len(sys.argv) > 1:
        try:
            years = [int(y) for y in sys.argv[1:]]
        except ValueError:
            print("[ERR] Argumentos deben ser anios (ej.: 2020 2021).")
            return 1
    else:
        years = DEFAULT_YEARS

    print(f"Anios a descargar: {years}")
    print()

    conn = get_pg_connection()
    try:
        sport_id = _get_sport_id(conn)
        total = 0
        failed = 0
        for year in years:
            print(f"[{year}] descargando game log Retrosheet...")
            try:
                n = ingest_year(conn, sport_id, year)
                print(f"  [ok] {n:,} partidos insertados")
                total += n
            except Exception as e:
                print(f"  [FAIL] {type(e).__name__}: {e}")
                failed += 1
            time.sleep(0.5)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM baseball_games")
            db_total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM entities WHERE sport_id = %s", (sport_id,))
            n_teams = cur.fetchone()[0]

        print()
        print(f"[OK] Total partidos en baseball_games: {db_total:,}")
        print(f"     Equipos registrados: {n_teams}")
        if failed > 0:
            print(f"     [WARN] {failed} anios fallaron")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
