"""
Predicción de mercados de un enfrentamiento — reutilizable y desacoplada de la UI.

La usa la página "Partidos del día" para computar el top-10 de cada partido y
registrarlo en el historial. Misma matemática que el Analizador, pero como función
pura (recibe el engine, devuelve la lista de mercados).
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RHO = -0.10


def predict_baseball(engine, home_id: int, away_id: int, game_date=None) -> list:
    """Mercados MLB (Pythagorean + Monte Carlo). [] si faltan datos.

    Si se pasa `game_date`, ajusta las carreras esperadas por el abridor probable
    de ese juego (FIP) cuando el dato está disponible en mlb_starters/pitcher_stats.
    """
    from sports.baseball.markets import all_markets

    df = pd.read_sql(
        "SELECT home_team_id, away_team_id, home_runs, away_runs, date "
        "FROM baseball_games WHERE home_runs IS NOT NULL",
        engine, parse_dates=["date"],
    )
    if df.empty:
        return []
    df = df[df["date"].dt.year == df["date"].dt.year.max()]
    h = df[["home_team_id", "home_runs", "away_runs"]].rename(
        columns={"home_team_id": "tid", "home_runs": "rs", "away_runs": "ra"})
    a = df[["away_team_id", "away_runs", "home_runs"]].rename(
        columns={"away_team_id": "tid", "away_runs": "rs", "home_runs": "ra"})
    agg = pd.concat([h, a]).groupby("tid").agg(
        RS=("rs", "sum"), RA=("ra", "sum"), G=("rs", "count")).reset_index()
    league_rpg = float(agg["RS"].sum()) / float(agg["G"].sum()) if agg["G"].sum() else 4.5

    def rates(tid):
        row = agg[agg["tid"] == tid]
        if row.empty or int(row["G"].iloc[0]) == 0:
            return league_rpg, league_rpg
        g = float(row["G"].iloc[0])
        return float(row["RS"].iloc[0]) / g, float(row["RA"].iloc[0]) / g

    h_rs, h_ra = rates(home_id)
    a_rs, a_ra = rates(away_id)
    e_home = max(0.5, h_rs * a_ra / league_rpg * 1.03)   # leve ventaja local
    e_away = max(0.5, a_rs * h_ra / league_rpg)

    # Ajuste por abridor probable (FIP) cuando hay fecha y dato disponible.
    if game_date is not None:
        from sports.baseball.starter_adjustment import adjust_runs, lookup_starter_fips
        hf, af = lookup_starter_fips(engine, home_id, away_id, game_date)
        e_home, e_away = adjust_runs(e_home, e_away, hf, af)

    # Park factor del estadio local (afecta a ambas ofensivas por igual).
    from sports.baseball.park_factors import park_factor
    nm = pd.read_sql("SELECT name FROM entities WHERE id = %(h)s",
                     engine, params={"h": int(home_id)})
    if not nm.empty:
        pf = park_factor(nm["name"].iloc[0])
        e_home, e_away = e_home * pf, e_away * pf

    markets = all_markets(e_home, e_away, rng=np.random.default_rng(42))
    # Hits/jonrones/ponches (modelo aparte). [] si no hay dato re-ingestado.
    from core.baseball_stats import stats_markets_for
    return markets + stats_markets_for(engine, home_id, away_id)


def predict_football(engine, home_id: int, away_id: int) -> list:
    """Mercados de fútbol (GLM Poisson + Dixon-Coles). [] si falta el modelo."""
    import joblib

    from sports.football.markets import all_markets

    model_path = ROOT / "data" / "models" / "football_poisson_v1.joblib"
    if not model_path.exists():
        return []
    model = joblib.load(model_path)

    def elo(tid):
        d = pd.read_sql("SELECT elo FROM football_elo WHERE team_id = %(t)s "
                        "ORDER BY date DESC LIMIT 1", engine, params={"t": tid})
        return float(d["elo"].iloc[0]) if not d.empty else 1500.0

    def stats(tid):
        d = pd.read_sql(
            "SELECT CASE WHEN home_team_id=%(t)s THEN home_goals ELSE away_goals END AS gf, "
            "CASE WHEN home_team_id=%(t)s THEN away_goals ELSE home_goals END AS ga "
            "FROM football_matches WHERE (home_team_id=%(t)s OR away_team_id=%(t)s) "
            "AND home_goals IS NOT NULL ORDER BY date DESC LIMIT 10",
            engine, params={"t": tid})
        if d.empty:
            return {"gf_5": 1.4, "gf_10": 1.4, "ga_5": 1.4, "ga_10": 1.4, "form_5": 6}
        l5, l10 = d.head(5), d.head(10)
        form = int(sum(3 if r.gf > r.ga else (1 if r.gf == r.ga else 0)
                       for r in l5.itertuples(index=False)))
        return {"gf_5": float(l5.gf.mean()), "gf_10": float(l10.gf.mean()),
                "ga_5": float(l5.ga.mean()), "ga_10": float(l10.ga.mean()), "form_5": form}

    he, ae = elo(home_id), elo(away_id)
    hs, as_ = stats(home_id), stats(away_id)
    feats = pd.DataFrame([{
        "home_elo": he, "away_elo": ae,
        "home_gf_5": hs["gf_5"], "home_gf_10": hs["gf_10"],
        "home_ga_5": hs["ga_5"], "home_ga_10": hs["ga_10"],
        "away_gf_5": as_["gf_5"], "away_gf_10": as_["gf_10"],
        "away_ga_5": as_["ga_5"], "away_ga_10": as_["ga_10"],
        "home_form_5": hs["form_5"], "away_form_5": as_["form_5"],
        "home_rest": 7, "away_rest": 7,
    }])
    pred = model.predict_lambda(feats)
    lh, la = float(pred["lambda_home"].iloc[0]), float(pred["lambda_away"].iloc[0])

    from core.football_stats import stats_markets_for
    return all_markets(lh, la, rho=RHO) + stats_markets_for(engine, home_id, away_id)


def predict(sport: str, engine, home_id: int, away_id: int, game_date=None) -> list:
    """Dispatcher: mercados del enfrentamiento según deporte."""
    if sport == "baseball":
        return predict_baseball(engine, home_id, away_id, game_date)
    if sport == "football":
        return predict_football(engine, home_id, away_id)
    return []
