import numpy as np
from scipy.stats import nbinom

from core.forecast.base import half_line, market
from core.markets import premium_picks, top_markets  # noqa: F401

NB_P = 0.741
DISPERSION_R = 4.0
TIE_HOME = 0.52
MAX_RUNS = 30

_RUN_LINE = "Run line (±1.5)"
_F5 = "F5 (5 entradas)"


def runs_pmf(mean_runs: float, r: float = DISPERSION_R, max_runs: int = MAX_RUNS) -> np.ndarray:
    mu = max(float(mean_runs), 0.05)
    pmf = nbinom.pmf(np.arange(max_runs + 1), r, r / (r + mu))
    return pmf / pmf.sum()


def run_matrix(e_home: float, e_away: float, r: float = DISPERSION_R) -> np.ndarray:
    return np.outer(runs_pmf(e_home, r), runs_pmf(e_away, r))


# El empate tras 9 entradas se reparte con tie_home (entradas extra).
def _winner(m: np.ndarray, tie_home: float) -> float:
    n = m.shape[0]
    h, a = np.indices((n, n))
    return float(m[h > a].sum() + tie_home * m[h == a].sum())


def matrix_markets(m: np.ndarray, tie_home: float = TIE_HOME) -> list:
    n = m.shape[0]
    h, a = np.indices((n, n))
    diff, total = h - a, h + a
    p_home = _winner(m, tie_home)
    out = [market("Ganador (ML)", "Gana local", p_home),
           market("Ganador (ML)", "Gana visitante", 1.0 - p_home),
           market(_RUN_LINE, "Local -1.5 (gana por ≥2)", m[diff >= 2].sum()),
           market(_RUN_LINE, "Visitante +1.5", m[diff <= 1].sum()),
           market(_RUN_LINE, "Visitante -1.5 (gana por ≥2)", m[diff <= -2].sum()),
           market(_RUN_LINE, "Local +1.5", m[diff >= -1].sum())]
    mean_total = float((m * total).sum())
    tl0 = half_line(mean_total)
    for tl in (tl0 - 2.0, tl0, tl0 + 2.0):
        p_over = float(m[total > tl].sum())
        out.append(market("Total carreras", f"Over {tl:.1f}", p_over))
        out.append(market("Total carreras", f"Under {tl:.1f}", 1.0 - p_over))
    ph, pa = m.sum(axis=1), m.sum(axis=0)
    out += [market("Carreras del local", "Local Over 0.5", ph[1:].sum()),
            market("Carreras del local", "Local Over 2.5", ph[3:].sum()),
            market("Carreras del visitante", "Visitante Over 0.5", pa[1:].sum()),
            market("Carreras del visitante", "Visitante Over 2.5", pa[3:].sum())]
    return out


def _f5_markets(e_home: float, e_away: float, r: float) -> list:
    frac = 5.0 / 9.0
    m5 = run_matrix(e_home * frac, e_away * frac, r)
    n = m5.shape[0]
    h, a = np.indices((n, n))
    total = h + a
    p5 = _winner(m5, 0.5)
    tl5 = half_line(float((m5 * total).sum()))
    p5o = float(m5[total > tl5].sum())
    return [market(_F5, "Gana local F5", p5, aprox=True),
            market(_F5, "Gana visitante F5", 1.0 - p5, aprox=True),
            market(_F5, f"F5 Over {tl5:.1f}", p5o, aprox=True),
            market(_F5, f"F5 Under {tl5:.1f}", 1.0 - p5o, aprox=True)]


def all_markets(e_home_runs: float, e_away_runs: float, n_sims: int = 20000, rng=None,
                dispersion: float = DISPERSION_R, tie_home: float = TIE_HOME) -> list:
    del n_sims, rng
    m = run_matrix(e_home_runs, e_away_runs, dispersion)
    return matrix_markets(m, tie_home) + _f5_markets(e_home_runs, e_away_runs, dispersion)
