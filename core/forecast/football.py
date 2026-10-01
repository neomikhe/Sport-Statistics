from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from core.forecast.base import Forecast
from sports.football.markets import all_markets, score_matrix
from sports.football.team_ratings import WINDOW_DAYS, fit_ratings

ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = ROOT / "data" / "models" / "football_poisson_v1.json"
DEFAULT_STATS = {"gf_5": 1.4, "gf_10": 1.4, "ga_5": 1.4, "ga_10": 1.4, "form_5": 6.0}
HEATMAP_GOALS = 6


@dataclass(frozen=True)
class FootballParams:
    xi: float = 0.0015
    reg: float = 8.0
    w_dc: float = 0.5
    rho: float = -0.10


_RECENT_SQL = """
    SELECT team_id, date, league, gf, ga FROM (
        SELECT team_id, date, league, gf, ga,
               ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY date DESC) AS rn
        FROM (
            SELECT home_team_id AS team_id, date, league, home_goals AS gf, away_goals AS ga
            FROM football_matches WHERE home_goals IS NOT NULL
            UNION ALL
            SELECT away_team_id, date, league, away_goals, home_goals
            FROM football_matches WHERE home_goals IS NOT NULL
        ) t
    ) x
    WHERE rn <= 10
"""

_ELO_SQL = """
    SELECT DISTINCT ON (team_id) team_id, elo, date
    FROM football_elo ORDER BY team_id, date DESC
"""

_LEAGUE_SQL = """
    SELECT date, home_team_id, away_team_id, home_goals, away_goals
    FROM football_matches
    WHERE league = %(lg)s AND home_goals IS NOT NULL AND date >= %(since)s
    ORDER BY date
"""


def _team_features(recent: pd.DataFrame) -> dict:
    if recent.empty:
        return {}
    r = recent.sort_values(["team_id", "date"], ascending=[True, False])
    r = r.assign(rn=r.groupby("team_id").cumcount(),
                 pts=np.select([r["gf"] > r["ga"], r["gf"] == r["ga"]], [3.0, 1.0], 0.0),
                 res=np.select([r["gf"] > r["ga"], r["gf"] == r["ga"]], ["G", "E"], "P"))
    last5 = r[r["rn"] < 5].groupby("team_id").agg(
        gf_5=("gf", "mean"), ga_5=("ga", "mean"), form_5=("pts", "sum"), form=("res", list))
    last10 = r.groupby("team_id").agg(
        gf_10=("gf", "mean"), ga_10=("ga", "mean"), last_date=("date", "first"),
        league=("league", "first"))
    return {int(k): v for k, v in last5.join(last10).to_dict("index").items()}


