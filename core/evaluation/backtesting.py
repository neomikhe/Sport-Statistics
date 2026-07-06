"""
Walk-forward temporal backtesting.

Para cada temporada i >= min_train_seasons:
    Train: seasons[0..i-1]
    Test:  seasons[i]

Entrena el modelo Poisson, predice probabilidades 1X2 exactas y calcula metricas.
Compara con naive (media historica 1X2) y mercado (cuotas Pinnacle de cierre).
"""
import numpy as np
import pandas as pd

from sports.football.models import (
    FootballPoissonModel,
    HOME_MODEL_FEATURES,
    AWAY_MODEL_FEATURES,
)
from sports.football.simulation import exact_probabilities
from core.evaluation.metrics import (
    log_loss_multiclass,
    brier_score_multiclass,
    accuracy,
    naive_probabilities,
    implied_probabilities,
    outcomes_from_goals,
)


def _predict_1x2_probs(model, df):
    """Predice lambdas y convierte a probabilidades 1X2 via Poisson exacto."""
    pred = model.predict_lambda(df)
    probs = np.zeros((len(df), 3))
    lh_arr = pred["lambda_home"].values
    la_arr = pred["lambda_away"].values
    for i in range(len(df)):
        p = exact_probabilities(lh_arr[i], la_arr[i])
        probs[i] = [p["prob_home"], p["prob_draw"], p["prob_away"]]
    return probs


def walk_forward_backtest(df, min_train_seasons=4):
    """
    Ejecuta walk-forward temporal.

    Returns
    -------
    per_season: DataFrame con una fila por temporada de test con metricas.
    all_predictions: DataFrame con predicciones fila-a-fila para analisis posterior.
    """
    all_feats = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    complete = df[all_feats + ["home_goals", "away_goals"]].notna().all(axis=1)
    df = df[complete].copy()

    seasons = sorted(df["season"].unique())
    if len(seasons) < min_train_seasons + 1:
        raise ValueError(
            f"Se necesitan al menos {min_train_seasons + 1} temporadas, hay {len(seasons)}."
        )

    per_season_rows = []
    all_predictions = []

    for i in range(min_train_seasons, len(seasons)):
        test_season = seasons[i]
        train_seasons = seasons[:i]

        df_train = df[df["season"].isin(train_seasons)]
        df_test = df[df["season"] == test_season]

        if len(df_test) == 0 or len(df_train) < 1000:
            continue

        print(f"  [fold] train {train_seasons[0]}..{train_seasons[-1]} "
              f"({len(df_train):,} partidos)  ->  test {test_season} ({len(df_test):,})")

        model = FootballPoissonModel().fit(df_train)
        probs = _predict_1x2_probs(model, df_test)
        outcomes = outcomes_from_goals(
            df_test["home_goals"].values, df_test["away_goals"].values
        )

        ll_model = log_loss_multiclass(probs, outcomes)
        br_model = brier_score_multiclass(probs, outcomes)
        ac_model = accuracy(probs, outcomes)

        train_outcomes = outcomes_from_goals(
            df_train["home_goals"].values, df_train["away_goals"].values
        )
        naive_p = naive_probabilities(train_outcomes)
        naive_tiled = np.tile(naive_p, (len(df_test), 1))
        ll_naive = log_loss_multiclass(naive_tiled, outcomes)
        br_naive = brier_score_multiclass(naive_tiled, outcomes)
        ac_naive = accuracy(naive_tiled, outcomes)

        has_odds = df_test[
            ["odds_home_close", "odds_draw_close", "odds_away_close"]
        ].notna().all(axis=1)

        if has_odds.sum() > 0:
            df_odds = df_test[has_odds]
            probs_odds = probs[has_odds.values]
            outcomes_odds = outcomes[has_odds.values]
            market_probs = implied_probabilities(
                df_odds["odds_home_close"].values,
                df_odds["odds_draw_close"].values,
                df_odds["odds_away_close"].values,
            )
            ll_market = log_loss_multiclass(market_probs, outcomes_odds)
            br_market = brier_score_multiclass(market_probs, outcomes_odds)
            ac_market = accuracy(market_probs, outcomes_odds)
            ll_model_on_odds = log_loss_multiclass(probs_odds, outcomes_odds)
        else:
            ll_market = br_market = ac_market = np.nan
            ll_model_on_odds = np.nan

        per_season_rows.append({
            "season": test_season,
            "n_test": len(df_test),
            "n_train": len(df_train),
            "ll_model": ll_model,
            "ll_naive": ll_naive,
            "ll_market": ll_market,
            "ll_model_vs_market": ll_model_on_odds,
            "br_model": br_model,
            "br_naive": br_naive,
            "br_market": br_market,
            "acc_model": ac_model,
            "acc_naive": ac_naive,
            "acc_market": ac_market,
        })

        pred_df = df_test.copy()
        pred_df["prob_home"] = probs[:, 0]
        pred_df["prob_draw"] = probs[:, 1]
        pred_df["prob_away"] = probs[:, 2]
        pred_df["outcome"] = outcomes
        all_predictions.append(pred_df)

    per_season_df = pd.DataFrame(per_season_rows)
    all_predictions_df = (
        pd.concat(all_predictions, ignore_index=True)
        if all_predictions else pd.DataFrame()
    )

    return per_season_df, all_predictions_df
