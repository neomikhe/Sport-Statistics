"""
Correccion Dixon-Coles para el modelo Poisson independiente de futbol.

La Poisson independiente subestima la frecuencia de marcadores bajos (0-0, 1-0, 0-1)
y sobreestima 1-1. Dixon-Coles (1997) aplica un factor de correccion tau(h,a,lh,la,rho)
a las 4 celdas criticas:

    tau(0,0) = 1 - lh * la * rho
    tau(0,1) = 1 + lh * rho
    tau(1,0) = 1 + la * rho
    tau(1,1) = 1 - rho
    tau(otros) = 1

Con rho negativo (~-0.10 a -0.15) aumenta P(0-0) y cruces 1-0 / 0-1, y disminuye P(1-1).
El parametro rho se estima por maxima verosimilitud sobre el histórico.

Uso tipico:
    rho_hat = fit_rho(home_goals, away_goals, lambda_home, lambda_away)
    probs = exact_probabilities_dc(lh, la, rho_hat)
"""
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import poisson


def tau_factor(h: int, a: int, lh: float, la: float, rho: float) -> float:
    """Factor Dixon-Coles para una celda (h, a)."""
    if h == 0 and a == 0:
        return 1.0 - lh * la * rho
    if h == 0 and a == 1:
        return 1.0 + lh * rho
    if h == 1 and a == 0:
        return 1.0 + la * rho
    if h == 1 and a == 1:
        return 1.0 - rho
    return 1.0


def dixon_coles_pmf(h, a, lh, la, rho):
    """P_DC(H=h, A=a) = tau * P_Poisson(H=h) * P_Poisson(A=a)."""
    base = poisson.pmf(h, lh) * poisson.pmf(a, la)
    return base * tau_factor(h, a, lh, la, rho)


def _neg_log_likelihood(rho: float, home_goals, away_goals, lh, la) -> float:
    """Neg-log-likelihood vectorizado de rho."""
    home_goals = np.asarray(home_goals)
    away_goals = np.asarray(away_goals)
    lh = np.asarray(lh, dtype=float)
    la = np.asarray(la, dtype=float)

    log_pmf_h = poisson.logpmf(home_goals, lh)
    log_pmf_a = poisson.logpmf(away_goals, la)
    base_log = log_pmf_h + log_pmf_a

    tau = np.ones_like(home_goals, dtype=float)
    m00 = (home_goals == 0) & (away_goals == 0)
    m01 = (home_goals == 0) & (away_goals == 1)
    m10 = (home_goals == 1) & (away_goals == 0)
    m11 = (home_goals == 1) & (away_goals == 1)

    tau[m00] = 1.0 - lh[m00] * la[m00] * rho
    tau[m01] = 1.0 + lh[m01] * rho
    tau[m10] = 1.0 + la[m10] * rho
    tau[m11] = 1.0 - rho

    tau = np.clip(tau, 1e-10, None)
    log_lik = base_log + np.log(tau)
    return -float(np.sum(log_lik))


def fit_rho(home_goals, away_goals, lh, la, bracket=(-0.25, 0.05)) -> float:
    """Estima rho por MLE. Tipico en futbol: -0.10 a -0.15."""
    result = minimize_scalar(
        lambda rho: _neg_log_likelihood(rho, home_goals, away_goals, lh, la),
        bracket=bracket,
        method="brent",
    )
    return float(result.x)


def exact_probabilities_dc(lh: float, la: float, rho: float, max_goals: int = 15) -> dict:
    """
    Probabilidades analiticas 1X2, Over/Under 2.5 y BTTS con correccion Dixon-Coles.

    Renormaliza la joint para que sume 1 despues de aplicar los factores tau.
    """
    idx = np.arange(max_goals + 1)
    pmf_h = poisson.pmf(idx, lh)
    pmf_a = poisson.pmf(idx, la)
    joint = np.outer(pmf_h, pmf_a)

    # Aplicar correccion solo en las 4 celdas relevantes
    joint[0, 0] *= (1.0 - lh * la * rho)
    joint[0, 1] *= (1.0 + lh * rho)
    joint[1, 0] *= (1.0 + la * rho)
    joint[1, 1] *= (1.0 - rho)

    # Renormalizar (tau puede romper marginalmente la suma = 1)
    total_mass = joint.sum()
    if total_mass > 0:
        joint = joint / total_mass

    h_grid, a_grid = np.meshgrid(idx, idx, indexing="ij")
    total = h_grid + a_grid

    return {
        "prob_home":      float(joint[h_grid > a_grid].sum()),
        "prob_draw":      float(joint[h_grid == a_grid].sum()),
        "prob_away":      float(joint[h_grid < a_grid].sum()),
        "prob_over_2_5":  float(joint[total >= 3].sum()),
        "prob_under_2_5": float(joint[total <= 2].sum()),
        "prob_btts":      float(joint[(h_grid > 0) & (a_grid > 0)].sum()),
        "rho_used":       float(rho),
    }
