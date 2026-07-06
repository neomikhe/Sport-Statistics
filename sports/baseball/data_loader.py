"""
Carga de datos MLB usando pybaseball.

Scaffolding para Fase 7. Funciones implementadas:
  - schedule_and_record(season): trae el calendario completo de una temporada
  - team_pitching(season): FIP, xFIP por staff
  - team_batting(season): wOBA por equipo

NO implementado todavia:
  - Lineups diarios via MLB Stats API
  - Statcast pitch-by-pitch
  - Park factors
  - Bullpen fatigue rolling

Uso futuro:
    venv\\Scripts\\activate
    pip install pybaseball
    python scripts/download_baseball_data.py
"""


def fetch_team_records(season: int):
    """Trae record + runs scored / allowed por equipo MLB para una temporada."""
    try:
        from pybaseball import standings
    except ImportError:
        raise RuntimeError("Instala pybaseball: pip install pybaseball")
    # standings() devuelve una lista de DataFrames (uno por division)
    return standings(season)


def fetch_team_pitching(season: int):
    """Trae stats de pitching agregadas por equipo (FIP, xFIP, ERA, etc.)."""
    try:
        from pybaseball import team_pitching
    except ImportError:
        raise RuntimeError("Instala pybaseball: pip install pybaseball")
    return team_pitching(season)


def fetch_team_batting(season: int):
    """Trae stats de bateo agregadas (wOBA, OPS, etc.)."""
    try:
        from pybaseball import team_batting
    except ImportError:
        raise RuntimeError("Instala pybaseball: pip install pybaseball")
    return team_batting(season)


def load_season(season: int):
    """
    Pipeline completo: descarga + insercion en baseball_games.

    Pendiente. Esquema actual de baseball_games requiere:
      - home_sp_id / away_sp_id (starting pitcher) -> requiere lookup adicional
      - park_factor -> requiere tabla de park factors precalculada
      - weather -> opcional

    TODO: implementar con pybaseball.schedule_and_record por equipo.
    """
    raise NotImplementedError(
        "load_season pendiente. Ver PROYECTO.md Fase 7. "
        "Inicialmente, recomienda cargar 2020-2024 con pybaseball.standings + "
        "team_pitching + team_batting agregados."
    )
