"""
Ajuste de prediccion MLB por starting pitcher.

Dado el FIP del pitcher abridor frente a la media de la liga, ajusta la
probabilidad de victoria del equipo:
    p_ajustada = p_team * (FIP_liga / FIP_starter) ** factor

Heuristica ligera. Para modelo serio hay que separar starter + bullpen
en sub-modelos (PROYECTO.md §8.2).
"""
from typing import Optional


LEAGUE_AVG_FIP = 4.20
ADJUSTMENT_FACTOR = 0.5


def get_starter_fip(conn, pitcher_name: str, season: int) -> Optional[float]:
    """Lee FIP de mlb_pitcher_stats para un pitcher en una temporada."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT fip FROM mlb_pitcher_stats
            WHERE pitcher_name = %s AND season = %s
            """,
            (pitcher_name, season),
        )
        row = cur.fetchone()
        return float(row[0]) if row and row[0] is not None else None


def adjust_winrate_by_starter(
    base_winrate: float,
    starter_fip: Optional[float],
    league_avg_fip: float = LEAGUE_AVG_FIP,
    factor: float = ADJUSTMENT_FACTOR,
) -> float:
    """
    Ajusta winrate del equipo segun cuanto mejor/peor que la media es su starter.

    starter mejor que la media (FIP < liga) -> winrate sube.
    starter peor (FIP > liga) -> winrate baja.

    factor=0.5 controla la intensidad (mas alto = mas sensible).
    """
    if starter_fip is None or starter_fip <= 0:
        return base_winrate

    multiplier = (league_avg_fip / starter_fip) ** factor
    adjusted = base_winrate * multiplier
    # Cap en [0.05, 0.95] para evitar extremos
    return max(0.05, min(0.95, adjusted))


def matchup_adjustment(
    home_winrate: float,
    home_starter_fip: Optional[float],
    away_starter_fip: Optional[float],
    league_avg_fip: float = LEAGUE_AVG_FIP,
) -> float:
    """
    Ajusta winrate del local considerando AMBOS starters.

    El home team gana mas si su starter es mejor que el del oponente.
    """
    home_adj = adjust_winrate_by_starter(home_winrate, home_starter_fip, league_avg_fip)
    # Si el oponente tiene mejor starter, el home pierde algo
    if away_starter_fip is not None and away_starter_fip > 0:
        rival_factor = (away_starter_fip / league_avg_fip) ** ADJUSTMENT_FACTOR
        home_adj = home_adj * rival_factor

    # Re-normalizar: si ambos pitchers son muy buenos, baja el variance pero
    # mantiene el balance home/away. Cap en [0.10, 0.90].
    return max(0.10, min(0.90, home_adj))
