"""
Four Factors de Dean Oliver para baloncesto NBA.

Las 4 metricas que mejor explican un partido (segun Oliver):
    eFG% = (FGM + 0.5 * FG3M) / FGA            - Effective Field Goal %
    TOV% = TOV / (FGA + 0.44*FTA + TOV)         - Turnover %
    ORB% = OREB / (OREB + opp_DREB)             - Offensive Rebound %
    FTR  = FTA / FGA                            - Free Throw Rate

Pesos sugeridos por Oliver:
    eFG%: 40% (mas importante)
    TOV%: 25%
    ORB%: 20%
    FTR:  15%
"""
import pandas as pd
import numpy as np


def compute_four_factors(fgm, fga, fg3m, ftm, fta, oreb, opp_dreb, tov):
    """Calcula los 4 factors para un equipo en un partido."""
    fga = max(int(fga or 0), 1)
    fta = int(fta or 0)
    tov = int(tov or 0)
    oreb = int(oreb or 0)
    opp_dreb = int(opp_dreb or 0)
    fgm = int(fgm or 0)
    fg3m = int(fg3m or 0)

    efg = (fgm + 0.5 * fg3m) / fga
    poss_proxy = fga + 0.44 * fta + tov
    tov_pct = tov / poss_proxy if poss_proxy > 0 else 0
    orb_total = oreb + opp_dreb
    orb_pct = oreb / orb_total if orb_total > 0 else 0
    ftr = fta / fga

    return {
        "efg": float(efg),
        "tov_pct": float(tov_pct),
        "orb_pct": float(orb_pct),
        "ftr": float(ftr),
    }


def four_factors_score(ff_offense: dict, ff_defense_opp: dict) -> float:
    """
    Combina Four Factors propios + del oponente en un score escalar.
    Score positivo = ventaja para el equipo evaluado.
    """
    # Diferenciales. Defensa = invertir signo de las metricas del oponente.
    efg_diff = ff_offense["efg"] - ff_defense_opp["efg"]
    tov_diff = ff_defense_opp["tov_pct"] - ff_offense["tov_pct"]  # menos perdidas = mejor
    orb_diff = ff_offense["orb_pct"] - ff_defense_opp["orb_pct"]
    ftr_diff = ff_offense["ftr"] - ff_defense_opp["ftr"]

    # Pesos Oliver
    return (
        0.40 * efg_diff
        + 0.25 * tov_diff
        + 0.20 * orb_diff
        + 0.15 * ftr_diff
    )


def compute_team_rolling_four_factors(engine, team_id: int, n_games: int = 10) -> dict:
    """
    Calcula los Four Factors PROMEDIO del equipo en sus ultimos n partidos.
    Considera tanto cuando jugo de local como visitante.
    """
    df = pd.read_sql(
        f"""
        SELECT date,
            CASE WHEN home_team_id = {team_id} THEN home_fgm  ELSE away_fgm  END AS fgm,
            CASE WHEN home_team_id = {team_id} THEN home_fga  ELSE away_fga  END AS fga,
            CASE WHEN home_team_id = {team_id} THEN home_fg3m ELSE away_fg3m END AS fg3m,
            CASE WHEN home_team_id = {team_id} THEN home_ftm  ELSE away_ftm  END AS ftm,
            CASE WHEN home_team_id = {team_id} THEN home_fta  ELSE away_fta  END AS fta,
            CASE WHEN home_team_id = {team_id} THEN home_oreb ELSE away_oreb END AS oreb,
            CASE WHEN home_team_id = {team_id} THEN away_dreb ELSE home_dreb END AS opp_dreb,
            CASE WHEN home_team_id = {team_id} THEN home_tov  ELSE away_tov  END AS tov
        FROM basketball_games
        WHERE (home_team_id = {team_id} OR away_team_id = {team_id})
          AND home_score IS NOT NULL
          AND home_fga IS NOT NULL
        ORDER BY date DESC
        LIMIT {n_games}
        """,
        engine,
    )
    if df.empty:
        return {"efg": 0.50, "tov_pct": 0.14, "orb_pct": 0.27, "ftr": 0.25}

    factors = [
        compute_four_factors(
            r["fgm"], r["fga"], r["fg3m"], r["ftm"], r["fta"],
            r["oreb"], r["opp_dreb"], r["tov"],
        )
        for _, r in df.iterrows()
    ]
    return {
        "efg":     float(np.mean([f["efg"] for f in factors])),
        "tov_pct": float(np.mean([f["tov_pct"] for f in factors])),
        "orb_pct": float(np.mean([f["orb_pct"] for f in factors])),
        "ftr":     float(np.mean([f["ftr"] for f in factors])),
    }
