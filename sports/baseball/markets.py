"""
Mercados de béisbol (MLB) desde UNA simulación Monte Carlo de carreras.

Carreras por equipo ~ Binomial Negativa (overdispersión típica de MLB: varianza
≈ 1.35·media). Todos los mercados salen de las mismas muestras → coherencia.

Modelo a nivel EQUIPO (carreras esperadas desde RS/RA). NO usa abridor, bullpen,
park factor ni clima: no hay datos. Por eso el ML individual rara vez pasa de ~62%
(lo normal en béisbol). F5 (primeras 5 entradas) es APROXIMACIÓN (~5/9 del juego).
"""
import numpy as np

from core.markets import premium_picks, top_markets  # noqa: F401

NB_P = 0.741  # p de la binomial negativa -> varianza ≈ 1.35·media


def _sim_runs(mean_runs: float, n: int, rng):
    n_param = max(mean_runs, 0.05) * NB_P / (1.0 - NB_P)
    return rng.negative_binomial(n_param, NB_P, n)


def _winner_prob(diff):
    p_home = float((diff > 0).mean() + 0.5 * (diff == 0).mean())  # sin empates (entradas extra)
    return p_home, 1.0 - p_home


def _half_line(mean_total: float) -> float:
    line = round(mean_total * 2) / 2.0
    return line + 0.5 if line == round(line) else line  # evita push (línea entera)


def all_markets(e_home_runs: float, e_away_runs: float,
                n_sims: int = 20000, rng=None) -> list:
    if rng is None:
        rng = np.random.default_rng(42)
    h = _sim_runs(e_home_runs, n_sims, rng)
    a = _sim_runs(e_away_runs, n_sims, rng)
    diff = h - a
    total = h + a

    full = []
    p_home, p_away = _winner_prob(diff)
    full += [("Ganador (ML)", "Gana local", p_home),
             ("Ganador (ML)", "Gana visitante", p_away)]

    full += [("Run line (±1.5)", "Local -1.5 (gana por ≥2)", float((diff >= 2).mean())),
             ("Run line (±1.5)", "Visitante +1.5", float((diff <= 1).mean())),
             ("Run line (±1.5)", "Visitante -1.5 (gana por ≥2)", float((diff <= -2).mean())),
             ("Run line (±1.5)", "Local +1.5", float((diff >= -1).mean()))]

    tl0 = _half_line(total.mean())
    for tl in sorted({tl0 - 2.0, tl0, tl0 + 2.0}):
        full.append(("Total carreras", f"Over {tl:.1f}", float((total > tl).mean())))
        full.append(("Total carreras", f"Under {tl:.1f}", float((total < tl).mean())))

    full += [("Carreras del local", "Local Over 0.5", float((h >= 1).mean())),
             ("Carreras del local", "Local Over 2.5", float((h >= 3).mean())),
             ("Carreras del visitante", "Visitante Over 0.5", float((a >= 1).mean())),
             ("Carreras del visitante", "Visitante Over 2.5", float((a >= 3).mean()))]

    # F5 (primeras 5 entradas) — aprox: ~5/9 de las carreras
    frac = 5.0 / 9.0
    h5 = _sim_runs(e_home_runs * frac, n_sims, rng)
    a5 = _sim_runs(e_away_runs * frac, n_sims, rng)
    d5, t5 = h5 - a5, h5 + a5
    p5h, p5a = _winner_prob(d5)
    tl5 = _half_line(t5.mean())
    half = [("F5 (5 entradas)", "Gana local F5", p5h),
            ("F5 (5 entradas)", "Gana visitante F5", p5a),
            ("F5 (5 entradas)", f"F5 Over {tl5:.1f}", float((t5 > tl5).mean())),
            ("F5 (5 entradas)", f"F5 Under {tl5:.1f}", float((t5 < tl5).mean()))]

    res = [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in full]
    res += [{"grupo": g, "mercado": s, "prob": p, "aprox": True} for g, s, p in half]
    return res
