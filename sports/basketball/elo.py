from dataclasses import dataclass, field
from datetime import date as _date
from typing import Iterator, Tuple


DEFAULT_ELO = 1500.0
K_FACTOR = 22.0
HOME_ADVANTAGE = 100.0
SEASON_REGRESSION = 0.25


def expected_home_score(elo_home: float, elo_away: float,
                        home_advantage: float = HOME_ADVANTAGE) -> float:
    diff = (elo_away - elo_home - home_advantage) / 400.0
    return 1.0 / (1.0 + 10.0 ** diff)


def _mov_multiplier(home_score: int, away_score: int, elo_diff: float) -> float:
    import math
    mov = abs(home_score - away_score)
    favored_diff = elo_diff if home_score > away_score else -elo_diff
    numerator = math.log(mov + 1.0) * 2.2
    denominator = favored_diff * 0.001 + 2.2
    return numerator / max(denominator, 1.0)


def update_elos(elo_home: float, elo_away: float,
                home_score: int, away_score: int,
                k: float = K_FACTOR,
                home_advantage: float = HOME_ADVANTAGE,
                use_mov: bool = True) -> Tuple[float, float]:
    expected = expected_home_score(elo_home, elo_away, home_advantage)
    actual = 1.0 if home_score > away_score else 0.0

    if use_mov:
        mult = _mov_multiplier(home_score, away_score, elo_home - elo_away)
    else:
        mult = 1.0

    delta = k * mult * (actual - expected)
    return elo_home + delta, elo_away - delta


@dataclass
class BasketballEloSystem:
    default_elo: float = DEFAULT_ELO
    k: float = K_FACTOR
    home_advantage: float = HOME_ADVANTAGE
    season_regression: float = SEASON_REGRESSION
    use_mov: bool = True

    _current: dict = field(default_factory=dict, init=False)
    _last_season: dict = field(default_factory=dict, init=False)
    _history: list = field(default_factory=list, init=False)

    def get(self, team_id: int) -> float:
        return self._current.get(team_id, self.default_elo)

    def _apply_season_regression(self, team_id: int, season: str) -> None:
        last = self._last_season.get(team_id)
        if last is not None and last != season:
            current = self._current.get(team_id, self.default_elo)
            self._current[team_id] = current - self.season_regression * (current - self.default_elo)
        self._last_season[team_id] = season

    def process_game(self, game_date: _date, season: str,
                     home_id: int, away_id: int,
                     home_score: int, away_score: int) -> None:
        self._apply_season_regression(home_id, season)
        self._apply_season_regression(away_id, season)

        eh = self.get(home_id)
        ea = self.get(away_id)

        new_h, new_a = update_elos(
            eh, ea, home_score, away_score,
            k=self.k,
            home_advantage=self.home_advantage,
            use_mov=self.use_mov,
        )
        self._current[home_id] = new_h
        self._current[away_id] = new_a

        self._history.append((home_id, game_date, new_h))
        self._history.append((away_id, game_date, new_a))

    def history(self) -> Iterator[Tuple[int, _date, float]]:
        yield from self._history
