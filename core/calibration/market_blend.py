"""
Mezcla bayesiana de probabilidades del modelo con probabilidades implicitas del mercado.

p_blend = alpha * p_model + (1 - alpha) * p_market_implied

Cuando alpha=1.0: confiar 100% en el modelo (puede ser overconfident).
Cuando alpha=0.0: confiar 100% en el mercado (no hay edge, copia al bookie).
Optimo tipico: alpha entre 0.3 y 0.7 segun calidad del modelo.

`fit_alpha` busca el alpha que minimiza log-loss en un set de validacion.
"""
from typing import Optional, Tuple

import numpy as np

from core.evaluation.metrics import log_loss_multiclass


def market_implied_probs_1x2(odds_home, odds_draw, odds_away) -> np.ndarray:
    """Probabilidades implicitas 1X2 normalizadas (sin margen del bookmaker)."""
    raw = np.stack([
        1.0 / np.asarray(odds_home, dtype=float),
        1.0 / np.asarray(odds_draw, dtype=float),
        1.0 / np.asarray(odds_away, dtype=float),
    ], axis=1)
    total = raw.sum(axis=1, keepdims=True)
    return raw / total


def blend_probs(model_probs: np.ndarray,
                market_probs: np.ndarray,
                alpha: float) -> np.ndarray:
    """Mezcla lineal en espacio probabilistico."""
    alpha = max(0.0, min(1.0, float(alpha)))
    blended = alpha * np.asarray(model_probs) + (1 - alpha) * np.asarray(market_probs)
    # Re-normalizar por seguridad (deberia sumar 1 ya, pero...)
    row_sums = blended.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums < 1e-9, 1e-9, row_sums)
    return blended / row_sums


def fit_alpha(model_probs: np.ndarray,
              market_probs: np.ndarray,
              outcomes,
              n_grid: int = 21) -> Tuple[float, float]:
    """
    Busca el alpha optimo en grid search.
    Returns: (alpha_optimo, log_loss_minimo).
    """
    grid = np.linspace(0.0, 1.0, n_grid)
    best_alpha, best_ll = 0.5, float("inf")
    for a in grid:
        blended = blend_probs(model_probs, market_probs, a)
        ll = log_loss_multiclass(blended, outcomes)
        if ll < best_ll:
            best_ll = ll
            best_alpha = float(a)
    return best_alpha, float(best_ll)
