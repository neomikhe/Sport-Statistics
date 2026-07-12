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


# ======================================================================
#  Ajuste a nivel de CARRERAS (para el modelo Monte Carlo de predict_baseball)
# ======================================================================
STARTER_SHARE = 0.60   # fracción del juego que lanza el abridor (~6 de 9 entradas)


def adjust_runs(e_home_runs: float, e_away_runs: float,
                home_fip: Optional[float], away_fip: Optional[float],
                league_fip: float = LEAGUE_AVG_FIP,
                starter_share: float = STARTER_SHARE):
    """Ajusta las carreras esperadas por el abridor RIVAL.

    El abridor local enfrenta a los bateadores visitantes -> suprime `e_away_runs`;
    el abridor visitante suprime `e_home_runs`. El efecto se amortigua por
    `starter_share`: el abridor lanza ~60% del juego, el resto (bullpen) se asume
    en la media de liga. Un FIP None (sin dato) deja ese lado sin ajustar.
    """
    def blend(fip):
        if fip is None or fip <= 0:
            return 1.0
        ratio = fip / league_fip              # <1 = mejor que la media -> menos carreras
        return starter_share * ratio + (1.0 - starter_share)

    e_away = max(0.5, e_away_runs * blend(home_fip))   # abridor local vs bateo visitante
    e_home = max(0.5, e_home_runs * blend(away_fip))   # abridor visitante vs bateo local
    return e_home, e_away


def lookup_starter_fips(engine, home_id: int, away_id: int, game_date):
    """(home_fip, away_fip) del abridor probable de ese juego. (None, None) si falta.

    Une mlb_starters (por nombre de equipo + fecha) con mlb_pitcher_stats (por
    pitcher_id, temporada más reciente). Best-effort: si falta cualquier pieza,
    devuelve None en ese lado y el modelo no ajusta.
    """
    import pandas as pd

    q = """
        SELECT
          (SELECT fip FROM mlb_pitcher_stats WHERE pitcher_id = s.home_starter_id
           ORDER BY season DESC LIMIT 1) AS home_fip,
          (SELECT fip FROM mlb_pitcher_stats WHERE pitcher_id = s.away_starter_id
           ORDER BY season DESC LIMIT 1) AS away_fip
        FROM mlb_starters s
        WHERE s.game_date = %(d)s
          AND s.home_team = (SELECT name FROM entities WHERE id = %(h)s)
          AND s.away_team = (SELECT name FROM entities WHERE id = %(a)s)
        LIMIT 1
    """
    try:
        df = pd.read_sql(q, engine, params={"h": int(home_id), "a": int(away_id),
                                            "d": str(game_date)})
    except Exception:
        return None, None
    if df.empty:
        return None, None

    def _f(v):
        return None if pd.isna(v) else float(v)

    return _f(df["home_fip"].iloc[0]), _f(df["away_fip"].iloc[0])
