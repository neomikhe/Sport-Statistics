"""
Feature engineering para baloncesto NBA.

Genera features pre-partido evitando data leakage (shift(1) + merge_asof backward).

Features (10):
    Elo:        home_elo, away_elo, elo_diff
    Ataque:     home_pts_5, home_pts_10, away_pts_5, away_pts_10
    Defensa:    home_pa_5, away_pa_5  (puntos concedidos rolling)
    Descanso:   home_rest, away_rest
"""
import numpy as np
import pandas as pd


DEFAULT_ELO = 1500.0
DEFAULT_REST_DAYS = 2  # NBA juega cada ~2 dias en temporada regular

FEATURE_COLS = [
    "home_elo", "away_elo", "elo_diff",
    "home_pts_5", "home_pts_10", "away_pts_5", "away_pts_10",
    "home_pa_5", "home_pa_10", "away_pa_5", "away_pa_10",
    "home_rest", "away_rest",
]


def _load_games(engine):
    return pd.read_sql(
        """
        SELECT id, date, home_team_id, away_team_id, home_score, away_score
        FROM basketball_games
        WHERE home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY date, id
        """,
        engine,
        parse_dates=["date"],
    )


def _load_basketball_elo(engine):
    """Lee snapshots Elo de la tabla football_elo? No, debemos crear basketball_elo.
    Por simplicidad inicial usamos un calculo en memoria del Elo en lugar de tabla."""
    # NBA no tiene tabla Elo en el schema inicial. Calcularemos en memoria.
    return None


def _build_team_timeline(df_games):
    home = df_games[["id", "date", "home_team_id", "away_team_id",
                     "home_score", "away_score"]].rename(columns={
        "home_team_id": "team_id",
        "away_team_id": "opponent_id",
        "home_score": "pts_for",
        "away_score": "pts_against",
    })
    home["is_home"] = True

    away = df_games[["id", "date", "home_team_id", "away_team_id",
                     "home_score", "away_score"]].rename(columns={
        "away_team_id": "team_id",
        "home_team_id": "opponent_id",
        "away_score": "pts_for",
        "home_score": "pts_against",
    })
    away["is_home"] = False

    timeline = pd.concat([home, away], ignore_index=True)
    return timeline.sort_values(["team_id", "date", "id"]).reset_index(drop=True)


def _add_rolling(timeline, windows=(5, 10)):
    for w in windows:
        timeline[f"pts_{w}"] = (
            timeline.groupby("team_id")["pts_for"]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
        )
        timeline[f"pa_{w}"] = (
            timeline.groupby("team_id")["pts_against"]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
        )
    return timeline


def _add_rest_days(timeline):
    timeline["_prev_date"] = timeline.groupby("team_id")["date"].shift(1)
    rest = (timeline["date"] - timeline["_prev_date"]).dt.days
    timeline["rest_days"] = rest.clip(upper=10).fillna(DEFAULT_REST_DAYS).astype(int)
    return timeline.drop(columns=["_prev_date"])


def _date_to_nba_season(d) -> str:
    """Temporada NBA: si mes >= 10 -> YYYY-YY+1; si no -> YYYY-1-YY."""
    if d.month >= 10:
        return f"{d.year}-{str(d.year + 1)[-2:]}"
    return f"{d.year - 1}-{str(d.year)[-2:]}"


def _compute_elo_inmemory(df_games, default_elo=DEFAULT_ELO):
    """Calcula Elo en memoria con regresion a la media entre temporadas NBA."""
    from sports.basketball.elo import BasketballEloSystem

    elo_pre = {}
    elo_sys = BasketballEloSystem()

    df_sorted = df_games.sort_values(["date", "id"]).reset_index(drop=True)
    for _, r in df_sorted.iterrows():
        elo_pre[(r["home_team_id"], r["id"])] = elo_sys.get(r["home_team_id"])
        elo_pre[(r["away_team_id"], r["id"])] = elo_sys.get(r["away_team_id"])
        season = _date_to_nba_season(r["date"])
        elo_sys.process_game(
            r["date"], season,
            r["home_team_id"], r["away_team_id"],
            int(r["home_score"]), int(r["away_score"]),
        )
    return elo_pre


def build_features(engine) -> pd.DataFrame:
    """Pipeline completo basketball features."""
    df = _load_games(engine)
    if df.empty:
        return df

    timeline = _build_team_timeline(df)
    timeline = _add_rolling(timeline, windows=(5, 10))
    timeline = _add_rest_days(timeline)

    # Elo en memoria (no hay tabla basketball_elo en el schema MVP)
    elo_pre = _compute_elo_inmemory(df)
    timeline["elo_pre"] = timeline.apply(
        lambda r: elo_pre.get((r["team_id"], r["id"]), DEFAULT_ELO), axis=1
    )

    # Pivot a vista por partido
    cols = ["id", "elo_pre", "pts_5", "pts_10", "pa_5", "pa_10", "rest_days"]
    home = timeline[timeline["is_home"]][cols].rename(columns={
        "elo_pre": "home_elo",
        "pts_5": "home_pts_5", "pts_10": "home_pts_10",
        "pa_5": "home_pa_5", "pa_10": "home_pa_10",
        "rest_days": "home_rest",
    })
    away = timeline[~timeline["is_home"]][cols].rename(columns={
        "elo_pre": "away_elo",
        "pts_5": "away_pts_5", "pts_10": "away_pts_10",
        "pa_5": "away_pa_5", "pa_10": "away_pa_10",
        "rest_days": "away_rest",
    })

    result = df.merge(home, on="id").merge(away, on="id")
    result["elo_diff"] = result["home_elo"] - result["away_elo"]
    return result.sort_values("date").reset_index(drop=True)
