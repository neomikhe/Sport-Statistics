"""
Parser e ingestor de CSVs de football-data.co.uk a la tabla football_matches.

Estructura esperada de archivos:
    data/raw/football/{LEAGUE}_{SEASON}.csv
        ej.: E0_2425.csv, SP1_1920.csv

Columnas usadas (tolerante a ausencias):
    Date, HomeTeam, AwayTeam, FTHG, FTAG
    Cuotas 1X2 de cierre: PSCH, PSCD, PSCA (con fallback a PSH, PSD, PSA)
    Cuotas O/U 2.5:       PC>2.5, PC<2.5 (con fallback a P>2.5 / Avg>2.5)
"""
import sys
import warnings
from pathlib import Path

import pandas as pd
from psycopg2.extras import execute_values

# Silenciar warnings cosmeticos al parsear CSVs heterogeneos
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

# Permitir imports desde la raiz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.database.connection import get_pg_connection  # noqa: E402
from sports.football.team_names import to_full as _team_full  # noqa: E402


LEAGUES = {
    # Top 5
    "E0":  {"name": "Premier League",      "country": "ENG"},
    "SP1": {"name": "La Liga",             "country": "ESP"},
    "I1":  {"name": "Serie A",             "country": "ITA"},
    "D1":  {"name": "Bundesliga",          "country": "GER"},
    "F1":  {"name": "Ligue 1",             "country": "FRA"},
    # Segunda division
    "E1":  {"name": "Championship",        "country": "ENG"},
    "SP2": {"name": "Segunda Division",    "country": "ESP"},
    "I2":  {"name": "Serie B",             "country": "ITA"},
    "D2":  {"name": "2. Bundesliga",       "country": "GER"},
    "F2":  {"name": "Ligue 2",             "country": "FRA"},
    # Otras ligas europeas
    "N1":  {"name": "Eredivisie",          "country": "NED"},
    "B1":  {"name": "Belgian Pro League",  "country": "BEL"},
    "P1":  {"name": "Primeira Liga",       "country": "POR"},
    "T1":  {"name": "Super Lig",           "country": "TUR"},
    "G1":  {"name": "Super League Greece", "country": "GRE"},
    "SC0": {"name": "Scottish Premiership","country": "SCO"},
}


def _season_code_to_label(code):
    """'2425' -> '2024-2025'."""
    return f"20{code[:2]}-20{code[2:]}"


def _parse_csv(csv_path):
    df = pd.read_csv(csv_path, encoding="latin-1", on_bad_lines="skip")

    required = {"Date", "HomeTeam", "AwayTeam"}
    if not required.issubset(df.columns):
        raise ValueError(f"CSV {csv_path.name} no tiene columnas {required}")

    df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam"])
    df["date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date"])

    return df


def _get_sport_id(conn, code):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM sports WHERE code = %s", (code,))
        row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Deporte '{code}' no existe en tabla sports")
    return row[0]


def _upsert_teams(conn, sport_id, team_names, country):
    # external_id sigue siendo el short name (estable). name = nombre completo.
    rows = [(sport_id, f"fd:{name}", _team_full(name), country) for name in team_names]
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


