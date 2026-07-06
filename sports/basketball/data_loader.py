"""
Carga de datos NBA usando nba_api (wrapper de stats.nba.com).

Descarga box scores historicos y los inserta en la tabla basketball_games.
nba_api tiene rate limits informales: sleep 0.6 s entre peticiones para evitar bloqueos.

Uso:
    from sports.basketball.data_loader import load_season
    load_season("2023-24")

    # O via script:
    python scripts/download_basketball_data.py
"""
import time

import pandas as pd
from psycopg2.extras import execute_values

from core.database.connection import get_pg_connection


# NBA IDs
NBA_SPORT_CODE = "basketball"
SLEEP_BETWEEN_REQUESTS = 0.6  # polite delay


def _get_sport_id(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM sports WHERE code = %s", (NBA_SPORT_CODE,))
        return cur.fetchone()[0]


def _upsert_team(conn, sport_id: int, external_id: str, name: str) -> int:
    """Inserta (si no existe) un equipo y devuelve su id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entities (sport_id, external_id, name, country)
            VALUES (%s, %s, %s, 'USA')
            ON CONFLICT (sport_id, external_id) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (sport_id, external_id, name),
        )
        return cur.fetchone()[0]


def _safe_int(v):
    try:
        if v is None or pd.isna(v):
            return None
        return int(v)
    except (ValueError, TypeError):
        return None


_NBA_TEAM_IDS = set(range(1610612737, 1610612767))  # 30 equipos NBA, IDs consecutivos


def fetch_season_games(season: str) -> pd.DataFrame:
    """
    Descarga box scores Regular Season + Playoffs de una temporada via nba_api.

    season: "2023-24" formato NBA estandar.

    Filtra:
      - Solo Regular Season + Playoffs (descarta preseason, All-Star, exhibiciones)
      - Solo partidos donde AMBOS equipos son NBA (descarta selecciones, internacionales)

    Returns DataFrame con una fila por partido (no por equipo).
    """
    from nba_api.stats.endpoints import leaguegamefinder

    parts = []
    for season_type in ("Regular Season", "Playoffs"):
        finder = leaguegamefinder.LeagueGameFinder(
            season_nullable=season,
            league_id_nullable="00",
            season_type_nullable=season_type,
        )
        df = finder.get_data_frames()[0]
        if not df.empty:
            parts.append(df)
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    if not parts:
        return pd.DataFrame()

    games = pd.concat(parts, ignore_index=True)

    # Filtrar a equipos NBA legitimos
    games = games[games["TEAM_ID"].isin(_NBA_TEAM_IDS)]

    # Cada partido aparece 2 veces. Quedarse con perspectiva del LOCAL.
    games["is_home"] = ~games["MATCHUP"].str.contains("@")
    home = games[games["is_home"]].copy()
    away = games[~games["is_home"]].copy()

    # Stats extendidas para Four Factors
    EXTRA_COLS = ["FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "TOV", "AST"]

    home_cols = (
        ["GAME_ID", "GAME_DATE", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "PTS"]
        + [c for c in EXTRA_COLS if c in home.columns]
    )
    away_cols = (
        ["GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "PTS"]
        + [c for c in EXTRA_COLS if c in away.columns]
    )

    merged = home[home_cols].merge(
        away[away_cols], on="GAME_ID", suffixes=("_home", "_away"),
    )

    rename = {
        "GAME_DATE": "date",
        "TEAM_ID_home": "home_ext_id",
        "TEAM_ABBREVIATION_home": "home_abbr",
        "TEAM_NAME_home": "home_name",
        "PTS_home": "home_score",
        "TEAM_ID_away": "away_ext_id",
        "TEAM_ABBREVIATION_away": "away_abbr",
        "TEAM_NAME_away": "away_name",
        "PTS_away": "away_score",
    }
    for c in EXTRA_COLS:
        rename[f"{c}_home"] = f"home_{c.lower()}"
        rename[f"{c}_away"] = f"away_{c.lower()}"

    return merged.rename(columns=rename)


def load_season(season: str) -> int:
    """Descarga una temporada NBA y la inserta en PostgreSQL. Devuelve # partidos insertados."""
    conn = get_pg_connection()
    try:
        sport_id = _get_sport_id(conn)
        df = fetch_season_games(season)
        df["date"] = pd.to_datetime(df["date"])

        # Upsert de equipos con nombre COMPLETO (Boston Celtics, no BOS)
        team_map = {}
        for _, r in df.iterrows():
            if r["home_abbr"] not in team_map:
                team_map[r["home_abbr"]] = _upsert_team(
                    conn, sport_id, f"nba:{r['home_ext_id']}", r["home_name"]
                )
            if r["away_abbr"] not in team_map:
                team_map[r["away_abbr"]] = _upsert_team(
                    conn, sport_id, f"nba:{r['away_ext_id']}", r["away_name"]
                )
        conn.commit()

        # Insertar partidos
        rows = []
        EXTRA_COLS = ["fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "tov", "ast"]
        for _, r in df.iterrows():
            base = (
                r["date"].date(),
                team_map[r["home_abbr"]],
                team_map[r["away_abbr"]],
                int(r["home_score"]),
                int(r["away_score"]),
            )
            extras_h = tuple(_safe_int(r.get(f"home_{c}")) for c in EXTRA_COLS)
            extras_a = tuple(_safe_int(r.get(f"away_{c}")) for c in EXTRA_COLS)
            rows.append(base + extras_h + extras_a)

        with conn.cursor() as cur:
            extra_cols_sql_h = ", ".join(f"home_{c}" for c in EXTRA_COLS)
            extra_cols_sql_a = ", ".join(f"away_{c}" for c in EXTRA_COLS)
            execute_values(
                cur,
                f"""
                INSERT INTO basketball_games
                    (date, home_team_id, away_team_id, home_score, away_score,
                     {extra_cols_sql_h}, {extra_cols_sql_a})
                VALUES %s
                ON CONFLICT (date, home_team_id, away_team_id) DO NOTHING
                """,
                rows,
            )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def load_multiple_seasons(seasons: list) -> dict:
    """Carga varias temporadas secuencialmente con pausas."""
    totals = {}
    for season in seasons:
        print(f"[basketball] descargando temporada {season}...")
        try:
            n = load_season(season)
            totals[season] = n
            print(f"  [ok] {n} partidos insertados")
        except Exception as e:
            print(f"  [ERR] {type(e).__name__}: {e}")
            totals[season] = -1
        time.sleep(1.0)
    return totals
