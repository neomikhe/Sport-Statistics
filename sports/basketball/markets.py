import math

from core.forecast.base import half_line, market, norm_cdf
from core.markets import premium_picks, top_markets  # noqa: F401

SIGMA_TEAM = 11.0
SIGMA_MARGIN = 13.8
SIGMA_TOTAL = 18.8

_MARGIN = "Margen de victoria"
_HALF = "1ª mitad"


def _p_over(mu: float, sigma: float, line: float) -> float:
    return 1.0 - norm_cdf((line - mu) / sigma)


def _margin_bands(mu: float, sigma: float) -> list:
    def between(lo, hi):
        return norm_cdf((hi - mu) / sigma) - norm_cdf((lo - mu) / sigma)

    tie = between(-0.5, 0.5)
    return [
        market(_MARGIN, "Local gana por 1-5", between(0.5, 5.5) + tie / 2),
        market(_MARGIN, "Local gana por 6-10", between(5.5, 10.5)),
        market(_MARGIN, "Local gana por 11+", _p_over(mu, sigma, 10.5)),
        market(_MARGIN, "Visitante gana por 1-5", between(-5.5, -0.5) + tie / 2),
        market(_MARGIN, "Visitante gana por 6-10", between(-10.5, -5.5)),
        market(_MARGIN, "Visitante gana por 11+", norm_cdf((-10.5 - mu) / sigma)),
    ]


def normal_markets(margin_mu: float, total_mu: float,
                   sigma_margin: float = SIGMA_MARGIN,
                   sigma_total: float = SIGMA_TOTAL) -> list:
    sm, st_ = max(float(sigma_margin), 1e-6), max(float(sigma_total), 1e-6)
    mu, tot = float(margin_mu), float(total_mu)
    p_home = norm_cdf(mu / sm)
    out = [market("Ganador (ML)", "Gana local", p_home),
           market("Ganador (ML)", "Gana visitante", 1.0 - p_home)]

    hl0 = half_line(-mu)
    for hl in (hl0 - 6.0, hl0, hl0 + 6.0):
        out.append(market("Hándicap local", f"Local {hl:+.1f}", norm_cdf((mu + hl) / sm)))
    v0 = half_line(mu)
    for v in (v0 - 6.0, v0, v0 + 6.0):
        out.append(market("Hándicap visitante", f"Visitante {v:+.1f}", norm_cdf((v - mu) / sm)))

    tl0 = half_line(tot)
    for tl in (tl0 - 7.0, tl0, tl0 + 7.0):
        p_over = _p_over(tot, st_, tl)
        out.append(market("Total puntos", f"Over {tl:.1f}", p_over))
        out.append(market("Total puntos", f"Under {tl:.1f}", 1.0 - p_over))

    # Cada equipo = (total ± margen) / 2.
    s_team = math.sqrt(sm ** 2 + st_ ** 2) / 2.0
    for side, mean in (("local", (tot + mu) / 2.0), ("visitante", (tot - mu) / 2.0)):
        t0 = half_line(mean)
        for tt in (t0 - 8.0, t0, t0 + 8.0):
            out.append(market(f"Puntos del {side}", f"{side.capitalize()} Over {tt:.1f}",
                              _p_over(mean, s_team, tt)))

    out += _margin_bands(mu, sm)

    m1, s1m = mu / 2.0, sm / math.sqrt(2.0)
    t1, s1t = tot / 2.0, st_ / math.sqrt(2.0)
    p1 = norm_cdf(m1 / s1m)
    tl1 = half_line(t1)
    p1o = _p_over(t1, s1t, tl1)
    out += [market(_HALF, "Gana local 1ª mitad", p1, aprox=True),
            market(_HALF, "Gana visitante 1ª mitad", 1.0 - p1, aprox=True),
            market(_HALF, f"1ª mitad Over {tl1:.1f}", p1o, aprox=True),
            market(_HALF, f"1ª mitad Under {tl1:.1f}", 1.0 - p1o, aprox=True)]
    return out


def all_markets(e_home: float, e_away: float, sigma: float = SIGMA_TEAM,
                n_sims: int = 20000, rng=None) -> list:
    del n_sims, rng
    s = float(sigma) * math.sqrt(2.0)
    return normal_markets(e_home - e_away, e_home + e_away, s, s)