def _get_team_map(conn, sport_id, team_names):
    ext_ids = [f"fd:{n}" for n in team_names]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT external_id, id FROM entities
            WHERE sport_id = %s AND external_id = ANY(%s)
            """,
            (sport_id, ext_ids),
        )
        return {ext.replace("fd:", "", 1): tid for ext, tid in cur.fetchall()}


def _safe_int(value):
    try:
        if pd.isna(value):
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_odds(row, columns):
    """Devuelve la primera cuota valida encontrada entre `columns`."""
    for col in columns:
        if col not in row:
            continue
        val = row[col]
        if pd.isna(val):
            continue
        try:
            f = float(val)
        except (ValueError, TypeError):
            continue
        if f > 1.0:
            return round(f, 3)
    return None


def load_csv(conn, csv_path, league_code, season_code):
    df = _parse_csv(csv_path)
    if df.empty:
        return 0

    sport_id = _get_sport_id(conn, "football")
    league = LEAGUES[league_code]
    season_label = _season_code_to_label(season_code)

    teams = set(df["HomeTeam"]) | set(df["AwayTeam"])
    _upsert_teams(conn, sport_id, teams, league["country"])
    team_map = _get_team_map(conn, sport_id, teams)

    rows = []
    for _, r in df.iterrows():
        ht, at = r["HomeTeam"], r["AwayTeam"]
        if ht not in team_map or at not in team_map:
            continue
        rows.append((
            r["date"].date(),
            league["name"],
            season_label,
            team_map[ht],
            team_map[at],
            _safe_int(r.get("FTHG")),
            _safe_int(r.get("FTAG")),
            None,  # home_xg (football-data.co.uk no incluye xG)
            None,  # away_xg
            _safe_int(r.get("HC")),   # córners local
            _safe_int(r.get("AC")),   # córners visitante
            _safe_int(r.get("HY")),   # amarillas local
            _safe_int(r.get("AY")),   # amarillas visitante
            _safe_int(r.get("HR")),   # rojas local
            _safe_int(r.get("AR")),   # rojas visitante
            _safe_odds(r, ["PSCH", "PSH"]),
            _safe_odds(r, ["PSCD", "PSD"]),
            _safe_odds(r, ["PSCA", "PSA"]),
            _safe_odds(r, ["PC>2.5", "P>2.5", "Avg>2.5"]),
            _safe_odds(r, ["PC<2.5", "P<2.5", "Avg<2.5"]),
            "football-data.co.uk",
        ))

    if not rows:
        return 0

    with conn.cursor() as cur:
        # DO UPDATE (no DO NOTHING): así una re-ingesta rellena córners/tarjetas
        # en los partidos que ya existían sin ese dato. COALESCE evita pisar un
        # valor existente con NULL si un CSV no trae la columna.
        execute_values(
            cur,
            """
            INSERT INTO football_matches
                (date, league, season, home_team_id, away_team_id,
                 home_goals, away_goals, home_xg, away_xg,
                 home_corners, away_corners, home_yellows, away_yellows,
                 home_reds, away_reds,
                 odds_home_close, odds_draw_close, odds_away_close,
                 odds_o25_close, odds_u25_close, source)
            VALUES %s
            ON CONFLICT (date, home_team_id, away_team_id) DO UPDATE SET
                home_corners = COALESCE(EXCLUDED.home_corners, football_matches.home_corners),
                away_corners = COALESCE(EXCLUDED.away_corners, football_matches.away_corners),
                home_yellows = COALESCE(EXCLUDED.home_yellows, football_matches.home_yellows),
                away_yellows = COALESCE(EXCLUDED.away_yellows, football_matches.away_yellows),
                home_reds    = COALESCE(EXCLUDED.home_reds,    football_matches.home_reds),
                away_reds    = COALESCE(EXCLUDED.away_reds,    football_matches.away_reds)
            """,
            rows,
        )
    conn.commit()
    return len(rows)


def load_directory(raw_dir="data/raw/football"):
    """Ingesta todos los {LEAGUE}_{SEASON}.csv de un directorio."""
    raw_path = Path(raw_dir)
    if not raw_path.exists():
        raise FileNotFoundError(f"Directorio no existe: {raw_path}")

    csv_files = sorted(raw_path.glob("*.csv"))
    if not csv_files:
        print(f"[WARN] Sin CSVs en {raw_path}. Ejecuta primero scripts/download_football_data.py")
        return 0

    total = 0
    conn = get_pg_connection()
    try:
        for csv_file in csv_files:
            parts = csv_file.stem.split("_")
            if len(parts) != 2:
                print(f"[skip] {csv_file.name}: nombre no cumple {{LEAGUE}}_{{SEASON}}.csv")
                continue
            league_code, season_code = parts
            if league_code not in LEAGUES:
                print(f"[skip] {csv_file.name}: liga '{league_code}' no soportada")
                continue
            try:
                inserted = load_csv(conn, csv_file, league_code, season_code)
                print(f"[ok]   {csv_file.name:<20} {inserted:>4} partidos")
                total += inserted
            except Exception as e:
                print(f"[ERR]  {csv_file.name}: {type(e).__name__}: {e}")
                conn.rollback()
    finally:
        conn.close()

    return total
