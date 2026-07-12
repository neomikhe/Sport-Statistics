"""
Park factors de MLB — multiplicador del ambiente de carreras por estadio.

Un park factor > 1 infla las carreras (estadio de bateadores: Coors, Fenway…);
< 1 las deprime (estadio de pitchers: Oracle, Petco…). El factor se aplica al
ambiente TOTAL del juego (ambos equipos), porque el partido se juega en el parque
del LOCAL. Valores aproximados de varios años (dominio público, estables entre
temporadas), centrados en 1.00 y clave = nombre exacto de `entities`.
"""

PARK_FACTORS = {
    "Colorado Rockies":     1.15,   # Coors Field (altitud) — el más extremo
    "Boston Red Sox":       1.06,   # Fenway Park
    "Cincinnati Reds":      1.06,   # Great American Ball Park
    "Kansas City Royals":   1.03,
    "Baltimore Orioles":    1.03,
    "Philadelphia Phillies": 1.03,
    "Arizona Diamondbacks": 1.02,
    "Toronto Blue Jays":    1.02,
    "Chicago White Sox":    1.01,
    "New York Yankees":     1.01,
    "Chicago Cubs":         1.01,
    "Texas Rangers":        1.01,
    "Atlanta Braves":       1.00,
    "Los Angeles Angels":   1.00,
    "Washington Nationals": 1.00,
    "Minnesota Twins":      1.00,
    "Houston Astros":       1.00,
    "Milwaukee Brewers":    0.99,
    "St. Louis Cardinals":  0.99,
    "Pittsburgh Pirates":   0.99,
    "Cleveland Guardians":  0.98,
    "Detroit Tigers":       0.98,
    "Los Angeles Dodgers":  0.98,
    "New York Mets":        0.97,
    "Miami Marlins":        0.97,
    "Tampa Bay Rays":       0.97,
    "San Diego Padres":     0.95,
    "Oakland Athletics":    0.95,
    "San Francisco Giants": 0.94,
    "Seattle Mariners":     0.93,   # T-Mobile Park — de los más difíciles para batear
}


def park_factor(home_team_name: str) -> float:
    """Multiplicador de carreras del parque del equipo local (1.0 si no se conoce)."""
    return PARK_FACTORS.get(str(home_team_name).strip(), 1.0)
