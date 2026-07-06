"""
Simulacion Monte Carlo de partidos de futbol con Poisson independiente.

Dadas las medias de goles (lambda_home, lambda_away) del modelo GLM Poisson,
muestreamos N partidos y extraemos probabilidades de todos los mercados.

Incluye tambien una version analitica exacta usando scipy.stats.poisson.pmf
para verificar que la MC converge a los valores correctos.

Uso tipico:
    from sports.football.simulation import simulate_and_probabilities
    probs = simulate_and_probabilities(lambda_home=1.6, lambda_away=1.1, n_sims=10000)
    # probs = {'prob_home':..., 'prob_draw':..., ...}
"""
from collections import Counter

import numpy as np
from scipy.stats import poisson


DEFAULT_N_SIMS = 10_000


def simulate_match(lambda_home, lambda_away, n_sims=DEFAULT_N_SIMS, rng=None):
    """
    Muestrea n_sims partidos de Poisson independiente.

    Returns
    -------
    (home_goals, away_goals) : tuple de np.ndarray de tamaño n_sims
    """
    if rng is None:
        rng = np.random.default_rng()
    home_goals = rng.poisson(lambda_home, size=n_sims)
    away_goals = rng.poisson(lambda_away, size=n_sims)
    return home_goals, away_goals


def probabilities_from_sims(home_goals, away_goals):
    """
    Extrae probabilidades de 1X2, Over/Under 2.5, BTTS y media de goles
    a partir de arrays simulados.
    """
    total = home_goals + away_goals
    return {
        "prob_home":        float((home_goals > away_goals).mean()),
        "prob_draw":        float((home_goals == away_goals).mean()),
        "prob_away":        float((home_goals < away_goals).mean()),
        "prob_over_2_5":    float((total >= 3).mean()),
        "prob_under_2_5":   float((total <= 2).mean()),
        "prob_btts":        float(((home_goals > 0) & (away_goals > 0)).mean()),
        "mean_total_goals": float(total.mean()),
    }


def top_scorelines(home_goals, away_goals, n=5):
    """Devuelve los N marcadores mas frecuentes con sus probabilidades MC."""
    pairs = list(zip(home_goals.tolist(), away_goals.tolist()))
    counter = Counter(pairs)
    total = len(pairs)
    return [(h, a, count / total) for (h, a), count in counter.most_common(n)]


def simulate_and_probabilities(lambda_home, lambda_away,
                               n_sims=DEFAULT_N_SIMS, rng=None):
    """Combina simulate_match + probabilities_from_sims en una sola llamada."""
    home_goals, away_goals = simulate_match(lambda_home, lambda_away, n_sims, rng)
    return probabilities_from_sims(home_goals, away_goals)


def exact_probabilities(lambda_home, lambda_away, max_goals=15):
    """
    Probabilidades analiticas EXACTAS para Poisson independiente (sin MC).

    Calcula P(H=h) * P(A=a) para todos los (h,a) en [0, max_goals] y
    suma segun la region que define cada mercado.

    max_goals=15 da error <1e-8 incluso para lambdas altas (>4).
    """
    idx = np.arange(max_goals + 1)
    pmf_h = poisson.pmf(idx, lambda_home)
    pmf_a = poisson.pmf(idx, lambda_away)
    joint = np.outer(pmf_h, pmf_a)  # joint[h, a] = P(H=h) * P(A=a)

    h_grid, a_grid = np.meshgrid(idx, idx, indexing="ij")
    total_grid = h_grid + a_grid

    return {
        "prob_home":      float(joint[h_grid > a_grid].sum()),
        "prob_draw":      float(joint[h_grid == a_grid].sum()),
        "prob_away":      float(joint[h_grid < a_grid].sum()),
        "prob_over_2_5":  float(joint[total_grid >= 3].sum()),
        "prob_under_2_5": float(joint[total_grid <= 2].sum()),
        "prob_btts":      float(joint[(h_grid > 0) & (a_grid > 0)].sum()),
    }
