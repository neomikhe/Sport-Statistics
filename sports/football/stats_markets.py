from scipy.stats import nbinom, poisson

CORNER_LINES = (8.5, 9.5, 10.5, 11.5)
CARD_LINES = (2.5, 3.5, 4.5, 5.5)

CORNER_PHI = 1.18
CARD_PHI = 1.16


def _nb_sf(k: int, mean: float, phi: float) -> float:
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
    lam = max(0.1, e_cards_total)
    out = []
    for line in CARD_LINES:
        p_over = _nb_sf(int(line), lam, CARD_PHI)
        out.append(("Tarjetas totales", f"Más de {_fmt(line)} tarjetas", p_over))
        out.append(("Tarjetas totales", f"Menos de {_fmt(line)} tarjetas", 1.0 - p_over))

    p_red = 1.0 - float(poisson.pmf(0, max(0.01, e_reds_total)))
    out.append(("Tarjeta roja", "Al menos 1 tarjeta roja", p_red))
    out.append(("Tarjeta roja", "Ninguna tarjeta roja", 1.0 - p_red))

    return [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in out]


def stats_markets(e_home_c: float, e_away_c: float,
                  e_cards_total: float, e_reds_total: float) -> list:
    return corner_markets(e_home_c, e_away_c) + card_markets(e_cards_total, e_reds_total)
