"""
Mercados de baloncesto (NBA) desde UNA simulación Monte Carlo (Normal).

Todos los mercados salen de las mismas muestras → coherencia interna. No usa
cuotas. Modelo: marcador de cada equipo ~ Normal(E, sigma≈11). Las líneas de
hándicap/total se derivan de la propia distribución (línea justa ± alternativas).
Los mercados de 1ª mitad son APROXIMACIÓN (Normal con E/2 y sigma/√2).
"""
import numpy as np

from core.markets import premium_picks, top_markets  # noqa: F401

SIGMA_TEAM = 11.0


def _round_half(x: float) -> float:
    return round(float(x) * 2) / 2.0


def _winner_prob(diff):
    p_home = float((diff > 0).mean() + 0.5 * (diff == 0).mean())  # empates (OT) 50/50
    return p_home, 1.0 - p_home


def all_markets(e_home: float, e_away: float, sigma: float = SIGMA_TEAM,
                n_sims: int = 20000, rng=None) -> list:
    if rng is None:
        rng = np.random.default_rng(42)
    h = rng.normal(e_home, sigma, n_sims)
    a = rng.normal(e_away, sigma, n_sims)
    diff = h - a
    total = h + a

    full = []
    p_home, p_away = _winner_prob(diff)
    full += [("Ganador (ML)", "Gana local", p_home),
             ("Ganador (ML)", "Gana visitante", p_away)]

    # Hándicap (spread): "Local {hl}" gana si diff > -hl. Línea justa ± 6.5.
    hl0 = _round_half(-diff.mean())
    for hl in sorted({hl0 - 6.5, hl0, hl0 + 6.5}):
        full.append(("Hándicap local", f"Local {hl:+.1f}", float((diff > -hl).mean())))
    v0 = _round_half(diff.mean())   # "Visitante {v}" gana si diff < v
    for v in sorted({v0 - 6.5, v0, v0 + 6.5}):
        full.append(("Hándicap visitante", f"Visitante {v:+.1f}", float((diff < v).mean())))

    # Total de puntos
    tl0 = _round_half(total.mean())
    for tl in sorted({tl0 - 7.0, tl0, tl0 + 7.0}):
        full.append(("Total puntos", f"Over {tl:.1f}", float((total > tl).mean())))
        full.append(("Total puntos", f"Under {tl:.1f}", float((total < tl).mean())))

    # Team totals
    th = _round_half(h.mean())
    for tt in sorted({th - 8.0, th, th + 8.0}):
        full.append(("Puntos del local", f"Local Over {tt:.1f}", float((h > tt).mean())))
    ta = _round_half(a.mean())
    for tt in sorted({ta - 8.0, ta, ta + 8.0}):
        full.append(("Puntos del visitante", f"Visitante Over {tt:.1f}", float((a > tt).mean())))

    # 1ª mitad (aprox)
    h1 = rng.normal(e_home / 2, sigma / np.sqrt(2), n_sims)
    a1 = rng.normal(e_away / 2, sigma / np.sqrt(2), n_sims)
    d1, t1 = h1 - a1, h1 + a1
    p1h, p1a = _winner_prob(d1)
    tl1 = _round_half(t1.mean())
    half = [("1ª mitad", "Gana local 1ª mitad", p1h),
            ("1ª mitad", "Gana visitante 1ª mitad", p1a),
            ("1ª mitad", f"1ª mitad Over {tl1:.1f}", float((t1 > tl1).mean())),
            ("1ª mitad", f"1ª mitad Under {tl1:.1f}", float((t1 < tl1).mean()))]

    res = [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in full]
    res += [{"grupo": g, "mercado": s, "prob": p, "aprox": True} for g, s, p in half]
    return res
