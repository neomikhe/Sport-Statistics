"""
Kelly staking fraccional.

Kelly completo (formula original, Kelly 1956):
    f* = (p*b - q) / b
donde:
    p = probabilidad de ganar (del modelo)
    q = 1 - p
    b = beneficio neto por unidad apostada = cuota_decimal - 1

El Kelly completo maximiza el crecimiento geometrico esperado a largo plazo pero
con varianza brutal (drawdowns del 50 %+ son normales). En la practica se usa
1/4 Kelly (o 1/8) que sacrifica ~25 % del crecimiento a cambio de drawdowns
mucho menores.

Regla adicional: cap absoluto de % del bankroll por pick (default 5 %).
"""


def kelly_full(prob, odds):
    """Fraccion del bankroll segun Kelly completo. Devuelve 0 si no hay valor."""
    b = float(odds) - 1.0
    if b <= 0:
        return 0.0
    p = float(prob)
    q = 1.0 - p
    f = (p * b - q) / b
    return max(0.0, f)


def kelly_fractional(prob, odds, fraction=0.25):
    """Kelly reducido por `fraction`. Default 1/4 Kelly."""
    return kelly_full(prob, odds) * float(fraction)


def kelly_stake(prob, odds, bankroll, fraction=0.25, max_stake_pct=0.05):
    """Stake en euros/dolares segun Kelly fraccional con cap al max_stake_pct."""
    f = min(kelly_fractional(prob, odds, fraction), float(max_stake_pct))
    return float(bankroll) * f
