"""
Traduce el CONTEXTO cualitativo de la IA (impacto de las bajas) a un AJUSTE
cuantitativo de la fuerza ofensiva (λ de goles esperados) del equipo.

Es la pieza del "peso" (PROYECTO.md §7.5): saber que falta el goleador es fácil;
cuánto baja la probabilidad es lo difícil. Empezamos CONSERVADORES y es tuneable.

  none / unknown -> sin cambio (1.00)
  low            -> -4 %  (0.96)
  medium         -> -10 % (0.90)
  high           -> -18 % (0.82)  (p. ej. falta el máximo goleador)
"""
def _get(table: dict, impact: str, default):
    return table.get(str(impact).lower().strip(), default)


# ---- Fútbol: multiplica el λ de goles esperados ----
_GOALS = {"none": 1.0, "unknown": 1.0, "low": 0.96, "medium": 0.90, "high": 0.82}


def lambda_multiplier(impact: str) -> float:
    """Factor del λ ofensivo (goles) del equipo según el impacto de las bajas."""
    return _get(_GOALS, impact, 1.0)


# ---- NBA: multiplica los puntos esperados (escala MUY pequeña: una estrella
#      fuera baja ~5-6 pts sobre ~115, no un 18%) ----
_POINTS = {"none": 1.0, "unknown": 1.0, "low": 0.985, "medium": 0.97, "high": 0.95}


def points_multiplier(impact: str) -> float:
    """Factor de los puntos esperados del equipo (NBA)."""
    return _get(_POINTS, impact, 1.0)


# ---- MLB: multiplica las carreras esperadas (escala media) ----
_RUNS = {"none": 1.0, "unknown": 1.0, "low": 0.97, "medium": 0.93, "high": 0.88}


def runs_multiplier(impact: str) -> float:
    """Factor de las carreras esperadas del equipo (MLB)."""
    return _get(_RUNS, impact, 1.0)


# ---- Tenis: puntos de Elo a RESTAR al jugador afectado (se recalcula la prob.) ----
_ELO_PEN = {"none": 0.0, "unknown": 0.0, "low": 20.0, "medium": 45.0, "high": 80.0}


def elo_penalty(impact: str) -> float:
    """Penalización en puntos de Elo del jugador afectado (tenis)."""
    return _get(_ELO_PEN, impact, 0.0)
