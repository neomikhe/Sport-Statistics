"""
Modelo pace-adjusted para baloncesto NBA.

A diferencia del futbol (Poisson sobre goles), el baloncesto se modela mejor con
regresion lineal sobre el marcador o sobre el spread (diferencia de puntos).

Implementacion: dos regresiones lineales sklearn — una para home_score, otra
para away_score — con las mismas features del modulo features.py.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


HOME_MODEL_FEATURES = [
    "home_elo", "away_elo",
    "home_pts_5", "home_pts_10",
    "away_pa_5", "away_pa_10",
    "home_rest", "away_rest",
]

AWAY_MODEL_FEATURES = [
    "away_elo", "home_elo",
    "away_pts_5", "away_pts_10",
    "home_pa_5", "home_pa_10",
    "away_rest", "home_rest",
]


class BasketballScoreModel:
    """Predice home_score y away_score con dos Ridge regressions independientes."""

    def __init__(self, alpha: float = 1.0, version: str = "v1"):
        self.alpha = alpha
        self.version = version
        self.home_model = None
        self.away_model = None
        self.home_features = list(HOME_MODEL_FEATURES)
        self.away_features = list(AWAY_MODEL_FEATURES)
        self.trained_rows = 0

    def fit(self, df: pd.DataFrame) -> "BasketballScoreModel":
        needed = set(self.home_features) | set(self.away_features) | {"home_score", "away_score"}
        missing = needed - set(df.columns)
        if missing:
            raise ValueError(f"Faltan columnas: {missing}")

        mask = df[list(needed)].notna().all(axis=1)
        df_train = df[mask]
        if len(df_train) < 500:
            raise ValueError(f"Pocos datos: {len(df_train)} filas. Minimo 500.")

        self.home_model = Ridge(alpha=self.alpha).fit(
            df_train[self.home_features].values, df_train["home_score"].values
        )
        self.away_model = Ridge(alpha=self.alpha).fit(
            df_train[self.away_features].values, df_train["away_score"].values
        )
        self.trained_rows = len(df_train)
        return self

    def predict_score(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.home_model is None or self.away_model is None:
            raise RuntimeError("Modelo no entrenado.")
        e_home = self.home_model.predict(df[self.home_features].values)
        e_away = self.away_model.predict(df[self.away_features].values)
        return pd.DataFrame(
            {"expected_home": e_home, "expected_away": e_away},
            index=df.index,
        )
