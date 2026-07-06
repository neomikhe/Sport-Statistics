"""
Modelo GLM Poisson para prediccion de goles en futbol.

Dos modelos independientes:
  - home_model: predice lambda (media) de goles del equipo local
  - away_model: predice lambda de goles del equipo visitante

Usa statsmodels.GLM(family=Poisson) para entrenar. Guarda solo los coeficientes
(no el objeto statsmodels entero) para que el modelo sea robusto entre versiones
y ligero en disco.

Prediccion: lambda = exp(intercept + sum(coef_i * feature_i))

Uso tipico:
    model = FootballPoissonModel()
    model.fit(df_train)
    pred = model.predict_lambda(df_new)
    # pred tiene columnas lambda_home y lambda_away
"""
import numpy as np
import pandas as pd

# statsmodels solo hace falta para ENTRENAR (fit). La prediccion (predict_lambda)
# usa numpy puro, asi que se importa de forma perezosa dentro de _fit_poisson.
# Esto permite cargar un modelo ya entrenado en la nube sin instalar statsmodels.


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
    """Entrena un GLM Poisson y devuelve (coefs_dict, texto_summary, resultado)."""
    import statsmodels.api as sm  # import perezoso: solo necesario al entrenar

    X = sm.add_constant(df_train[features], has_constant="add")
    y = df_train[target]
    result = sm.GLM(y, X, family=sm.families.Poisson()).fit()

    coefs = result.params.to_dict()
    summary_text = str(result.summary())
    return coefs, summary_text, result


def _predict_lambda(coefs, features, df):
    """Aplica los coeficientes: lambda = exp(const + sum(c_i * x_i))."""
    linear = np.full(len(df), coefs["const"], dtype=float)
    for name in features:
        linear = linear + coefs[name] * df[name].to_numpy(dtype=float)
    return np.exp(linear)


class FootballPoissonModel:
    """Modelo dual de Poisson para goles locales y visitantes."""

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
        """Devuelve un DataFrame con columnas lambda_home y lambda_away (indexado como df)."""
        if not self.home_coefs or not self.away_coefs:
            raise RuntimeError("El modelo no ha sido entrenado todavia.")

        lam_home = _predict_lambda(self.home_coefs, self.home_features, df)
        lam_away = _predict_lambda(self.away_coefs, self.away_features, df)
        return pd.DataFrame(
            {"lambda_home": lam_home, "lambda_away": lam_away},
            index=df.index,
        )
