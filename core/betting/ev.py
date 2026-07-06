"""
Expected Value (EV) para apuestas deportivas.

EV = prob_real * cuota_decimal - 1

Interpretacion:
    EV > 0 -> apuesta con valor (a largo plazo gana dinero)
    EV = 0 -> apuesta justa (breakeven)
    EV < 0 -> apuesta perdedora a largo plazo

NOTA: EV se calcula con la probabilidad "real" (estimada por tu modelo), no con
la probabilidad implicita de la cuota.
"""
import numpy as np


def expected_value(prob, odds):
    """EV de una apuesta individual (escalar)."""
    return float(prob) * float(odds) - 1.0


def ev_array(probs, odds):
    """EV vectorizado."""
    return np.asarray(probs, dtype=float) * np.asarray(odds, dtype=float) - 1.0


def implied_from_odds(odds):
    """Probabilidad implicita cruda (sin quitar margen)."""
    return 1.0 / float(odds)


def edge(prob_model, odds):
    """
    'Edge' = prob_modelo - prob_implicita_cruda.
    Util para ver si el modelo discrepa del mercado en la misma direccion del EV.
    """
    return float(prob_model) - 1.0 / float(odds)
