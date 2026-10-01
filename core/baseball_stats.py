import pandas as pd

from sports.baseball.stats_markets import stats_markets

_CACHE = {}


def _rates(engine):
    if "rates" in _CACHE:
        return _CACHE["rates"], _CACHE["league"]
    try:
        df = pd.read_sql(
            "SELECT home_team_id, away_team_id, home_hits, away_hits, "
            "home_hr, away_hr, home_so, away_so, date FROM baseball_games "
            "WHERE home_hits IS NOT NULL", engine, parse_dates=["date"])
    except Exception:
        return None, None
    if df.empty:
        return None, None
    df = df[df["date"].dt.year == df["date"].dt.year.max()]

    home = pd.DataFrame({
        "tid": df.home_team_id, "hf": df.home_hits, "ha": df.away_hits,
        "hrf": df.home_hr, "hra": df.away_hr, "kf": df.home_so, "ka": df.away_so})
    away = pd.DataFrame({
        "tid": df.away_team_id, "hf": df.away_hits, "ha": df.home_hits,
        "hrf": df.away_hr, "hra": df.home_hr, "kf": df.away_so, "ka": df.home_so})
    both = pd.concat([home, away], ignore_index=True).dropna()
    if both.empty:
        return None, None

    agg = both.groupby("tid").mean(numeric_only=True)
    rates = {int(t): r.to_dict() for t, r in agg.iterrows()}
    league = {"h": float(both.hf.mean()), "hr": float(both.hrf.mean()),
              "k": float(both.kf.mean())}
    _CACHE["rates"], _CACHE["league"] = rates, league
    return rates, league


def stats_markets_for(engine, home_id: int, away_id: int) -> list:
    rates, league = _rates(engine)
    if not rates or home_id not in rates or away_id not in rates:
        return []
    h, a = rates[home_id], rates[away_id]
    lg_h = league["h"] or 8.5
    lg_hr = league["hr"] or 1.2
    lg_k = league["k"] or 8.5

    e_home_h = h["hf"] * a["ha"] / lg_h
    e_away_h = a["hf"] * h["ha"] / lg_h
    e_home_hr = h["hrf"] * a["hra"] / lg_hr
    e_away_hr = a["hrf"] * h["hra"] / lg_hr
    e_home_k = h["kf"] * a["ka"] / lg_k
    e_away_k = a["kf"] * h["ka"] / lg_k

    return stats_markets(e_home_h, e_away_h, e_home_hr, e_away_hr, e_home_k + e_away_k)
