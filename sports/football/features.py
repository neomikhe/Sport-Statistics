import numpy as np
import pandas as pd


DEFAULT_ELO = 1500.0
DEFAULT_REST_DAYS = 7
MAX_REST_DAYS_CAP = 30

FEATURE_COLS = [
    "home_elo", "away_elo", "elo_diff",
    "home_gf_5", "home_ga_5", "home_gf_10", "home_ga_10",
    "away_gf_5", "away_ga_5", "away_gf_10", "away_ga_10",
    "home_form_5", "away_form_5",
    "home_rest", "away_rest",
]


def _load_matches(engine):
    return pd.read_sql(
        """
        SELECT id, date, league, season,
               home_team_id, away_team_id,
               home_goals, away_goals,
               odds_home_close, odds_draw_close, odds_away_close
        FROM football_matches
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
        ORDER BY date, id
        """,
        engine,
        parse_dates=["date"],
    )


def _load_elo(engine):
    return pd.read_sql(
        "SELECT team_id, date, elo FROM football_elo",
        engine,
        parse_dates=["date"],
    )


def _build_team_timeline(df_matches):
    home = df_matches[["id", "date", "home_team_id", "away_team_id",
                       "home_goals", "away_goals"]].rename(columns={
        "home_team_id": "team_id",
        "away_team_id": "opponent_id",
        "home_goals": "goals_for",
        "away_goals": "goals_against",
    })
    home["is_home"] = True

    away = df_matches[["id", "date", "home_team_id", "away_team_id",
                       "home_goals", "away_goals"]].rename(columns={
        "away_team_id": "team_id",
        "home_team_id": "opponent_id",
        "away_goals": "goals_for",
        "home_goals": "goals_against",
    })
    away["is_home"] = False

    timeline = pd.concat([home, away], ignore_index=True)
    timeline = timeline.sort_values(["team_id", "date", "id"]).reset_index(drop=True)
    return timeline


def _add_elo_pre(timeline, df_elo):
    timeline = timeline.sort_values("date", kind="mergesort").reset_index(drop=True)
    df_elo_sorted = df_elo.sort_values("date", kind="mergesort").reset_index(drop=True)

    merged = pd.merge_asof(
        timeline,
        df_elo_sorted.rename(columns={"elo": "elo_pre"}),
        by="team_id",
        on="date",
        direction="backward",
        allow_exact_matches=False,
    )
    merged["elo_pre"] = merged["elo_pre"].fillna(DEFAULT_ELO).astype(float)
    return merged


def _add_rolling_goals(timeline, windows=(5, 10)):
    timeline = timeline.sort_values(["team_id", "date", "id"]).reset_index(drop=True)
    for w in windows:
        timeline[f"gf_{w}"] = (
            timeline.groupby("team_id")["goals_for"]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
        )
        timeline[f"ga_{w}"] = (
            timeline.groupby("team_id")["goals_against"]
            .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
        )
    return timeline


def _add_form_points(timeline, window=5):
    pts = np.where(
        timeline["goals_for"] > timeline["goals_against"], 3,
        np.where(timeline["goals_for"] == timeline["goals_against"], 1, 0),
    )
    timeline["_pts"] = pts
    timeline[f"form_{window}"] = (
        timeline.groupby("team_id")["_pts"]
        .transform(lambda x: x.shift(1).rolling(window, min_periods=1).sum())
    )
    return timeline.drop(columns=["_pts"])


def _add_rest_days(timeline):
    timeline["_prev_date"] = timeline.groupby("team_id")["date"].shift(1)
    rest = (timeline["date"] - timeline["_prev_date"]).dt.days
    rest = rest.clip(upper=MAX_REST_DAYS_CAP).fillna(DEFAULT_REST_DAYS).astype(int)
    timeline["rest_days"] = rest
    return timeline.drop(columns=["_prev_date"])


def _pivot_to_match_view(timeline, df_matches):
    cols = ["id", "elo_pre", "gf_5", "ga_5", "gf_10", "ga_10", "form_5", "rest_days"]

    home = timeline[timeline["is_home"]][cols].rename(columns={
        "elo_pre": "home_elo",
        "gf_5": "home_gf_5", "ga_5": "home_ga_5",
        "gf_10": "home_gf_10", "ga_10": "home_ga_10",
        "form_5": "home_form_5",
        "rest_days": "home_rest",
    })

    away = timeline[~timeline["is_home"]][cols].rename(columns={
        "elo_pre": "away_elo",
        "gf_5": "away_gf_5", "ga_5": "away_ga_5",
        "gf_10": "away_gf_10", "ga_10": "away_ga_10",
        "form_5": "away_form_5",
        "rest_days": "away_rest",
    })

    result = df_matches.merge(home, on="id", how="inner").merge(away, on="id", how="inner")
    result["elo_diff"] = result["home_elo"] - result["away_elo"]
    return result


def build_features(engine) -> pd.DataFrame:
    df_matches = _load_matches(engine)
    df_elo = _load_elo(engine)

    timeline = _build_team_timeline(df_matches)
    timeline = _add_elo_pre(timeline, df_elo)
    timeline = _add_rolling_goals(timeline, windows=(5, 10))
    timeline = _add_form_points(timeline, window=5)
    timeline = _add_rest_days(timeline)

    features = _pivot_to_match_view(timeline, df_matches)
    return features.sort_values("date").reset_index(drop=True)
