import math
from dataclasses import dataclass

import pandas as pd

from core.forecast.base import Forecast, season_of
from sports.basketball.elo import BasketballEloSystem
from sports.basketball.markets import normal_markets

SEASON_START_MONTH = 10


@dataclass(frozen=True)
class NBAParams:
    decay: float = 0.95
    prior_games: float = 6.0
    season_carry: float = 0.4
    league_decay: float = 0.998
    hca: float = 2.0
    w_elo: float = 0.2
    elo_pts: float = 28.0
    sigma_margin: float = 13.8
    sigma_total: float = 18.8


# Fórmula de Oliver.
def possessions(fga, oreb, tov, fta):
    return fga - oreb + tov + 0.44 * fta


def load_games(engine) -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT id, date, home_team_id, away_team_id, home_score, away_score,
               home_fga, home_oreb, home_tov, home_fta,
               away_fga, away_oreb, away_tov, away_fta
        FROM basketball_games
        WHERE home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY date, id
        """,
        engine, parse_dates=["date"],
    )
    ph = possessions(df["home_fga"], df["home_oreb"], df["home_tov"], df["home_fta"])
    pa = possessions(df["away_fga"], df["away_oreb"], df["away_tov"], df["away_fta"])
    df["poss"] = (ph + pa) / 2.0
    return df


class NBAForecaster:
    def __init__(self, params: NBAParams | None = None):
        self.p = params or NBAParams()
        self.elo = BasketballEloSystem()
        self._t: dict = {}
        self._lg = [0.0, 0.0, 0.0]
        self.last_date = None
        self.n_games = 0

    @classmethod
    def from_games(cls, df: pd.DataFrame, params: NBAParams | None = None) -> "NBAForecaster":
        f = cls(params)
        cols = ["date", "home_team_id", "away_team_id", "home_score", "away_score", "poss"]
        for d, h, a, hs, as_, poss in df[cols].itertuples(index=False, name=None):
            f.update(d, int(h), int(a), float(hs), float(as_), poss)
        return f

    def _league(self):
        pts, poss, w = self._lg
        if w <= 0:
            return 112.0, 99.0
        return pts / w, poss / w

    def _roll_season(self, team: int, season: int) -> list:
        s = self._t.get(team)
        if s is None:
            s = [0.0, 0.0, 0.0, 0.0, season, 0, None]
            self._t[team] = s
        elif s[4] != season:
            c = self.p.season_carry
            s[0], s[1], s[2], s[3] = s[0] * c, s[1] * c, s[2] * c, s[3] * c
            s[4] = season
        return s

    def update(self, date, home: int, away: int, home_pts: float, away_pts: float,
               poss=None) -> None:
        season = season_of(date, SEASON_START_MONTH)
        self.elo.process_game(date, str(season), home, away, int(home_pts), int(away_pts))
        _, lg_poss = self._league()
        if poss is None or not math.isfinite(float(poss)) or poss <= 0:
            poss = lg_poss
        d = self.p.decay
        for team, pf, pa in ((home, home_pts, away_pts), (away, away_pts, home_pts)):
            s = self._roll_season(team, season)
            s[0] = s[0] * d + pf
            s[1] = s[1] * d + pa
            s[2] = s[2] * d + poss
            s[3] = s[3] * d + 1.0
            s[5] += 1
            s[6] = date
        ld = self.p.league_decay
        self._lg[0] = self._lg[0] * ld + (home_pts + away_pts) / 2.0
        self._lg[1] = self._lg[1] * ld + poss
        self._lg[2] = self._lg[2] * ld + 1.0
        self.last_date = date
        self.n_games += 1

    def team_state(self, team: int) -> dict:
        lg_pts, lg_poss = self._league()
        k = self.p.prior_games
        s = self._t.get(team, [0.0, 0.0, 0.0, 0.0, None, 0, None])
        off = (s[0] + k * lg_pts) / (s[2] + k * lg_poss)
        dfn = (s[1] + k * lg_pts) / (s[2] + k * lg_poss)
        pace = (s[2] + k * lg_poss) / (s[3] + k)
        return {"elo": float(self.elo.get(team)), "ortg": 100.0 * off, "drtg": 100.0 * dfn,
                "net": 100.0 * (off - dfn), "pace": pace, "games": int(s[5]),
                "last_date": s[6]}

    def expected(self, home: int, away: int) -> tuple:
        lg_pts, lg_poss = self._league()
        lg_eff = lg_pts / lg_poss
        h, a = self.team_state(home), self.team_state(away)
        poss = h["pace"] * a["pace"] / lg_poss
        pts_h = poss * (h["ortg"] / 100.0) * (a["drtg"] / 100.0) / lg_eff
        pts_a = poss * (a["ortg"] / 100.0) * (h["drtg"] / 100.0) / lg_eff
        margin_r = pts_h - pts_a + self.p.hca
        margin_elo = (h["elo"] - a["elo"]) / self.p.elo_pts + self.p.hca
        margin = (1.0 - self.p.w_elo) * margin_r + self.p.w_elo * margin_elo
        return margin, pts_h + pts_a

    def forecast(self, home: int, away: int, home_name: str = "Local",
                 away_name: str = "Visitante", points_mult=(1.0, 1.0)) -> Forecast:
        margin, total = self.expected(home, away)
        e_home, e_away = (total + margin) / 2.0, (total - margin) / 2.0
        e_home, e_away = e_home * points_mult[0], e_away * points_mult[1]
        margin, total = e_home - e_away, e_home + e_away
        mk = normal_markets(margin, total, self.p.sigma_margin, self.p.sigma_total)
        p_home = next(m["prob"] for m in mk if m["mercado"] == "Gana local")
        h, a = self.team_state(home), self.team_state(away)
        notes = []
        for nm, st in ((home_name, h), (away_name, a)):
            if st["games"] < 10:
                notes.append(f"{nm}: pocos partidos en la base ({st['games']}); "
                             "el rating está muy encogido hacia la media de la liga.")
        return Forecast(
            sport="basketball", home=home_name, away=away_name, markets=mk,
            win={"home": p_home, "draw": None, "away": 1.0 - p_home},
            expected={"home": e_home, "away": e_away, "unit": "puntos",
                      "margin": margin, "total": total},
            ratings={"home": h, "away": a},
            notes=notes,
            extras={"sigma_margin": self.p.sigma_margin, "sigma_total": self.p.sigma_total,
                    "data_until": self.last_date},
        )

