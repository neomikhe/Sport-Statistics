import math
from dataclasses import dataclass, field


@dataclass
class Forecast:
    sport: str
    home: str
    away: str
    markets: list
    win: dict
    expected: dict
    ratings: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    extras: dict = field(default_factory=dict)


def fair_odds(p: float) -> float:
    return 1.0 / p if p > 1e-9 else float("inf")


def logit(p: float) -> float:
    p = min(max(float(p), 1e-9), 1 - 1e-9)
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def round_half(x: float) -> float:
    return round(float(x) * 2.0) / 2.0


def half_line(x: float) -> float:
    line = round_half(x)
    return line + 0.5 if line == round(line) else line


def market(grupo: str, mercado: str, prob: float, aprox: bool = False) -> dict:
    return {"grupo": grupo, "mercado": mercado,
            "prob": min(max(float(prob), 0.0), 1.0), "aprox": bool(aprox)}


def season_of(d, start_month: int) -> int:
    return d.year if d.month >= start_month else d.year - 1
