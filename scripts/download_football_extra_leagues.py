"""
Descarga ligas adicionales de football-data.co.uk en formato 'new'.

Estas ligas tienen un CSV unico por pais con multiples temporadas:
    https://www.football-data.co.uk/new/{COUNTRY}.csv

Cubre:
    MEX  - Liga MX (Mexico)
    USA  - MLS (Estados Unidos)
    BRA  - Brasileirao (Brasil)
    ARG  - Primera Division (Argentina)
    POL  - Ekstraklasa (Polonia)
    ROM  - Liga 1 (Rumania)
    SWE  - Allsvenskan (Suecia)
    NOR  - Eliteserien (Noruega)
    JPN  - J1 League (Japon)
    CHN  - Super League (China)

Formato CSV diferente al principal:
    Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PH,PD,PA,...

Ingesta a la misma tabla football_matches con `league` igual al nombre completo.

Uso:
    venv\\Scripts\\activate
    python scripts/download_football_extra_leagues.py
    python scripts/download_football_extra_leagues.py MEX USA  # solo Liga MX y MLS
"""
import sys
from pathlib import Path

import pandas as pd
import requests
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402
from sports.football.team_names import to_full as _team_full  # noqa: E402


BASE_URL = "https://www.football-data.co.uk/new"

EXTRA_LEAGUES = {
    "MEX": {"name": "Liga MX",          "country": "MEX"},
    "USA": {"name": "MLS",              "country": "USA"},
    "BRA": {"name": "Brasileirão",      "country": "BRA"},
    "ARG": {"name": "Primera Division", "country": "ARG"},
    "POL": {"name": "Ekstraklasa",      "country": "POL"},
    "ROM": {"name": "Liga 1 Romania",   "country": "ROU"},
    "SWE": {"name": "Allsvenskan",      "country": "SWE"},
    "NOR": {"name": "Eliteserien",      "country": "NOR"},
    "JPN": {"name": "J1 League",        "country": "JPN"},
    "CHN": {"name": "China Super",      "country": "CHN"},
}


def _get_sport_id(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM sports WHERE code = 'football'")
        return cur.fetchone()[0]


def _upsert_team(conn, sport_id: int, short_name: str, country: str) -> int:
    full = _team_full(short_name)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entities (sport_id, external_id, name, country)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (sport_id, external_id) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (sport_id, f"fd:{short_name}", full, country),
        )
        return cur.fetchone()[0]


def _safe_float(v):
    try:
        if pd.isna(v):
            return None
        f = float(v)
        return f if f > 1.0 else None
    except (ValueError, TypeError):
        return None


def _safe_int(v):
    try:
        if pd.isna(v):
            return None
        return int(v)
    except (ValueError, TypeError):
        return None


def download_country(country_code: str, conn, sport_id: int) -> int:
    if country_code not in EXTRA_LEAGUES:
        print(f"  [skip] {country_code}: no soportado")
        return 0

    info = EXTRA_LEAGUES[country_code]
    url = f"{BASE_URL}/{country_code}.csv"

    print(f"\n[{country_code} - {info['name']}]")
    try:
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            print(f"  [FAIL] HTTP {r.status_code}")
            return 0
    except requests.RequestException as e:
        print(f"  [FAIL] {type(e).__name__}: {e}")
        return 0

    output_dir = Path(__file__).resolve().parent.parent / "data" / "raw" / "football_extra"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / f"{country_code}.csv"
    raw_path.write_bytes(r.content)
    print(f"  [ok] descargado ({len(r.content) / 1024:.1f} KB)")

    df = pd.read_csv(raw_path, encoding="latin-1", on_bad_lines="skip")
    if "Date" not in df.columns or "Home" not in df.columns:
        print(f"  [WARN] columnas inesperadas: {df.columns.tolist()[:10]}")
        return 0

    df["date_parsed"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date_parsed", "Home", "Away"])

    # Upsert teams
    teams = set(df["Home"].dropna()) | set(df["Away"].dropna())
    team_map = {t: _upsert_team(conn, sport_id, t, info["country"]) for t in teams}
    conn.commit()

    rows = []
    for _, r in df.iterrows():
        ht, at = r["Home"], r["Away"]
        if ht not in team_map or at not in team_map:
            continue
        season_str = str(r.get("Season", "")).replace("/", "-")[:9]
        rows.append((
            r["date_parsed"].date(),
            info["name"],
            season_str,
            team_map[ht],
            team_map[at],
            _safe_int(r.get("HG")),
            _safe_int(r.get("AG")),
            None, None,  # xG no disponible
            _safe_float(r.get("PH")),
            _safe_float(r.get("PD")),
            _safe_float(r.get("PA")),
            _safe_float(r.get("PO>2.5")) or _safe_float(r.get("Avg>2.5")),
            _safe_float(r.get("PU<2.5")) or _safe_float(r.get("Avg<2.5")),
            "football-data.co.uk/new",
        ))

    if not rows:
        print(f"  [WARN] sin filas validas")
        return 0

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO football_matches
                (date, league, season, home_team_id, away_team_id,
                 home_goals, away_goals, home_xg, away_xg,
                 odds_home_close, odds_draw_close, odds_away_close,
                 odds_o25_close, odds_u25_close, source)
            VALUES %s
            ON CONFLICT (date, home_team_id, away_team_id) DO NOTHING
            """,
            rows,
        )
    conn.commit()
    print(f"  [ok] {len(rows)} partidos insertados")
    return len(rows)


def main():
    if len(sys.argv) > 1:
        countries = [c.upper() for c in sys.argv[1:]]
    else:
        countries = list(EXTRA_LEAGUES.keys())

    print(f"Descargando ligas extra: {countries}")

    conn = get_pg_connection()
    try:
        sport_id = _get_sport_id(conn)
        total = 0
        for c in countries:
            n = download_country(c, conn, sport_id)
            total += n

        print()
        print("=" * 60)
        print(f"  TOTAL: {total:,} partidos insertados en football_matches")
        print("=" * 60)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
