import math

from core.history.resolvers import STATS_GROUPS, BASEBALL_STATS_GROUPS

EVENT_GROUPS = set(STATS_GROUPS) | set(BASEBALL_STATS_GROUPS)

MIN_N = 150
PRIOR = 200.0
CAP = 0.5

_CACHE = {}


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def group_corrections(engine=None) -> dict:
    if "corr" in _CACHE:
        return _CACHE["corr"]
    try:
        from core.history.store import history_summary
        df = history_summary()
    except Exception:
        return {}
    corr = {}
    if df is not None and not df.empty:
        for r in df.itertuples(index=False):
            if r.grupo not in EVENT_GROUPS:
                continue
            n = int(r.n)
            if n < MIN_N:
                continue
            p = float(r.prob_media)
            hits = float(r.aciertos)
            obs_shrunk = (hits + PRIOR * p) / (n + PRIOR)
            delta = _logit(obs_shrunk) - _logit(p)
            corr[(r.sport, r.grupo)] = max(-CAP, min(CAP, delta))
    _CACHE["corr"] = corr
    return corr


def apply_corrections(markets: list, sport: str, engine=None) -> list:
    corr = group_corrections(engine)
    if not corr:
        return markets
    for m in markets:
        d = corr.get((sport, m.get("grupo")))
        if d:
            m["prob"] = _sigmoid(_logit(float(m["prob"])) + d)
    return markets
