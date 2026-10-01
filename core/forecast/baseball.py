from dataclasses import dataclass

import pandas as pd

from core.forecast.base import Forecast, season_of
from sports.baseball.elo import BaseballEloSystem
from sports.baseball.markets import DISPERSION_R, TIE_HOME, all_markets
from sports.baseball.park_factors import park_factor

SEASON_START_MONTH = 3


def _fip(v) -> str:
    return f"{v:.2f}" if v else "s/d"


@dataclass(frozen=True)
class MLBParams:
    decay: float = 0.995
    prior_games: float = 10.0
    season_carry: float = 0.5
    league_decay: float = 0.999
    hfa: float = 1.07
    dispersion_r: float = DISPERSION_R
    tie_home: float = TIE_HOME
    use_park: bool = True


def load_games(engine) -> pd.DataFrame:
    return pd.read_sql(
        """
        SELECT g.id, g.date, g.home_team_id, g.away_team_id, g.home_runs, g.away_runs,
               e.name AS home_name
        FROM baseball_games g
        JOIN entities e ON e.id = g.home_team_id
        WHERE g.home_runs IS NOT NULL AND g.away_runs IS NOT NULL
        ORDER BY g.date, g.id
        """,
        engine, parse_dates=["date"],
    )


class MLBForecaster:
    def __init__(self, params: MLBParams | None = None, park_of=None):
        self.p = params or MLBParams()
        self.elo = BaseballEloSystem()
        self._t: dict = {}
        self._lg = [0.0, 0.0]
        self._park_of = park_of or {}
        self.last_date = None
        self.n_games = 0

    @classmethod
    def from_games(cls, df: pd.DataFrame, params: MLBParams | None = None) -> "MLBForecaster":
        parks = {int(t): park_factor(n) for t, n in zip(df["home_team_id"], df["home_name"])}
        f = cls(params, parks)
        cols = ["date", "home_team_id", "away_team_id", "home_runs", "away_runs"]
        for d, h, a, hr, ar in df[cols].itertuples(index=False, name=None):
            f.update(d, int(h), int(a), float(hr), float(ar))
        return f

    def pf(self, home: int) -> float:
        return self._park_of.get(home, 1.0) if self.p.use_park else 1.0

    def league_rpg(self) -> float:
        runs, w = self._lg
        return runs / w if w > 0 else 4.5

    def _roll_season(self, team: int, season: int) -> list:
        s = self._t.get(team)
        if s is None:
            s = [0.0, 0.0, 0.0, season, 0, None]
            self._t[team] = s
        elif s[3] != season:
            c = self.p.season_carry
            s[0], s[1], s[2] = s[0] * c, s[1] * c, s[2] * c
            s[3] = season
        return s

    def update(self, date, home: int, away: int, home_runs: float, away_runs: float) -> None:
        season = season_of(date, SEASON_START_MONTH)
        self.elo.process_game(date, str(season), home, away, int(home_runs), int(away_runs))
        pf = self.pf(home)
        # Carreras de estadio neutral: evita contar dos veces el park factor.
        hn, an = home_runs / pf, away_runs / pf
        d = self.p.decay
        for team, rs, ra in ((home, hn, an), (away, an, hn)):
            s = self._roll_season(team, season)
            s[0] = s[0] * d + rs
            s[1] = s[1] * d + ra
            s[2] = s[2] * d + 1.0
            s[4] += 1
            s[5] = date
        ld = self.p.league_decay
        self._lg[0] = self._lg[0] * ld + (hn + an) / 2.0
        self._lg[1] = self._lg[1] * ld + 1.0
        self.last_date = date
        self.n_games += 1

    def team_state(self, team: int) -> dict:
        lg = self.league_rpg()
        k = self.p.prior_games
        s = self._t.get(team, [0.0, 0.0, 0.0, None, 0, None])
        rs = (s[0] + k * lg) / (s[2] + k)
        ra = (s[1] + k * lg) / (s[2] + k)
        return {"elo": float(self.elo.get(team)), "rs": rs, "ra": ra, "games": int(s[4]),
                "last_date": s[5], "park": self._park_of.get(team, 1.0)}

    def expected(self, home: int, away: int) -> tuple:
        lg = self.league_rpg()
        h, a = self.team_state(home), self.team_state(away)
        pf = self.pf(home)
        e_home = h["rs"] * a["ra"] / lg * pf * self.p.hfa
        e_away = a["rs"] * h["ra"] / lg * pf
        return max(0.3, e_home), max(0.3, e_away)

    def forecast(self, home: int, away: int, home_name: str = "Local",
                 away_name: str = "Visitante", starter_fips=(None, None),
                 runs_mult=(1.0, 1.0)) -> Forecast:
        from sports.baseball.starter_adjustment import adjust_runs

        e_home, e_away = self.expected(home, away)
        notes = []
        hf, af = starter_fips
        if hf is not None or af is not None:
            e_home, e_away = adjust_runs(e_home, e_away, hf, af)
            notes.append("Carreras ajustadas por abridor probable (FIP): local "
                         f"{_fip(hf)} · visitante {_fip(af)}.")
        e_home, e_away = e_home * runs_mult[0], e_away * runs_mult[1]
        mk = all_markets(e_home, e_away, dispersion=self.p.dispersion_r,
                         tie_home=self.p.tie_home)
        p_home = next(m["prob"] for m in mk if m["mercado"] == "Gana local")
        h, a = self.team_state(home), self.team_state(away)
        pf = self.pf(home)
        if abs(pf - 1.0) >= 0.02:
            notes.append(f"Estadio de {home_name}: factor de carreras ×{pf:.2f}.")
        for nm, st in ((home_name, h), (away_name, a)):
            if st["games"] < 20:
                notes.append(f"{nm}: {st['games']} partidos en la base; rating encogido "
                             "hacia la media de la liga.")
        return Forecast(
            sport="baseball", home=home_name, away=away_name, markets=mk,
            win={"home": p_home, "draw": None, "away": 1.0 - p_home},
            expected={"home": e_home, "away": e_away, "unit": "carreras",
                      "total": e_home + e_away},
            ratings={"home": h, "away": a},
            notes=notes,
            extras={"park_factor": pf, "dispersion_r": self.p.dispersion_r,
                    "data_until": self.last_date},
        )
