from dataclasses import dataclass, field
from datetime import date as _date
from typing import Iterator, Tuple


DEFAULT_ELO = 1500.0
K_FACTOR = 4.0
HOME_ADVANTAGE = 24.0
SEASON_REGRESSION = 0.30


def expected_home_score(elo_home: float, elo_away: float,
                        home_advantage: float = HOME_ADVANTAGE) -> float:
    diff = (elo_away - elo_home - home_advantage) / 400.0
    return 1.0 / (1.0 + 10.0 ** diff)


def _run_diff_multiplier(home_runs: int, away_runs: int) -> float:
    diff = abs(home_runs - away_runs)
    if diff <= 1:
        return 1.0
    if diff <= 3:
        return 1.0 + (diff - 1) * 0.15
    return 1.3 + (diff - 3) * 0.05


def update_elos(elo_home: float, elo_away: float,
                home_runs: int, away_runs: int,
                k: float = K_FACTOR,
                home_advantage: float = HOME_ADVANTAGE,
                use_run_diff: bool = True) -> Tuple[float, float]:
    expected = expected_home_score(elo_home, elo_away, home_advantage)
    actual = 1.0 if home_runs > away_runs else 0.0
    mult = _run_diff_multiplier(home_runs, away_runs) if use_run_diff else 1.0
    delta = k * mult * (actual - expected)
    return elo_home + delta, elo_away - delta


@dataclass
class BaseballEloSystem:
    default_elo: float = DEFAULT_ELO
    k: float = K_FACTOR
    home_advantage: float = HOME_ADVANTAGE
    season_regression: float = SEASON_REGRESSION
    use_run_diff: bool = True

    _current: dict = field(default_factory=dict, init=False)
    _last_season: dict = field(default_factory=dict, init=False)
    _history: list = field(default_factory=list, init=False)

    def get(self, team_id: int) -> float:
        return self._current.get(team_id, self.default_elo)

    def _apply_season_regression(self, team_id: int, season: str) -> None:
        last = self._last_season.get(team_id)
        if last is not None and last != season:
            cur = self._current.get(team_id, self.default_elo)
            self._current[team_id] = cur - self.season_regression * (cur - self.default_elo)
        self._last_season[team_id] = season

    def process_game(self, game_date: _date, season: str,
                     home_id: int, away_id: int,
                     home_runs: int, away_runs: int) -> None:
        self._apply_season_regression(home_id, season)
        self._apply_season_regression(away_id, season)

        eh = self.get(home_id)
        ea = self.get(away_id)
        new_h, new_a = update_elos(
            eh, ea, home_runs, away_runs,
            k=self.k, home_advantage=self.home_advantage,
            use_run_diff=self.use_run_diff,
        )
        self._current[home_id] = new_h
        self._current[away_id] = new_a
        self._history.append((home_id, game_date, new_h))
        self._history.append((away_id, game_date, new_a))

    def history(self) -> Iterator[Tuple[int, _date, float]]:
        yield from self._history
