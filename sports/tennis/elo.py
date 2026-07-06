"""
Elo por superficie para tenis (ATP/WTA).

A diferencia del futbol y baloncesto:
  - Deporte INDIVIDUAL: la entidad es el jugador, no el equipo
  - Cuatro Elos separados por superficie: hard, clay, grass, carpet
  - Tambien un Elo "general" agregando todas las superficies
  - K-factor mas alto en superficies con menos partidos

Conversion Elo -> probabilidad:
    P(A) = 1 / (1 + 10^((Elo_B - Elo_A) / 400))

NO hay home advantage en tenis (excepto Davis/Billie Jean Cup, edge case).
"""
from dataclasses import dataclass, field
from typing import Iterator, Tuple


SURFACES = ["hard", "clay", "grass", "carpet"]
DEFAULT_ELO = 1500.0
K_FACTOR_DEFAULT = 32.0  # tenis tipico (ITF, FiveThirtyEight)


def expected_score(elo_a: float, elo_b: float) -> float:
    """Probabilidad de que A gane (sin home advantage)."""
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def update_elos(elo_a: float, elo_b: float, a_won: bool, k: float = K_FACTOR_DEFAULT) -> Tuple[float, float]:
    """Actualiza Elos despues de un partido. a_won=True si gana A."""
    expected_a = expected_score(elo_a, elo_b)
    actual_a = 1.0 if a_won else 0.0
    delta = k * (actual_a - expected_a)
    return elo_a + delta, elo_b - delta


@dataclass
class TennisEloSystem:
    """
    Almacena Elo por (jugador, superficie). Tambien mantiene un Elo general.

    Estado:
        _elo[(player_id, surface)] -> rating
        _elo[(player_id, "all")]   -> rating general (todas las superficies)
    """
    default_elo: float = DEFAULT_ELO
    k: float = K_FACTOR_DEFAULT
    _elo: dict = field(default_factory=dict, init=False)
    _history: list = field(default_factory=list, init=False)

    def get(self, player_id: int, surface: str) -> float:
        return self._elo.get((player_id, surface), self.default_elo)

    def get_general(self, player_id: int) -> float:
        return self._elo.get((player_id, "all"), self.default_elo)

    def process_match(self, match_date, surface: str,
                      player1_id: int, player2_id: int,
                      winner_id: int) -> None:
        if surface not in SURFACES:
            return  # superficie desconocida, no actualizamos

        e1_surface = self.get(player1_id, surface)
        e2_surface = self.get(player2_id, surface)
        e1_general = self.get_general(player1_id)
        e2_general = self.get_general(player2_id)

        p1_won = (winner_id == player1_id)

        new1_s, new2_s = update_elos(e1_surface, e2_surface, p1_won, k=self.k)
        new1_g, new2_g = update_elos(e1_general, e2_general, p1_won, k=self.k)

        self._elo[(player1_id, surface)] = new1_s
        self._elo[(player2_id, surface)] = new2_s
        self._elo[(player1_id, "all")] = new1_g
        self._elo[(player2_id, "all")] = new2_g

        # Snapshot para tabla tennis_elo
        self._history.append((player1_id, match_date, surface, new1_s))
        self._history.append((player2_id, match_date, surface, new2_s))

    def history(self) -> Iterator[Tuple[int, object, str, float]]:
        yield from self._history
