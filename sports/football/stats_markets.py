"""
Mercados de córners y tarjetas — modelo Binomial Negativa sobre tasas de equipo.

v2: córners y tarjetas presentan SOBREDISPERSIÓN real (medido en el histórico:
var/media ≈ 1.18 córners, 1.16 tarjetas), así que un Poisson subestima las colas
(los "más de X" altos). Se usa Binomial Negativa parametrizada por media y factor
de sobredispersión φ, igual espíritu que el modelo de carreras de béisbol.

La media de cada equipo se estima con el modelo multiplicativo
(ataque × defensa × media de LIGA) — la media de liga la aporta core/football_stats.py,
porque las tarjetas varían muchísimo por liga (Grecia ~5.2 vs Países Bajos ~3.0).

Funciones PURAS: reciben los valores esperados y devuelven {grupo, mercado, prob, aprox}.
"""
from scipy.stats import nbinom, poisson

CORNER_LINES = (8.5, 9.5, 10.5, 11.5)   # líneas de córners totales habituales
CARD_LINES = (2.5, 3.5, 4.5, 5.5)       # líneas de tarjetas totales (amarillas + rojas)

CORNER_PHI = 1.18   # sobredispersión medida (var/media) en el histórico
CARD_PHI = 1.16


def _nb_sf(k: int, mean: float, phi: float) -> float:
    """P(X > k) para X ~ Binomial Negativa con esa media y sobredispersión φ (var=φ·media).

    φ≈1 -> se degrada a Poisson. Parametrización: p = 1/φ, n = media/(φ-1).
    """
    if mean <= 0:
        return 0.0
    if phi <= 1.0:
        return float(poisson.sf(k, mean))
    r = mean / (phi - 1.0)
    p = 1.0 / phi
    return float(nbinom.sf(k, r, p))


def _fmt(line: float) -> str:
    return f"{line:.1f}"


def corner_markets(e_home: float, e_away: float) -> list:
    """Mercados de córners a partir de los córners esperados de cada equipo."""
    total = max(0.1, e_home + e_away)
    out = []
    for line in CORNER_LINES:
        p_over = _nb_sf(int(line), total, CORNER_PHI)
        out.append(("Córners totales", f"Más de {_fmt(line)} córners", p_over))
        out.append(("Córners totales", f"Menos de {_fmt(line)} córners", 1.0 - p_over))

    for line in (3.5, 4.5, 5.5):
        ph = _nb_sf(int(line), max(0.1, e_home), CORNER_PHI)
        pa = _nb_sf(int(line), max(0.1, e_away), CORNER_PHI)
        out.append(("Córners del local", f"Local más de {_fmt(line)} córners", ph))
        out.append(("Córners del visitante", f"Visitante más de {_fmt(line)} córners", pa))

    return [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in out]


def card_markets(e_cards_total: float, e_reds_total: float) -> list:
    """Mercados de tarjetas: totales (amarillas+rojas) y probabilidad de roja."""
    lam = max(0.1, e_cards_total)
    out = []
    for line in CARD_LINES:
        p_over = _nb_sf(int(line), lam, CARD_PHI)
        out.append(("Tarjetas totales", f"Más de {_fmt(line)} tarjetas", p_over))
        out.append(("Tarjetas totales", f"Menos de {_fmt(line)} tarjetas", 1.0 - p_over))

    # Tarjeta roja: evento raro -> Poisson basta (NB≈Poisson con media pequeña).
    p_red = 1.0 - float(poisson.pmf(0, max(0.01, e_reds_total)))
    out.append(("Tarjeta roja", "Al menos 1 tarjeta roja", p_red))
    out.append(("Tarjeta roja", "Ninguna tarjeta roja", 1.0 - p_red))

    return [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in out]


def stats_markets(e_home_c: float, e_away_c: float,
                  e_cards_total: float, e_reds_total: float) -> list:
    """Lista combinada de córners + tarjetas."""
    return corner_markets(e_home_c, e_away_c) + card_markets(e_cards_total, e_reds_total)
