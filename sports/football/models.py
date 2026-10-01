import json
from pathlib import Path

import numpy as np
import pandas as pd


HOME_MODEL_FEATURES = [
    "home_elo", "away_elo",
    "home_gf_5", "home_gf_10",
    "away_ga_5", "away_ga_10",
    "home_form_5",
    "home_rest", "away_rest",
]

AWAY_MODEL_FEATURES = [
    "away_elo", "home_elo",
    "away_gf_5", "away_gf_10",
    "home_ga_5", "home_ga_10",
    "away_form_5",
    "away_rest", "home_rest",
]


def _fit_poisson(df_train, features, target):
    import statsmodels.api as sm

    X = sm.add_constant(df_train[features], has_constant="add")
    y = df_train[target]
    result = sm.GLM(y, X, family=sm.families.Poisson()).fit()

    coefs = result.params.to_dict()
    summary_text = str(result.summary())
    return coefs, summary_text, result


def _predict_lambda(coefs, features, df):
    linear = np.full(len(df), coefs["const"], dtype=float)
    for name in features:
        linear = linear + coefs[name] * df[name].to_numpy(dtype=float)
    return np.exp(linear)


class FootballPoissonModel:
    def __init__(self,
                 home_features=None,
                 away_features=None,
                 version="v1"):
        self.home_features = list(home_features or HOME_MODEL_FEATURES)
        self.away_features = list(away_features or AWAY_MODEL_FEATURES)
        self.home_coefs: dict = {}
        self.away_coefs: dict = {}
        self.summary_home: str = ""
        self.summary_away: str = ""
        self.version = version
        self.trained_rows: int = 0
        self.trained_seasons: list = []

    def fit(self, df: pd.DataFrame) -> "FootballPoissonModel":
        needed = set(self.home_features) | set(self.away_features)
        needed.update(["home_goals", "away_goals", "season"])
        missing = needed - set(df.columns)
        if missing:
            raise ValueError(f"Faltan columnas en el DataFrame: {missing}")

        mask = (
            df[list(set(self.home_features) | set(self.away_features))].notna().all(axis=1)
            & df["home_goals"].notna()
            & df["away_goals"].notna()
        )
        df_train = df[mask]
        if len(df_train) < 1000:
            raise ValueError(f"Muy pocos datos para entrenar: {len(df_train)} filas. Minimo ~1000.")

        self.home_coefs, self.summary_home, _ = _fit_poisson(
            df_train, self.home_features, "home_goals"
        )
        self.away_coefs, self.summary_away, _ = _fit_poisson(
            df_train, self.away_features, "away_goals"
        )

        self.trained_rows = len(df_train)
        self.trained_seasons = sorted(df_train["season"].dropna().unique().tolist())
        return self

    def predict_lambda(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.home_coefs or not self.away_coefs:
            raise RuntimeError("El modelo no ha sido entrenado todavia.")

        lam_home = _predict_lambda(self.home_coefs, self.home_features, df)
        lam_away = _predict_lambda(self.away_coefs, self.away_features, df)
        return pd.DataFrame(
            {"lambda_home": lam_home, "lambda_away": lam_away},
            index=df.index,
        )

    def to_dict(self) -> dict:
        return {"version": self.version, "home_features": self.home_features,
                "away_features": self.away_features,
                "home_coefs": {k: float(v) for k, v in self.home_coefs.items()},
                "away_coefs": {k: float(v) for k, v in self.away_coefs.items()},
                "trained_rows": int(self.trained_rows),
                "trained_seasons": [str(s) for s in self.trained_seasons]}

    @classmethod
    def from_dict(cls, d: dict) -> "FootballPoissonModel":
        m = cls(d["home_features"], d["away_features"], d.get("version", "v1"))
        m.home_coefs = {str(k): float(v) for k, v in d["home_coefs"].items()}
        m.away_coefs = {str(k): float(v) for k, v in d["away_coefs"].items()}
        m.trained_rows = int(d.get("trained_rows", 0))
        m.trained_seasons = list(d.get("trained_seasons", []))
        missing = ({"const", *m.home_features} - set(m.home_coefs)) | ({"const", *m.away_features} - set(m.away_coefs))
        if missing:
            raise ValueError(f"Modelo incompleto: faltan coeficientes {sorted(missing)}")
        return m

    def save_json(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


# JSON: cargarlo no ejecuta código (a diferencia de pickle/joblib).
def load_model(path) -> FootballPoissonModel:
    return FootballPoissonModel.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
