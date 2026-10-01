import logging
from pathlib import Path

import pandas as pd
import streamlit as st

_log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
MODEL_TTL = 3600
DATA_TTL = 600


@st.cache_resource(show_spinner=False)
def engine():
    from core.database.connection import get_sqlalchemy_engine
    return get_sqlalchemy_engine()


@st.cache_data(ttl=60, show_spinner=False)
def db_ok() -> bool:
    try:
        pd.read_sql("SELECT 1 AS ok", engine())
        return True
    except Exception as e:  # noqa: BLE001 - cualquier fallo = sin BD
        _log.warning("BD no disponible: %s", e)
        return False


# Consultas siempre parametrizadas; si la BD falla, se devuelve vacío.
def _read(sql: str, params: dict | None = None, **kw) -> pd.DataFrame:
    try:
        return pd.read_sql(sql, engine(), params=params, **kw)
    except Exception as e:  # noqa: BLE001
        _log.warning("consulta fallida: %s", e)
        return pd.DataFrame()


@st.cache_resource(ttl=MODEL_TTL, show_spinner=False)
def model(sport: str):
    from core.matchup import build_model
    try:
        return build_model(sport, engine())
    except Exception as e:  # noqa: BLE001
        _log.warning("no se pudo construir el motor de %s: %s", sport, e)
        return None


def forecast(sport: str, home_id: int, away_id: int, home_name: str, away_name: str, **opts):
    m = model(sport)
    if m is None:
        return None
    mult = opts.get("mult", (1.0, 1.0))
    if sport == "football":
        from core.football_stats import stats_markets_for
        from core.history.calibration import apply_corrections
        extra = apply_corrections(stats_markets_for(engine(), home_id, away_id), sport, engine())
        return m.forecast(home_id, away_id, home_name, away_name, league=opts.get("league"),
                          lambda_mult=mult, extra_markets=extra)
    if sport == "basketball":
        return m.forecast(home_id, away_id, home_name, away_name, points_mult=mult)
    if sport == "baseball":
        from core.baseball_stats import stats_markets_for
        from core.history.calibration import apply_corrections
        from sports.baseball.starter_adjustment import lookup_starter_fips
        fips = lookup_starter_fips(engine(), home_id, away_id, opts.get("game_date"))
        fc = m.forecast(home_id, away_id, home_name, away_name, starter_fips=fips, runs_mult=mult)
        fc.markets = fc.markets + apply_corrections(
            stats_markets_for(engine(), home_id, away_id), sport, engine())
        return fc
    if sport == "tennis":
        from core.tennis_stats import stats_markets_for as tennis_stats
        fc = m.forecast(home_id, away_id, opts.get("surface", "hard"), opts.get("best_of", 3),
                        home_name, away_name, elo_penalty=opts.get("elo_penalty", (0.0, 0.0)))
        fc.markets = fc.markets + tennis_stats(engine(), home_id, away_id, fc.extras["surface"],
                                               home_name, away_name, best_of=fc.extras["best_of"])
        return fc
    return None


@st.cache_data(ttl=900, show_spinner=False, max_entries=400)
def _fixture_forecast(sport: str, home_id: int, away_id: int, home: str, away: str, day):
    from core.matchup import forecast_match
    try:
        return forecast_match(sport, engine(), home_id, away_id, home, away,
                              game_date=day, model=model(sport))
    except Exception as e:  # noqa: BLE001
        _log.warning("pronóstico de %s vs %s: %s", home, away, e)
        return None


def fixture_forecast(sport: str, fx: dict, day):
    if not (fx.get("home_id") and fx.get("away_id")):
        return None
    return _fixture_forecast(sport, int(fx["home_id"]), int(fx["away_id"]),
                             str(fx["home"]), str(fx["away"]), day)


@st.cache_data(ttl=DATA_TTL, show_spinner=False)
def entities(sport: str) -> pd.DataFrame:
    return _read("""
        SELECT id, name FROM entities
        WHERE sport_id = (SELECT id FROM sports WHERE code = %(s)s)
        ORDER BY name
    """, {"s": sport})


TOP_LEAGUES = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
               "Primeira Liga", "Eredivisie", "Championship", "Belgian Pro League", "Super Lig",
               "Scottish Premiership", "MLS", "Liga MX", "Brasileirão"]


