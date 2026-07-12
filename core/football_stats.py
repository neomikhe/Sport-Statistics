"""
Estimación de córners/tarjetas esperados de un enfrentamiento, desde la BD (v2).

Modelo multiplicativo (ataque × defensa × media de LIGA), pero con dos mejoras sobre v1:
  - Media por LIGA, no global: las tarjetas varían enormemente entre ligas (Grecia
    ~5.2 vs Países Bajos ~3.0 por partido), así que la media de referencia se toma de
    la liga del enfrentamiento.
  - Ponderación por RECENCIA: los partidos recientes pesan más (decaimiento exponencial),
    para captar la forma/plantilla/árbitro actuales.

Si la BD aún no tiene columnas de córners pobladas (re-ingesta pendiente), devuelve [].
"""
import pandas as pd

from sports.football.stats_markets import stats_markets

_CACHE = {}
_HALFLIFE_DAYS = 540.0   # ~1.5 temporadas: los partidos recientes pesan más


def _rates(engine):
    """Tasas por equipo (recencia), medias por liga y liga principal de cada equipo.

    Devuelve (rates, league_avg, team_league, global_avg) o (None, ...) si no hay dato.
    """
    if "rates" in _CACHE:
        return _CACHE["rates"], _CACHE["league_avg"], _CACHE["team_league"], _CACHE["global_avg"]
    try:
        df = pd.read_sql(
            "SELECT home_team_id, away_team_id, league, date, "
            "home_corners, away_corners, home_yellows, away_yellows, "
            "home_reds, away_reds FROM football_matches "
            "WHERE home_corners IS NOT NULL", engine, parse_dates=["date"])
    except Exception:
        return None, None, None, None
    if df.empty:
        return None, None, None, None

    df["home_cards"] = df["home_yellows"].fillna(0) + df["home_reds"].fillna(0)
    df["away_cards"] = df["away_yellows"].fillna(0) + df["away_reds"].fillna(0)
    df["home_reds"] = df["home_reds"].fillna(0)
    df["away_reds"] = df["away_reds"].fillna(0)
    # Peso por recencia (decaimiento exponencial por antigüedad en días).
    age = (df["date"].max() - df["date"]).dt.days.clip(lower=0)
    df["w"] = 0.5 ** (age / _HALFLIFE_DAYS)

    # --- Medias por liga (ponderadas) sobre el nivel partido ---
    def _wmean(sub, col):
        wsum = sub["w"].sum()
        return float((sub[col] * sub["w"]).sum() / wsum) if wsum else 0.0

    league_avg = {}
    for lg, sub in df.groupby("league"):
        cf = (_wmean(sub, "home_corners") + _wmean(sub, "away_corners")) / 2
        kf = (_wmean(sub, "home_cards") + _wmean(sub, "away_cards")) / 2
        rf = (_wmean(sub, "home_reds") + _wmean(sub, "away_reds")) / 2
        league_avg[lg] = {
            "home_c": _wmean(sub, "home_corners"), "away_c": _wmean(sub, "away_corners"),
            "cf": cf, "kf": kf, "rf": rf}
    global_avg = {
        "home_c": _wmean(df, "home_corners"), "away_c": _wmean(df, "away_corners"),
        "cf": (_wmean(df, "home_corners") + _wmean(df, "away_corners")) / 2,
        "kf": (_wmean(df, "home_cards") + _wmean(df, "away_cards")) / 2,
        "rf": (_wmean(df, "home_reds") + _wmean(df, "away_reds")) / 2}

    # --- Tasas por equipo (perspectiva local + visitante, ponderadas por recencia) ---
    home = df.rename(columns={
        "home_team_id": "tid", "home_corners": "cf", "away_corners": "ca",
        "home_cards": "kf", "away_cards": "ka", "home_reds": "rf", "league": "lg"})
    away = df.rename(columns={
        "away_team_id": "tid", "away_corners": "cf", "home_corners": "ca",
        "away_cards": "kf", "home_cards": "ka", "away_reds": "rf", "league": "lg"})
    cols = ["tid", "lg", "w", "cf", "ca", "kf", "ka", "rf"]
    both = pd.concat([home[cols], away[cols]], ignore_index=True)

    rates, team_league = {}, {}
    for tid, sub in both.groupby("tid"):
        wsum = sub["w"].sum() or 1.0
        rates[int(tid)] = {c: float((sub[c] * sub["w"]).sum() / wsum)
                           for c in ("cf", "ca", "kf", "ka", "rf")}
        # Liga principal = donde el equipo acumula más peso.
        team_league[int(tid)] = sub.groupby("lg")["w"].sum().idxmax()

    _CACHE.update(rates=rates, league_avg=league_avg,
                  team_league=team_league, global_avg=global_avg)
    return rates, league_avg, team_league, global_avg


def stats_markets_for(engine, home_id: int, away_id: int) -> list:
    """Mercados de córners/tarjetas del enfrentamiento. [] si faltan datos."""
    rates, league_avg, team_league, global_avg = _rates(engine)
    if not rates or home_id not in rates or away_id not in rates:
        return []

    # Media de referencia = la de la liga del enfrentamiento (la del local).
    lg = team_league.get(home_id) or team_league.get(away_id)
    base = league_avg.get(lg, global_avg)

    h, a = rates[home_id], rates[away_id]
    lg_cf = base["cf"] or 5.0
    lg_kf = base["kf"] or 2.0

    def strength(val, ref):
        return (val / ref) if ref else 1.0

    e_home_c = base["home_c"] * strength(h["cf"], lg_cf) * strength(a["ca"], lg_cf)
    e_away_c = base["away_c"] * strength(a["cf"], lg_cf) * strength(h["ca"], lg_cf)

    e_home_k = lg_kf * strength(h["kf"], lg_kf) * strength(a["ka"], lg_kf)
    e_away_k = lg_kf * strength(a["kf"], lg_kf) * strength(h["ka"], lg_kf)
    e_cards_total = e_home_k + e_away_k

    e_reds_total = float(h["rf"]) + float(a["rf"])

    return stats_markets(e_home_c, e_away_c, e_cards_total, e_reds_total)
