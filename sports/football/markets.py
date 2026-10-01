import numpy as np
from scipy.stats import poisson

from core.markets import premium_picks, top_markets  # noqa: F401

HALF_FRACTION = 0.45


def score_matrix(lambda_home: float, lambda_away: float,
                 rho: float = 0.0, max_goals: int = 10) -> np.ndarray:
    idx = np.arange(max_goals + 1)
    joint = np.outer(poisson.pmf(idx, lambda_home), poisson.pmf(idx, lambda_away))

    joint[0, 0] *= (1.0 - lambda_home * lambda_away * rho)
    joint[0, 1] *= (1.0 + lambda_home * rho)
    joint[1, 0] *= (1.0 + lambda_away * rho)
    joint[1, 1] *= (1.0 - rho)

    total_mass = joint.sum()
    return joint / total_mass if total_mass > 0 else joint


def _grids(n: int):
    h = np.arange(n)[:, None] * np.ones((1, n), dtype=int)
    a = np.ones((n, 1), dtype=int) * np.arange(n)[None, :]
    return h, a


def _fulltime_markets(m: np.ndarray) -> list:
    h, a = _grids(m.shape[0])
    total = h + a
    diff = h - a

    p_home = float(m[h > a].sum())
    p_draw = float(m[h == a].sum())
    p_away = float(m[h < a].sum())
    p_btts = float(m[(h >= 1) & (a >= 1)].sum())

    def over(line_int):
        return float(m[total >= line_int].sum())

    no_draw = p_home + p_away
    out = []

    out += [("1X2", "Gana local", p_home),
            ("1X2", "Empate", p_draw),
            ("1X2", "Gana visitante", p_away)]

    out += [("Doble oportunidad", "1X (local o empate)", p_home + p_draw),
            ("Doble oportunidad", "12 (sin empate)", p_home + p_away),
            ("Doble oportunidad", "X2 (empate o visitante)", p_draw + p_away)]

    if no_draw > 0:
        out += [("DNB (empate anula)", "Local", p_home / no_draw),
                ("DNB (empate anula)", "Visitante", p_away / no_draw)]

    for line, li in [("0.5", 1), ("1.5", 2), ("2.5", 3), ("3.5", 4)]:
        o = over(li)
        out += [("Over/Under", f"Over {line}", o),
                ("Over/Under", f"Under {line}", 1.0 - o)]

    out += [("Ambos anotan (BTTS)", "Sí", p_btts),
            ("Ambos anotan (BTTS)", "No", 1.0 - p_btts)]

    out += [("Goles del local", "Local Over 0.5", float(m[h >= 1].sum())),
            ("Goles del local", "Local Over 1.5", float(m[h >= 2].sum())),
            ("Goles del local", "Local Over 2.5", float(m[h >= 3].sum())),
            ("Goles del visitante", "Visitante Over 0.5", float(m[a >= 1].sum())),
            ("Goles del visitante", "Visitante Over 1.5", float(m[a >= 2].sum())),
            ("Goles del visitante", "Visitante Over 2.5", float(m[a >= 3].sum()))]

    out += [("Hándicap", "Local -1.5 (gana por ≥2)", float(m[diff >= 2].sum())),
            ("Hándicap", "Visitante +1.5", float(m[diff <= 1].sum())),
            ("Hándicap", "Local -2.5 (gana por ≥3)", float(m[diff >= 3].sum())),
            ("Hándicap", "Visitante +2.5", float(m[diff <= 2].sum())),
            ("Hándicap", "Visitante -1.5 (gana por ≥2)", float(m[diff <= -2].sum())),
            ("Hándicap", "Local +1.5", float(m[diff >= -1].sum()))]

    out += [("Resultado + O/U 2.5", "Local y Over 2.5", float(m[(h > a) & (total >= 3)].sum())),
            ("Resultado + O/U 2.5", "Local y Under 2.5", float(m[(h > a) & (total <= 2)].sum())),
            ("Resultado + O/U 2.5", "Visitante y Over 2.5", float(m[(h < a) & (total >= 3)].sum())),
            ("Resultado + O/U 2.5", "Visitante y Under 2.5", float(m[(h < a) & (total <= 2)].sum()))]

    out += [("Resultado + BTTS", "Local y BTTS sí", float(m[(h > a) & (a >= 1)].sum())),
            ("Resultado + BTTS", "Visitante y BTTS sí", float(m[(h < a) & (h >= 1)].sum())),
            ("Resultado + BTTS", "Empate y BTTS sí", float(m[(h == a) & (h >= 1)].sum()))]

    return [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in out]


def _firsthalf_markets(lambda_home: float, lambda_away: float,
                       rho: float, max_goals: int) -> list:
    lh = HALF_FRACTION * lambda_home
    la = HALF_FRACTION * lambda_away
    m = score_matrix(lh, la, rho, max_goals)
    h, a = _grids(m.shape[0])
    total = h + a

    lam_total = lambda_home + lambda_away
    p_goal_1h = 1.0 - np.exp(-HALF_FRACTION * lam_total)
    p_goal_2h = 1.0 - np.exp(-(1.0 - HALF_FRACTION) * lam_total)

    out = [
        ("1ª mitad", "1ª mitad Over 0.5", float(m[total >= 1].sum())),
        ("1ª mitad", "1ª mitad Under 0.5", float(m[total == 0].sum())),
        ("1ª mitad", "1ª mitad Over 1.5", float(m[total >= 2].sum())),
        ("1ª mitad", "Gana local 1ª mitad", float(m[h > a].sum())),
        ("1ª mitad", "Empate 1ª mitad", float(m[h == a].sum())),
        ("1ª mitad", "Gana visitante 1ª mitad", float(m[h < a].sum())),
        ("Mitades", "Gol en ambas mitades", float(p_goal_1h * p_goal_2h)),
    ]
    return [{"grupo": g, "mercado": s, "prob": p, "aprox": True} for g, s, p in out]


def all_markets(lambda_home: float, lambda_away: float,
                rho: float = 0.0, max_goals: int = 10) -> list:
    m = score_matrix(lambda_home, lambda_away, rho, max_goals)
    return _fulltime_markets(m) + _firsthalf_markets(lambda_home, lambda_away, rho, max_goals)


def top_scorelines(lambda_home: float, lambda_away: float,
                   rho: float = 0.0, max_goals: int = 10, n: int = 5) -> list:
    m = score_matrix(lambda_home, lambda_away, rho, max_goals)
    flat = [(i, j, float(m[i, j])) for i in range(m.shape[0]) for j in range(m.shape[1])]
    return sorted(flat, key=lambda x: x[2], reverse=True)[:n]
