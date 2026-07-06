"""
Modelo Barnett-Clarke (2005) para probabilidad de ganar un partido de tenis
a partir de los porcentajes de puntos ganados al saque (SPW) y al resto (RPW).

Formula clave (probabilidad de ganar un juego al saque dada p = SPW):

    P_game(p) = p^4 * (15 - 34p + 28p^2 - 8p^3) / (1 - 2p + 2p^2)

Esta es la solucion analitica de la cadena de Markov del juego de tenis,
asumiendo independencia entre puntos.

Probabilidad de ganar un set: convolucion de prob de ganar juegos al saque
y al resto. Probabilidad de ganar el partido: best of 3 vs best of 5.
"""
from typing import Tuple


def prob_win_game_on_serve(p_serve: float) -> float:
    """
    Probabilidad de ganar un juego al saque dada SPW = p.

    Formula cerrada de la Markov chain del juego (incluye deuce resuelto).
    """
    p = max(min(p_serve, 0.99), 0.01)
    numerator = p ** 4 * (15 - 34 * p + 28 * p ** 2 - 8 * p ** 3)
    denominator = 1 - 2 * p + 2 * p ** 2
    if denominator <= 0:
        return 0.5
    return max(0.0, min(1.0, numerator / denominator))


def prob_win_set(p_serve: float, p_return: float) -> float:
    """
    Probabilidad de ganar un set dado SPW y RPW.

    Implementacion simplificada: suma binomial sobre las distribuciones
    de juegos ganados al saque y al resto en 6 juegos cada uno + tiebreak.

    Para precision exacta usar la cadena de Markov completa del set.
    """
    g_serve = prob_win_game_on_serve(p_serve)
    g_return = prob_win_game_on_serve(p_return)  # mismo formula con p_return como SPW del oponente desde nuestro punto

    # Aproximacion: probabilidad media de ganar un juego en 12 juegos
    avg_g = (g_serve + g_return) / 2.0

    # Probabilidad de ganar un set por mayoria simple (al menos 6 de 10)
    # esto es una aproximacion razonable; la formula exacta es mas larga
    from scipy.stats import binom
    return float(1 - binom.cdf(5, 10, avg_g))


def prob_win_match(p_serve: float, p_return: float, best_of: int = 3) -> float:
    """
    Probabilidad de ganar el partido.

    best_of = 3 (ATP/WTA regular) o 5 (Grand Slam masculino).
    """
    p_set = prob_win_set(p_serve, p_return)
    sets_to_win = (best_of + 1) // 2  # 2 para BO3, 3 para BO5

    # Distribucion negativo binomial: prob de ganar `sets_to_win` antes de perder `sets_to_win`
    from scipy.stats import binom
    # Ganamos el partido si ganamos al menos `sets_to_win` de los primeros `best_of` sets
    return float(1 - binom.cdf(sets_to_win - 1, best_of, p_set))


def estimate_serve_return_from_elo(elo_a: float, elo_b: float,
                                   surface_avg_spw: float = 0.62) -> Tuple[float, float]:
    """
    Estima SPW y RPW del jugador A vs B a partir de la diferencia de Elo.

    Heuristica: cada 100 puntos Elo de ventaja vale ~2 % de SPW adicional.
    Surface average SPW ~ 0.62 (hard), 0.59 (clay), 0.66 (grass).
    """
    elo_diff_norm = (elo_a - elo_b) / 100.0
    # SPW de A: media de superficie + ajuste por elo
    spw_a = surface_avg_spw + elo_diff_norm * 0.01
    # RPW de A vs B = 1 - SPW de B vs A
    spw_b = surface_avg_spw - elo_diff_norm * 0.01
    rpw_a = 1.0 - spw_b
    return max(0.30, min(0.90, spw_a)), max(0.10, min(0.70, rpw_a))
