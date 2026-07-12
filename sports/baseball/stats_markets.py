"""
Mercados de hits, jonrones y ponches de MLB — modelo Poisson sobre tasas de equipo.

El equivalente en béisbol a los córners del fútbol: se modelan aparte de las carreras.
Hits y ponches por equipo rondan 8-9; jonrones ~1.2. Las líneas se generan dinámicamente
alrededor del total esperado para que las situaciones sean informativas.

Funciones PURAS: reciben los valores esperados y devuelven {grupo, mercado, prob, aprox}.
"""
from scipy.stats import poisson

from core.markets import straddling_lines


def _over_under(grupo, prefijo, mean, lines, unidad):
    out = []
    for line in lines:
        p_over = float(poisson.sf(int(line), max(0.1, mean)))
        out.append((grupo, f"{prefijo}más de {line:.1f} {unidad}", p_over))
        out.append((grupo, f"{prefijo}menos de {line:.1f} {unidad}", 1.0 - p_over))
    return out


def hit_markets(e_home: float, e_away: float) -> list:
    """Hits totales del partido + por equipo."""
    total = max(0.2, e_home + e_away)
    out = _over_under("Hits totales", "", total,
                      straddling_lines(total, (-3.5, -1.5, 0.5, 2.5)), "hits")
    for e, side in ((e_home, "Local"), (e_away, "Visitante")):
        for line in straddling_lines(max(0.2, e), (-1.5, 0.5, 2.5)):
            p = float(poisson.sf(int(line), max(0.1, e)))
            out.append((f"Hits del {side.lower()}", f"{side} más de {line:.1f} hits", p))
    return [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in out]


def hr_markets(e_home: float, e_away: float) -> list:
    """Jonrones totales + probabilidad de al menos 1."""
    total = max(0.05, e_home + e_away)
    # Líneas desde 2.5 hacia arriba: el caso ≥1 lo cubre "Al menos 1 jonrón" (sin duplicar).
    out = _over_under("Jonrones totales", "", total,
                      straddling_lines(total, (0.5, 1.5, 2.5, 3.5)), "jonrones")
    p_hr = 1.0 - float(poisson.pmf(0, total))
    out.append(("Jonrones", "Al menos 1 jonrón", p_hr))
    out.append(("Jonrones", "Ningún jonrón", 1.0 - p_hr))
    return [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in out]


def strikeout_markets(e_total_k: float) -> list:
    """Ponches totales del partido (bateadores de ambos equipos = ponches de los pitchers)."""
    total = max(0.2, e_total_k)
    out = _over_under("Ponches totales", "", total,
                      straddling_lines(total, (-3.5, -1.5, 0.5, 2.5)), "ponches")
    return [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in out]


def stats_markets(e_home_h: float, e_away_h: float,
                  e_home_hr: float, e_away_hr: float, e_total_k: float) -> list:
    """Lista combinada de hits + jonrones + ponches."""
    return (hit_markets(e_home_h, e_away_h)
            + hr_markets(e_home_hr, e_away_hr)
            + strikeout_markets(e_total_k))
