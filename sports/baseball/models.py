"""
Modelos base para beisbol (MLB).

Implementa:
  - Log5 (Bill James, 1981) para probabilidad cabeza a cabeza
  - Pythagorean expectation (Bill James) para win-rate desde runs
  - Ajuste por starting pitcher via FIP

NO implementa todavia la simulacion Markov por plate appearance ni el
modelado dual starter+bullpen. Esto es scaffolding para Fase 7.
"""


def pythagorean_expectation(runs_scored: float, runs_allowed: float, exp: float = 1.83) -> float:
    """
    Win-rate esperado segun Pythagorean (Bill James, exp 1.83 estandar MLB).

    Returns: win-rate en [0, 1]
    """
    if runs_scored <= 0 and runs_allowed <= 0:
        return 0.5
    rs_e = runs_scored ** exp
    ra_e = runs_allowed ** exp
    return rs_e / (rs_e + ra_e)


def log5(p_a: float, p_b: float) -> float:
    """
    Probabilidad de que A gane vs B (Bill James Log5).
        P(A | A vs B) = (pA - pA*pB) / (pA + pB - 2*pA*pB)

    p_a, p_b: win-rates de cada equipo (idealmente Pythagorean ajustado).
    """
    p_a = max(min(p_a, 0.999), 0.001)
    p_b = max(min(p_b, 0.999), 0.001)
    num = p_a - p_a * p_b
    den = p_a + p_b - 2.0 * p_a * p_b
    if den <= 0:
        return 0.5
    return num / den


def adjust_for_starting_pitcher(team_winrate: float,
                                fip_starter: float,
                                fip_league_avg: float = 4.00) -> float:
    """
    Ajusta el winrate del equipo segun el FIP del pitcher abridor.

    Regla heuristica: cada 0.5 de mejora sobre la media de liga vale ~3 % de winrate.
    Conservador para empezar; se refinara con datos reales.
    """
    fip_delta = fip_league_avg - fip_starter
    adjustment = fip_delta * 0.06
    return max(0.05, min(0.95, team_winrate + adjustment))


def home_advantage_adjustment(winrate: float, hfa: float = 0.04) -> float:
    """Aplica home-field advantage (~4 % en MLB) al winrate."""
    return max(0.05, min(0.95, winrate + hfa))


# Marcadores: scaffolding pendiente de implementar
def estimate_runs_distribution(*args, **kwargs):
    """
    Pendiente: usar binomial negativa o Markov chain por aparicion al bate.
    Ver PROYECTO.md §8.2 (arquitectura dual starter/bullpen).
    """
    raise NotImplementedError(
        "Distribucion de runs pendiente. Ver PROYECTO.md Fase 7."
    )
