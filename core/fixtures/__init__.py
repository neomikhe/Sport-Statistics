"""
Feed de "partidos del día" por deporte.

Solo fuentes GRATIS y FIABLES (según la investigación de fuentes):
  - MLB   -> statsapi.mlb.com  (sin clave, estable)
  - Fútbol-> football-data.org (con clave gratuita del usuario, 12 ligas top)

NBA (nba_api) y tenis quedan fuera por ahora: la NBA bloquea IPs de nube y no hay
API de tenis gratis fiable. Todo degrada limpio si no hay red/clave.
"""
from datetime import date as _date


def todays_fixtures(sport: str, day=None) -> list:
    """Partidos del día para `sport`. Devuelve [] si la fuente no está disponible."""
    day = day or _date.today()
    if sport == "baseball":
        from core.fixtures.mlb import todays_games
        return todays_games(day)
    if sport == "football":
        from core.fixtures.football import todays_games
        return todays_games(day)
    return []
