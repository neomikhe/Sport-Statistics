import pandas as pd

from sports.tennis.stats_markets import stats_markets

_CACHE = {}
_MIN_SURFACE = 5

_BO5_FACTOR = 1.4


def _long(engine):
    if "long" in _CACHE:
        return _CACHE["long"]
    try:
        df = pd.read_sql(
            "SELECT player1_id, player2_id, surface, p1_aces, p1_df, p2_aces, p2_df "
            "FROM tennis_matches WHERE p1_aces IS NOT NULL", engine)
    except Exception:
        return None
    if df.empty:
        return None
    df["surface"] = df["surface"].astype(str).str.lower()
    p1 = df[["player1_id", "surface", "p1_aces", "p1_df"]].rename(
        columns={"player1_id": "pid", "p1_aces": "aces", "p1_df": "df"})
    p2 = df[["player2_id", "surface", "p2_aces", "p2_df"]].rename(
        columns={"player2_id": "pid", "p2_aces": "aces", "p2_df": "df"})
    long = pd.concat([p1, p2], ignore_index=True).dropna(subset=["aces"])
    _CACHE["long"] = long
    _CACHE["league"] = (float(long["aces"].mean()), float(long["df"].mean()))
    return long


def _rate(long, pid: int, surface: str):
    sub = long[long["pid"] == pid]
    if surface:
        ss = sub[sub["surface"] == surface.lower()]
        if len(ss) >= _MIN_SURFACE:
            return float(ss["aces"].mean()), float(ss["df"].mean())
    if len(sub) >= 1:
        return float(sub["aces"].mean()), float(sub["df"].mean())
    return _CACHE["league"]


def stats_markets_for(engine, p1_id: int, p2_id: int, surface: str,
                      name_a: str, name_b: str, best_of: int = 3) -> list:
    long = _long(engine)
    if long is None:
        return []
    fmt = _BO5_FACTOR if int(best_of) == 5 else 1.0
    a_aces, a_df = _rate(long, p1_id, surface)
    b_aces, b_df = _rate(long, p2_id, surface)
    return stats_markets(a_aces * fmt, b_aces * fmt, a_df * fmt, b_df * fmt,
                         name_a, name_b)