@st.cache_data(ttl=DATA_TTL, show_spinner=False)
def football_leagues() -> list:
    df = _read("SELECT DISTINCT league FROM football_matches WHERE home_goals IS NOT NULL")
    if df.empty:
        return []
    have = set(df["league"].astype(str))
    return [lg for lg in TOP_LEAGUES if lg in have] + sorted(have - set(TOP_LEAGUES))


@st.cache_data(ttl=DATA_TTL, show_spinner=False)
def league_teams(league: str) -> pd.DataFrame:
    df = _read("""
        SELECT DISTINCT e.id, e.name FROM entities e
        JOIN football_matches m ON (m.home_team_id = e.id OR m.away_team_id = e.id)
        WHERE m.league = %(lg)s
          AND m.date >= (SELECT MAX(date) FROM football_matches WHERE league = %(lg)s) - 400
        ORDER BY e.name
    """, {"lg": league})
    return df


@st.cache_data(ttl=DATA_TTL, show_spinner=False)
def tennis_players(tour: str = "ATP") -> pd.DataFrame:
    prefix = "sack_wta:%" if tour == "WTA" else "sack_atp:%"
    return _read("""
        SELECT e.id, e.name, COUNT(*) AS n
        FROM tennis_matches m
        JOIN entities e ON e.id IN (m.player1_id, m.player2_id)
        WHERE m.date >= (SELECT MAX(date) FROM tennis_matches) - 730
          AND e.external_id LIKE %(prefix)s
        GROUP BY e.id, e.name
        ORDER BY n DESC, e.name
    """, {"prefix": prefix})


_RECENT = {
    "football": ("football_matches", "home_goals", "away_goals"),
    "basketball": ("basketball_games", "home_score", "away_score"),
    "baseball": ("baseball_games", "home_runs", "away_runs"),
}


@st.cache_data(ttl=DATA_TTL, show_spinner=False)
def recent_games(sport: str, team_id: int, n: int = 10) -> pd.DataFrame:
    if sport not in _RECENT:
        return pd.DataFrame()
    table, ch, ca = _RECENT[sport]
    df = _read(f"""
        SELECT g.date,
               CASE WHEN g.home_team_id = %(t)s THEN ea.name ELSE eh.name END AS rival,
               CASE WHEN g.home_team_id = %(t)s THEN g.{ch} ELSE g.{ca} END AS f,
               CASE WHEN g.home_team_id = %(t)s THEN g.{ca} ELSE g.{ch} END AS c,
               CASE WHEN g.home_team_id = %(t)s THEN 'L' ELSE 'V' END AS loc
        FROM {table} g
        JOIN entities eh ON eh.id = g.home_team_id
        JOIN entities ea ON ea.id = g.away_team_id
        WHERE (g.home_team_id = %(t)s OR g.away_team_id = %(t)s) AND g.{ch} IS NOT NULL
        ORDER BY g.date DESC LIMIT %(n)s
    """, {"t": int(team_id), "n": int(n)}, parse_dates=["date"])
    if df.empty:
        return df
    df = df.sort_values("date").reset_index(drop=True)
    df["f"], df["c"] = df["f"].astype(int), df["c"].astype(int)
    df["res"] = ["G" if a > b else ("E" if a == b else "P") for a, b in zip(df["f"], df["c"])]
    return df


@st.cache_data(ttl=DATA_TTL, show_spinner=False)
def tennis_recent(player_id: int, n: int = 10) -> pd.DataFrame:
    df = _read("""
        SELECT m.date, m.surface, m.tournament, m.round, m.score,
               CASE WHEN m.player1_id = %(p)s THEN e2.name ELSE e1.name END AS rival,
               CASE WHEN m.winner_id = %(p)s THEN 'G' ELSE 'P' END AS res
        FROM tennis_matches m
        JOIN entities e1 ON e1.id = m.player1_id
        JOIN entities e2 ON e2.id = m.player2_id
        WHERE m.player1_id = %(p)s OR m.player2_id = %(p)s
        ORDER BY m.date DESC, m.id DESC LIMIT %(n)s
    """, {"p": int(player_id), "n": int(n)}, parse_dates=["date"])
    return df


