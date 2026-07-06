"""
Experimento OOS: ¿features nuevas de los datos ACTUALES mejoran el 1X2 de fútbol?

understat (xG) queda descartado: Cloudflare + solo 18.6% de cobertura de ligas.
En su lugar probamos features con 100% de cobertura, derivadas de football_features.csv:

  - Splits LOCAL/VISITANTE del rolling (el actual mezcla casa y fuera):
      home_gf_venue_5 / home_ga_venue_5  (forma del local jugando EN CASA)
      away_gf_venue_5 / away_ga_venue_5  (forma del visitante jugando FUERA)

Todo leak-free (shift(1) antes del rolling). Entrena GLM Poisson en season<2024-2025
y evalúa el log-loss del 1X2 (Dixon-Coles ρ=-0.10) en 2024-2025 (OOS). Solo mide.

Uso:
    venv\\Scripts\\activate
    python scripts/eval_football_features_experiment.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.football.models import HOME_MODEL_FEATURES, AWAY_MODEL_FEATURES  # noqa: E402
from sports.football.markets import score_matrix  # noqa: E402

TEST_SEASON = "2024-2025"
RHO = -0.10
NEW_HOME = ["home_gf_venue_5", "away_ga_venue_5"]   # ataque local en casa + defensa visit. fuera
NEW_AWAY = ["away_gf_venue_5", "home_ga_venue_5"]


def _venue_features(df):
    """Rolling(5) de GF/GA por equipo SEGÚN localía, leak-free (shift(1))."""
    home = df[["id", "date", "home_team_id", "home_goals", "away_goals"]].rename(
        columns={"home_team_id": "team", "home_goals": "gf", "away_goals": "ga"})
    home["venue"] = "H"
    away = df[["id", "date", "away_team_id", "away_goals", "home_goals"]].rename(
        columns={"away_team_id": "team", "away_goals": "gf", "home_goals": "ga"})
    away["venue"] = "A"
    long = pd.concat([home, away]).sort_values(["team", "venue", "date"])
    g = long.groupby(["team", "venue"], sort=False)
    long["gf_v5"] = g["gf"].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    long["ga_v5"] = g["ga"].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())

    h = long[long.venue == "H"][["id", "gf_v5", "ga_v5"]].rename(
        columns={"gf_v5": "home_gf_venue_5", "ga_v5": "home_ga_venue_5"})
    a = long[long.venue == "A"][["id", "gf_v5", "ga_v5"]].rename(
        columns={"gf_v5": "away_gf_venue_5", "ga_v5": "away_ga_venue_5"})
    return df.merge(h, on="id").merge(a, on="id")


def _fit_poisson(X_tr, y_tr):
    import statsmodels.api as sm
    return sm.GLM(y_tr, sm.add_constant(X_tr), family=sm.families.Poisson()).fit()


def _predict(model, X):
    import statsmodels.api as sm
    return model.predict(sm.add_constant(X, has_constant="add"))


def _logloss_1x2(lh, la, outcomes):
    idx = {"H": 0, "D": 1, "A": 2}
    tot = 0.0
    for a, b, o in zip(lh, la, outcomes):
        m = score_matrix(a, b, rho=RHO)
        p = (float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum()))
        tot += -np.log(max(p[idx[o]], 1e-12))
    return tot / len(outcomes)


def _run(df_tr, df_te, home_feats, away_feats, outcomes):
    mh = _fit_poisson(df_tr[home_feats], df_tr["home_goals"])
    ma = _fit_poisson(df_tr[away_feats], df_tr["away_goals"])
    lh = _predict(mh, df_te[home_feats]).values
    la = _predict(ma, df_te[away_feats]).values
    return _logloss_1x2(lh, la, outcomes)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    df = pd.read_csv(root / "data" / "processed" / "football_features.csv", parse_dates=["date"])
    df = _venue_features(df.sort_values("date"))

    base = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    allf = base + NEW_HOME + NEW_AWAY
    # imputa NaN (primeros partidos por equipo/localía) con la media
    for c in NEW_HOME + NEW_AWAY:
        df[c] = df[c].fillna(df[c].mean())
    df = df[df[allf].notna().all(axis=1) & df["home_goals"].notna()].copy()

    tr = df[df["season"] < TEST_SEASON]
    te = df[df["season"] == TEST_SEASON]
    outcomes = np.where(te["home_goals"].values > te["away_goals"].values, "H",
                        np.where(te["home_goals"].values == te["away_goals"].values, "D", "A"))
    print(f"Train: {len(tr):,}  |  Test OOS ({TEST_SEASON}): {len(te):,}")

    ll_base = _run(tr, te, HOME_MODEL_FEATURES, AWAY_MODEL_FEATURES, outcomes)
    ll_new = _run(tr, te,
                  HOME_MODEL_FEATURES + NEW_HOME,
                  AWAY_MODEL_FEATURES + NEW_AWAY, outcomes)

    print("=" * 60)
    print(f"  Log-loss 1X2 OOS  base       : {ll_base:.4f}")
    print(f"  Log-loss 1X2 OOS  + venue    : {ll_new:.4f}   ({ll_new - ll_base:+.4f})")
    print("=" * 60)
    print("  MEJORA -> merece integrarse" if ll_new < ll_base
          else "  no mejora -> descartar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
