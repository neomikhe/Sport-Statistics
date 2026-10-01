def kelly_full(prob, odds):
    b = float(odds) - 1.0
    if b <= 0:
        return 0.0
    p = float(prob)
    q = 1.0 - p
    f = (p * b - q) / b
    return max(0.0, f)


def kelly_fractional(prob, odds, fraction=0.25):
    return kelly_full(prob, odds) * float(fraction)


def kelly_stake(prob, odds, bankroll, fraction=0.25, max_stake_pct=0.05):
    f = min(kelly_fractional(prob, odds, fraction), float(max_stake_pct))
    return float(bankroll) * f
