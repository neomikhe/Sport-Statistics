"""
Modelo XGBoost para prediccion de goles en futbol.

Dos regresiones independientes (mismo schema que models.py):
  - home_xgb: predice home_goals
  - away_xgb: predice away_goals

Usa misma feature set que el GLM Poisson para permitir ensemble directo.
"""
import numpy as np
import pandas as pd
import xgboost as xgb

from sports.football.models import HOME_MODEL_FEATURES, AWAY_MODEL_FEATURES


XGB_PARAMS = {
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.05,
    "objective": "count:poisson",   # Poisson regression objective
    "tree_method": "hist",
    "random_state": 42,
}


class FootballXGBoostModel:
    """Modelo dual XGBoost (home/away) con objetivo Poisson."""

    def __init__(self, params: dict = None, version: str = "v1"):
        self.params = dict(XGB_PARAMS)
        if params:
            self.params.update(params)
        self.home_model = None
        self.away_model = None
        self.home_features = list(HOME_MODEL_FEATURES)
        self.away_features = list(AWAY_MODEL_FEATURES)
        self.version = version
        self.trained_rows = 0

    def fit(self, df: pd.DataFrame) -> "FootballXGBoostModel":
        all_feats = list(set(self.home_features) | set(self.away_features))
        mask = df[all_feats + ["home_goals", "away_goals"]].notna().all(axis=1)
        df_train = df[mask]
        if len(df_train) < 1000:
            raise ValueError(f"Pocos datos: {len(df_train)} filas. Min 1000.")

        self.home_model = xgb.XGBRegressor(**self.params).fit(
            df_train[self.home_features].values,
            df_train["home_goals"].values,
        )
        self.away_model = xgb.XGBRegressor(**self.params).fit(
            df_train[self.away_features].values,
            df_train["away_goals"].values,
        )
        self.trained_rows = len(df_train)
        return self

    def predict_lambda(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.home_model is None or self.away_model is None:
            raise RuntimeError("Modelo no entrenado.")
        lam_home = self.home_model.predict(df[self.home_features].values)
        lam_away = self.away_model.predict(df[self.away_features].values)
        # Asegurar lambdas positivas (Poisson requiere >0)
        lam_home = np.clip(lam_home, 0.01, None)
        lam_away = np.clip(lam_away, 0.01, None)
        return pd.DataFrame(
            {"lambda_home": lam_home, "lambda_away": lam_away},
            index=df.index,
        )


class FootballEnsembleModel:
    """Promedio ponderado de GLM Poisson + XGBoost."""

    def __init__(self, glm_model, xgb_model, glm_weight: float = 0.5):
        self.glm = glm_model
        self.xgb = xgb_model
        self.glm_weight = float(glm_weight)
        self.xgb_weight = 1.0 - float(glm_weight)

    def predict_lambda(self, df: pd.DataFrame) -> pd.DataFrame:
        glm_pred = self.glm.predict_lambda(df)
        xgb_pred = self.xgb.predict_lambda(df)
        return pd.DataFrame({
            "lambda_home": (
                self.glm_weight * glm_pred["lambda_home"]
                + self.xgb_weight * xgb_pred["lambda_home"]
            ),
            "lambda_away": (
                self.glm_weight * glm_pred["lambda_away"]
                + self.xgb_weight * xgb_pred["lambda_away"]
            ),
        }, index=df.index)
