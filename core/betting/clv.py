"""
Closing Line Value (CLV) — la metrica mas importante para detectar edge real.

CLV mide la diferencia entre la cuota a la que apostaste (odds_taken) y la cuota
a la que cerro el mercado (odds_closing). Si tu modelo es bueno, sus picks tienden
a tener cuotas mejores que el cierre (positive CLV).

Para un mercado eficiente como Pinnacle, el CLV medio sostenido > 0 en 200+ apuestas
es la evidencia mas fuerte de que tu modelo tiene edge real, mas robusta que el ROI
(que tiene varianza enorme en muestras pequenas).

NOTA IMPORTANTE: Para medir CLV con sentido necesitas DOS cuotas distintas para el
MISMO evento — la cuota cuando apostaste y la cuota de cierre. football-data.co.uk
solo da cuotas de cierre, asi que tienes que registrar cuotas de apertura/intermedias
de otra fuente (Bet365 scraping controlado, OddsPortal API, etc.).
"""
import numpy as np


def closing_line_value(odds_taken: float, odds_closing: float) -> float:
    """
    CLV = (odds_taken / odds_closing) - 1

    Positivo: apostaste a una cuota mejor que el cierre (edge real).
    Negativo: el mercado se movio en tu contra (anti-edge o solo mala suerte timing).
    """
    if odds_closing is None or odds_closing <= 1.0:
        return 0.0
    return float(odds_taken) / float(odds_closing) - 1.0


def clv_array(odds_taken_arr, odds_closing_arr):
    """Vectorizado."""
    taken = np.asarray(odds_taken_arr, dtype=float)
    closing = np.asarray(odds_closing_arr, dtype=float)
    closing_safe = np.where(closing > 1.0, closing, np.nan)
    clv = taken / closing_safe - 1.0
    return clv


def clv_summary(odds_taken_arr, odds_closing_arr):
    """
    Devuelve dict con stadisticas del CLV: media, std, # positive, # negative.

    Interpretacion:
        media > +1 % en 200+ picks: edge real probable.
        media en [-0.5 %, +0.5 %]: sin edge claro.
        media < -1 %: anti-edge (modelo apuesta a contracorriente del mercado).
    """
    arr = clv_array(odds_taken_arr, odds_closing_arr)
    arr_clean = arr[~np.isnan(arr)]
    if len(arr_clean) == 0:
        return {"n": 0, "mean": 0.0, "std": 0.0, "n_positive": 0, "n_negative": 0}
    return {
        "n": int(len(arr_clean)),
        "mean": float(arr_clean.mean()),
        "std": float(arr_clean.std()),
        "n_positive": int((arr_clean > 0).sum()),
        "n_negative": int((arr_clean < 0).sum()),
        "median": float(np.median(arr_clean)),
        "p25": float(np.percentile(arr_clean, 25)),
        "p75": float(np.percentile(arr_clean, 75)),
    }


def implied_clv(prob_model: float, odds_closing: float) -> float:
    """
    'CLV implicito': diferencia entre prob de tu modelo y prob implicita del cierre.

    No es CLV puro pero es una proxy util: si tu modelo dice 30 % y la cuota de
    cierre implica 25 %, has detectado un mispricing del mercado.
    """
    if odds_closing is None or odds_closing <= 1.0:
        return 0.0
    implied_prob = 1.0 / float(odds_closing)
    return float(prob_model) - implied_prob