class FootballForecaster:
    def __init__(self, engine, glm, teams: dict, elo: dict,
                 params: FootballParams | None = None):
        self.engine = engine
        self.glm = glm
        self.teams = teams
        self.elo = elo
        self.p = params or FootballParams()
        self._ratings: dict = {}

    @classmethod
    def from_db(cls, engine, params: FootballParams | None = None,
                model_path: Path = MODEL_PATH) -> "FootballForecaster | None":
        from sports.football.models import load_model

        if not Path(model_path).exists():
            return None
        glm = load_model(model_path)
        recent = pd.read_sql(_RECENT_SQL, engine, parse_dates=["date"])
        elo = pd.read_sql(_ELO_SQL, engine)
        elo_map = {int(t): float(e) for t, e in zip(elo["team_id"], elo["elo"])}
        return cls(engine, glm, _team_features(recent), elo_map, params)

    def team_state(self, team_id: int) -> dict:
        s = dict(self.teams.get(int(team_id), DEFAULT_STATS))
        s.setdefault("form", [])
        s.setdefault("last_date", None)
        s.setdefault("league", None)
        s["elo"] = self.elo.get(int(team_id), 1500.0)
        return s

    def common_league(self, home_id: int, away_id: int) -> str | None:
        lh = self.teams.get(int(home_id), {}).get("league")
        la = self.teams.get(int(away_id), {}).get("league")
        return lh if lh and lh == la else None

    def league_ratings(self, league: str):
        if league in self._ratings:
            return self._ratings[league]
        since = (pd.Timestamp.today().normalize()
                 - pd.Timedelta(days=WINDOW_DAYS + 400)).date()
        m = pd.read_sql(_LEAGUE_SQL, self.engine, params={"lg": league, "since": str(since)},
                        parse_dates=["date"])
        r = None
        if not m.empty:
            ref = m["date"].max() + pd.Timedelta(days=1)
            r = fit_ratings(m, ref, xi=self.p.xi, reg=self.p.reg)
        self._ratings[league] = r
        return r

    def glm_lambdas(self, home_id: int, away_id: int) -> tuple:
        h, a = self.team_state(home_id), self.team_state(away_id)
        feats = pd.DataFrame([{
            "home_elo": h["elo"], "away_elo": a["elo"],
            "home_gf_5": h["gf_5"], "home_gf_10": h["gf_10"],
            "home_ga_5": h["ga_5"], "home_ga_10": h["ga_10"],
            "away_gf_5": a["gf_5"], "away_gf_10": a["gf_10"],
            "away_ga_5": a["ga_5"], "away_ga_10": a["ga_10"],
            "home_form_5": h["form_5"], "away_form_5": a["form_5"],
            "home_rest": 7, "away_rest": 7,
        }])
        pred = self.glm.predict_lambda(feats)
        return float(pred["lambda_home"].iloc[0]), float(pred["lambda_away"].iloc[0])

    def lambdas(self, home_id: int, away_id: int, league: str | None = None) -> tuple:
        lh, la = self.glm_lambdas(home_id, away_id)
        lg = league or self.common_league(home_id, away_id)
        r = self.league_ratings(lg) if lg else None
        if r is not None and r.has(int(home_id)) and r.has(int(away_id)):
            dh, da = r.lambdas(int(home_id), int(away_id))
            # Mezcla GLM y Dixon-Coles en escala logarítmica.
            w = self.p.w_dc
            lh = float(np.exp(w * np.log(dh) + (1 - w) * np.log(lh)))
            la = float(np.exp(w * np.log(da) + (1 - w) * np.log(la)))
            return lh, la, "GLM + Dixon-Coles", r
        return lh, la, "GLM (sin liga común)", None

    def forecast(self, home_id: int, away_id: int, home_name: str = "Local",
                 away_name: str = "Visitante", league: str | None = None,
                 lambda_mult=(1.0, 1.0), extra_markets=None) -> Forecast:
        lh, la, method, r = self.lambdas(home_id, away_id, league)
        lh, la = lh * lambda_mult[0], la * lambda_mult[1]
        mk = all_markets(lh, la, rho=self.p.rho) + list(extra_markets or [])
        win = {m["mercado"]: m["prob"] for m in mk if m["grupo"] == "1X2"}
        h, a = self.team_state(home_id), self.team_state(away_id)
        if r is not None:
            h.update({f"dc_{k}": v for k, v in r.team(int(home_id)).items()})
            a.update({f"dc_{k}": v for k, v in r.team(int(away_id)).items()})
        notes = []
        if method.startswith("GLM ("):
            notes.append("Equipos de ligas distintas (o sin liga común reciente): solo "
                         "modelo GLM con Elo, sin ratings de liga.")
        for nm, st_ in ((home_name, h), (away_name, a)):
            if not st_.get("form"):
                notes.append(f"{nm}: sin partidos recientes en la base; se usan medias por defecto.")
        matrix = score_matrix(lh, la, self.p.rho, max_goals=10)[:HEATMAP_GOALS + 1,
                                                                 :HEATMAP_GOALS + 1]
        return Forecast(
            sport="football", home=home_name, away=away_name, markets=mk,
            win={"home": win.get("Gana local", 0.0), "draw": win.get("Empate", 0.0),
                 "away": win.get("Gana visitante", 0.0)},
            expected={"home": lh, "away": la, "unit": "goles", "total": lh + la},
            ratings={"home": h, "away": a},
            notes=notes,
            extras={"method": method, "league": league or self.common_league(home_id, away_id),
                    "rho": self.p.rho, "matrix": matrix},
        )
