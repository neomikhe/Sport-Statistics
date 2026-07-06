"""
Motor de Elo dinamico para futbol de clubes.

Convenciones:
    - Elo inicial: 1500 para equipos nuevos.
    - K-factor: 20 (estandar para club football).
    - Home advantage: 100 puntos Elo (estandar).
    - Multiplicador por diferencia de goles al estilo Elo World Football.
    - Regresion a la media al inicio de temporada (configurable).

Uso tipico:
    elo = EloSystem()
    for match in sorted(matches, key=lambda m: m.date):
        elo.process_match(match.date, match.season,
                          match.home_id, match.away_id,
                          match.home_goals, match.away_goals)
    snapshots = list(elo.history())   # (team_id, date, elo_post_match)
"""
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Iterator, Tuple


DEFAULT_ELO = 1500.0
K_FACTOR = 20.0
HOME_ADVANTAGE = 100.0
SEASON_REGRESSION = 0.33


def expected_home_score(elo_home: float, elo_away: float,
                        home_advantage: float = HOME_ADVANTAGE) -> float:
    """
    Probabilidad esperada del local en un marco Elo binario (victoria=1, empate=0.5, derrota=0).
    No es probabilidad 1X2 — eso requiere modelo de goles aparte.
    """
    diff = (elo_away - elo_home - home_advantage) / 400.0
    return 1.0 / (1.0 + 10.0 ** diff)


def _actual_home_score(home_goals: int, away_goals: int) -> float:
    if home_goals > away_goals:
        return 1.0
    if home_goals == away_goals:
        return 0.5
    return 0.0


def _goal_diff_multiplier(home_goals: int, away_goals: int) -> float:
    """Multiplicador Elo World Football: escala el delta segun margen."""
    diff = abs(home_goals - away_goals)
    if diff <= 1:
        return 1.0
    if diff == 2:
        return 1.5
    if diff == 3:
        return 1.75
    return 1.75 + (diff - 3) * 0.25


def update_elos(elo_home: float, elo_away: float,
                home_goals: int, away_goals: int,
                k: float = K_FACTOR,
                home_advantage: float = HOME_ADVANTAGE,
                use_gd_multiplier: bool = True) -> Tuple[float, float]:
    """Devuelve (elo_home_post, elo_away_post)."""
    expected = expected_home_score(elo_home, elo_away, home_advantage)
    actual = _actual_home_score(home_goals, away_goals)
    mult = _goal_diff_multiplier(home_goals, away_goals) if use_gd_multiplier else 1.0
    delta = k * mult * (actual - expected)
    return elo_home + delta, elo_away - delta


@dataclass
class EloSystem:
    """
    Acumulador Elo con regresion a la media entre temporadas.

    Guarda snapshot POST-partido para cada equipo. Para obtener el Elo
    PRE-partido de un evento en fecha X, consultar el snapshot previo
    (SELECT ... WHERE team_id = X AND date < match_date ORDER BY date DESC LIMIT 1).
    """
    default_elo: float = DEFAULT_ELO
    k: float = K_FACTOR
    home_advantage: float = HOME_ADVANTAGE
    season_regression: float = SEASON_REGRESSION
    use_gd_multiplier: bool = True

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

    def process_match(self, match_date: _date, season: str,
                      home_id: int, away_id: int,
                      home_goals: int, away_goals: int) -> None:
        self._apply_season_regression(home_id, season)
        self._apply_season_regression(away_id, season)

        eh = self.get(home_id)
        ea = self.get(away_id)

        new_h, new_a = update_elos(
            eh, ea, home_goals, away_goals,
            k=self.k,
            home_advantage=self.home_advantage,
            use_gd_multiplier=self.use_gd_multiplier,
        )
        self._current[home_id] = new_h
        self._current[away_id] = new_a

        self._history.append((home_id, match_date, new_h))
        self._history.append((away_id, match_date, new_a))

    def history(self) -> Iterator[Tuple[int, _date, float]]:
        yield from self._history