@st.cache_data(ttl=900, show_spinner=False)
def fixtures(sport: str, day) -> list:
    from core.fixtures import todays_fixtures
    from core.fixtures.match import attach_entity_ids
    try:
        return attach_entity_ids(engine(), sport, todays_fixtures(sport, day))
    except Exception as e:  # noqa: BLE001
        _log.warning("agenda %s %s: %s", sport, day, e)
        return []


def football_token() -> bool:
    from core.fixtures.football import has_token
    return has_token()


def log_situations(sport: str, day, fx: dict, situations: list) -> None:
    from core.history.store import log_predictions
    log_predictions(sport, day, fx["home"], fx["away"], situations, fx["home_id"], fx["away_id"])


@st.cache_data(ttl=300, show_spinner=False)
def meta(key: str):
    df = _read("SELECT value FROM app_meta WHERE key = %(k)s", {"k": key})
    return df["value"].iloc[0] if not df.empty else None


@st.cache_data(ttl=DATA_TTL, show_spinner=False)
def coverage() -> dict:
    df = _read("""
        SELECT 'football' AS sport, COUNT(*) AS n, MAX(date) AS last FROM football_matches WHERE home_goals IS NOT NULL
        UNION ALL SELECT 'basketball', COUNT(*), MAX(date) FROM basketball_games WHERE home_score IS NOT NULL
        UNION ALL SELECT 'baseball', COUNT(*), MAX(date) FROM baseball_games WHERE home_runs IS NOT NULL
        UNION ALL SELECT 'tennis', COUNT(*), MAX(date) FROM tennis_matches WHERE winner_id IS NOT NULL
    """)
    return {r.sport: {"n": int(r.n), "last": r.last} for r in df.itertuples()} if not df.empty else {}


PICKS_COLS = ["season", "date", "league", "home", "away", "selection",
              "prob_model", "odds", "ev", "kelly_frac", "stake", "real_result"]


@st.cache_data(ttl=300, show_spinner=False)
def picks() -> tuple:
    df = _read(f"SELECT {', '.join(PICKS_COLS)} FROM football_picks", parse_dates=["date"])
    if not df.empty:
        num = ["prob_model", "odds", "ev", "kelly_frac", "stake"]
        df[num] = df[num].astype(float)
        return df, "BD"
    files = sorted((ROOT / "data" / "processed").glob("picks_football_*.csv"))
    frames = []
    for f in files:
        d = pd.read_csv(f, parse_dates=["date"])
        d.insert(0, "season", f.stem.replace("picks_football_", ""))
        frames.append(d)
    if not frames:
        return pd.DataFrame(columns=PICKS_COLS), None
    return pd.concat(frames, ignore_index=True)[PICKS_COLS], "CSV local"


@st.cache_data(ttl=DATA_TTL, show_spinner=False)
def history(sport: str | None, since) -> dict:
    from core.history.store import (history_points, history_summary, history_trend,
                                    recent_resolved)
    return {
        "summary": history_summary(sport, since),
        "points": history_points(sport, since),
        "trend": history_trend(sport, since),
        "recent": recent_resolved(60, sport, since),
    }


@st.cache_data(ttl=300, show_spinner=False)
def summary_dates(limit: int = 30) -> list:
    from core.history import summary
    try:
        return summary.available_dates(engine(), limit)
    except Exception as e:  # noqa: BLE001
        _log.warning("fechas de resumen: %s", type(e).__name__)
        return []


@st.cache_data(ttl=300, show_spinner=False)
def day_summary(day) -> tuple:
    from core.history import summary
    try:
        stored = summary.load(engine(), day)
        if stored:
            return stored, True
        live = summary.build(engine(), day)
        return (live if live["totals"]["matches"] else None), False
    except Exception as e:  # noqa: BLE001
        _log.warning("resumen del día: %s", type(e).__name__)
        return None, False


def ai_enabled() -> bool:
    from core.ai import gemini
    return gemini.is_enabled()


@st.cache_data(ttl=21600, show_spinner="Consultando bajas y contexto actual…")
def ai_context(home: str, away: str, sport: str, league: str = ""):
    from core.ai import gemini
    return gemini.match_context(home, away, sport, league)
