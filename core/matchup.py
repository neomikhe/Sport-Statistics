import time

_MODELS: dict = {}
_TTL_S = 3600


def build_model(sport: str, engine):
    if sport == "football":
        from core.forecast.football import FootballForecaster
        return FootballForecaster.from_db(engine)
    if sport == "basketball":
        from core.forecast.basketball import NBAForecaster, load_games
        df = load_games(engine)
        return NBAForecaster.from_games(df) if not df.empty else None
    if sport == "baseball":
        from core.forecast.baseball import MLBForecaster, load_games
        df = load_games(engine)
        return MLBForecaster.from_games(df) if not df.empty else None
    if sport == "tennis":
        from core.forecast.tennis import TennisForecaster, load_matches
        df = load_matches(engine)
        return TennisForecaster.from_matches(df) if not df.empty else None
    return None


def get_model(sport: str, engine):
    hit = _MODELS.get(sport)
    if hit and time.time() - hit[1] < _TTL_S:
        return hit[0]
    model = build_model(sport, engine)
    _MODELS[sport] = (model, time.time())
    return model


def forecast_match(sport: str, engine, home_id: int, away_id: int,
                   home_name: str = "Local", away_name: str = "Visitante",
                   game_date=None, model=None, with_stats: bool = True):
    model = model or get_model(sport, engine)
    if model is None:
        return None
    if sport == "football":
        extra = []
        if with_stats:
            from core.football_stats import stats_markets_for
            extra = stats_markets_for(engine, int(home_id), int(away_id))
        return model.forecast(int(home_id), int(away_id), home_name, away_name,
                              extra_markets=extra)
    if sport == "baseball":
        fips = (None, None)
        if game_date is not None:
            from sports.baseball.starter_adjustment import lookup_starter_fips
            fips = lookup_starter_fips(engine, home_id, away_id, game_date)
        fc = model.forecast(int(home_id), int(away_id), home_name, away_name, starter_fips=fips)
        if with_stats:
            from core.baseball_stats import stats_markets_for
            fc.markets = fc.markets + stats_markets_for(engine, int(home_id), int(away_id))
        return fc
    return None


def predict(sport: str, engine, home_id: int, away_id: int, game_date=None) -> list:
    fc = forecast_match(sport, engine, home_id, away_id, game_date=game_date)
    return fc.markets if fc is not None else []
