"""
Simulacion Monte Carlo para baloncesto (NBA).

En lugar de Poisson (goles), usamos distribuciones NORMALES para el marcador.
La desviacion tipica de un marcador NBA es ~11-12 puntos.

Entrada: Elo local, Elo visitante, media total esperada, desv tipica.
Salida: probabilidades moneyline (ML), spread y total (Over/Under).

La formula base para puntos esperados:
    E_home = total_medio/2 + ventaja_elo_convertida_a_puntos/2 + home_advantage_pts/2
    E_away = total_medio/2 - ventaja_elo_convertida_a_puntos/2 - home_advantage_pts/2

Conversion Elo -> puntos:
    1 punto real ~= 28 puntos Elo (calibrado empiricamente en NBA).
"""
import numpy as np


DEFAULT_N_SIMS = 10_000
DEFAULT_SIGMA_TEAM = 11.0          # desviacion tipica del marcador de un equipo
ELO_POINTS_PER_REAL_POINT = 28.0   # 1 punto NBA ~ 28 pts Elo
HOME_ADVANTAGE_PTS = 2.5            # ventaja de local en puntos reales


def expected_scores(elo_home: float, elo_away: float,
                    total_mean: float = 225.0,
                    home_advantage_pts: float = HOME_ADVANTAGE_PTS) -> tuple:
    """
    Calcula score esperado H/A dadas fuerzas Elo y total medio de la liga.
    """
    elo_diff = elo_home - elo_away
    point_spread = elo_diff / ELO_POINTS_PER_REAL_POINT + home_advantage_pts
    E_home = total_mean / 2.0 + point_spread / 2.0
    E_away = total_mean / 2.0 - point_spread / 2.0
    return float(E_home), float(E_away)


def simulate_game(elo_home: float, elo_away: float,
                  total_mean: float = 225.0,
                  sigma: float = DEFAULT_SIGMA_TEAM,
                  n_sims: int = DEFAULT_N_SIMS,
                  rng=None) -> tuple:
    """
    Simula n_sims marcadores Normales independientes.
    Devuelve (home_scores, away_scores) como arrays.
    """
    if rng is None:
        rng = np.random.default_rng()
    E_home, E_away = expected_scores(elo_home, elo_away, total_mean)
    home_scores = rng.normal(E_home, sigma, size=n_sims)
    away_scores = rng.normal(E_away, sigma, size=n_sims)
    return home_scores, away_scores


def probabilities_from_sims(home_scores, away_scores,
                            spread: float = 0.0,
                            total_line: float = 225.0) -> dict:
    """
    Extrae probabilidades de los mercados principales NBA.

    spread: linea del hdcap (puntos que recibe el local, por convención si local
            favorito y spread = -5, entonces "home -5" gana si home_score - away_score > 5)
    total_line: linea de total (Over/Under)
    """
    diff = home_scores - away_scores
    total = home_scores + away_scores

    return {
        "prob_ml_home":  float((diff > 0).mean()),
        "prob_ml_away":  float((diff < 0).mean()),
        "prob_tie":      float((diff == 0).mean()),  # raro en NBA (OT)
        "prob_spread_home_cover": float((diff > spread).mean()),
        "prob_over":     float((total > total_line).mean()),
        "prob_under":    float((total < total_line).mean()),
        "mean_home":     float(home_scores.mean()),
        "mean_away":     float(away_scores.mean()),
        "mean_total":    float(total.mean()),
        "mean_spread":   float(diff.mean()),
    }


def simulate_and_probabilities(elo_home: float, elo_away: float,
                               total_mean: float = 225.0,
                               sigma: float = DEFAULT_SIGMA_TEAM,
                               n_sims: int = DEFAULT_N_SIMS,
                               spread: float = 0.0,
                               total_line: float = 225.0,
                               rng=None) -> dict:
    """Convenience: simula y devuelve probabilidades listas."""
    h, a = simulate_game(elo_home, elo_away, total_mean, sigma, n_sims, rng)
    return probabilities_from_sims(h, a, spread=spread, total_line=total_line)
