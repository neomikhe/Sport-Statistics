from dataclasses import dataclass

import pandas as pd

from core.forecast.base import Forecast
from sports.tennis.markets import all_markets, match_prob, p_set_from_match

SURFACES = ("hard", "clay", "grass")
DEFAULT_ELO = 1500.0


@dataclass(frozen=True)
class TennisParams:
    k_num: float = 150.0
    k_offset: float = 5.0
    k_shape: float = 0.4
    w_surface: float = 0.25
    bo5_adjust: bool = True


def load_matches(engine) -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT id, date, surface, best_of, player1_id, player2_id, winner_id
        FROM tennis_matches
        WHERE winner_id IS NOT NULL
        ORDER BY date, id
        """,
        engine, parse_dates=["date"],
    )
    df["surface"] = df["surface"].astype(str).str.lower().str.strip()
    return df


# Convierte BO3 a BO5 a través de la probabilidad de ganar un set.
def format_adjust(p_bo3: float, best_of: int) -> float:
    if int(best_of) != 5:
        return p_bo3
    return match_prob(p_set_from_match(p_bo3, best_of=3), best_of=5)


class TennisForecaster:
    def __init__(self, params: TennisParams | None = None):
        self.p = params or TennisParams()
        self._elo: dict = {}
        self._n: dict = {}
        self._last: dict = {}
        self.last_date = None
        self.n_matches = 0

    @classmethod
    def from_matches(cls, df: pd.DataFrame, params: TennisParams | None = None):
        f = cls(params)
        cols = ["date", "surface", "player1_id", "player2_id", "winner_id"]
        for d, s, p1, p2, w in df[cols].itertuples(index=False, name=None):
            f.update(d, s, int(p1), int(p2), int(w))
        return f

    # K dinámico: menos reactivo cuanto más historial.
    def _k(self, key) -> float:
        return self.p.k_num / (self._n.get(key, 0) + self.p.k_offset) ** self.p.k_shape

    def rating(self, player: int, surface: str | None = None) -> float:
        return self._elo.get((player, surface or "all"), DEFAULT_ELO)

    def blended(self, player: int, surface: str) -> float:
        w = self.p.w_surface if surface in SURFACES else 0.0
        return w * self.rating(player, surface) + (1.0 - w) * self.rating(player)

    def prob(self, a: int, b: int, surface: str, best_of: int = 3) -> float:
        diff = self.blended(a, surface) - self.blended(b, surface)
        p = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
        return format_adjust(p, best_of) if self.p.bo5_adjust else p

    def update(self, date, surface: str, p1: int, p2: int, winner: int) -> None:
        s1 = 1.0 if winner == p1 else 0.0
        for key in ("all", surface) if surface in SURFACES else ("all",):
            r1, r2 = self.rating(p1, key), self.rating(p2, key)
            e1 = 1.0 / (1.0 + 10.0 ** ((r2 - r1) / 400.0))
            k1, k2 = self._k((p1, key)), self._k((p2, key))
            self._elo[(p1, key)] = r1 + k1 * (s1 - e1)
            self._elo[(p2, key)] = r2 + k2 * (e1 - s1)
            self._n[(p1, key)] = self._n.get((p1, key), 0) + 1
            self._n[(p2, key)] = self._n.get((p2, key), 0) + 1
        self._last[p1] = self._last[p2] = date
        self.last_date = date
        self.n_matches += 1

    def player_state(self, player: int) -> dict:
        return {
            "elo": self.rating(player),
            "surfaces": {s: self.rating(player, s) for s in SURFACES
                         if (player, s) in self._elo},
            "matches": self._n.get((player, "all"), 0),
            "surface_matches": {s: self._n.get((player, s), 0) for s in SURFACES},
            "last_date": self._last.get(player),
        }

    def forecast(self, a: int, b: int, surface: str, best_of: int = 3,
                 name_a: str = "Jugador 1", name_b: str = "Jugador 2",
                 elo_penalty=(0.0, 0.0)) -> Forecast:
        surface = str(surface).lower()
        diff = (self.blended(a, surface) - elo_penalty[0]) - (self.blended(b, surface) - elo_penalty[1])
        p_bo3 = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
        p = format_adjust(p_bo3, best_of) if self.p.bo5_adjust else p_bo3
        p_set = p_set_from_match(p, best_of=int(best_of))
        mk = all_markets(p_set, best_of=int(best_of), name_a=name_a, name_b=name_b)
        sa, sb = self.player_state(a), self.player_state(b)
        notes = []
        for nm, st in ((name_a, sa), (name_b, sb)):
            n_s = st["surface_matches"].get(surface, 0)
            if st["matches"] < 15:
                notes.append(f"{nm}: solo {st['matches']} partidos en la base; rating poco fiable.")
            elif n_s < 5:
                notes.append(f"{nm}: {n_s} partidos en {surface}; pesa más su Elo general.")
        return Forecast(
            sport="tennis", home=name_a, away=name_b, markets=mk,
            win={"home": p, "draw": None, "away": 1.0 - p},
            expected={"home": p_set, "away": 1.0 - p_set, "unit": "P(set)"},
            ratings={"home": sa, "away": sb},
            notes=notes,
            extras={"surface": surface, "best_of": int(best_of), "p_set": p_set,
                    "blended": (self.blended(a, surface), self.blended(b, surface)),
                    "data_until": self.last_date},
        )

