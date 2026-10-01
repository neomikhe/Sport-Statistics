def _get(table: dict, impact: str, default):
    return table.get(str(impact).lower().strip(), default)


_GOALS = {"none": 1.0, "unknown": 1.0, "low": 0.96, "medium": 0.90, "high": 0.82}


def lambda_multiplier(impact: str) -> float:
    return _get(_GOALS, impact, 1.0)


_POINTS = {"none": 1.0, "unknown": 1.0, "low": 0.985, "medium": 0.97, "high": 0.95}


def points_multiplier(impact: str) -> float:
    return _get(_POINTS, impact, 1.0)


_RUNS = {"none": 1.0, "unknown": 1.0, "low": 0.97, "medium": 0.93, "high": 0.88}


def runs_multiplier(impact: str) -> float:
    return _get(_RUNS, impact, 1.0)


_ELO_PEN = {"none": 0.0, "unknown": 0.0, "low": 20.0, "medium": 45.0, "high": 80.0}


def elo_penalty(impact: str) -> float:
    return _get(_ELO_PEN, impact, 0.0)
