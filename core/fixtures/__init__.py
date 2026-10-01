from datetime import date as _date


def todays_fixtures(sport: str, day=None) -> list:
    day = day or _date.today()
    if sport == "baseball":
        from core.fixtures.mlb import todays_games
        return todays_games(day)
    if sport == "football":
        from core.fixtures.football import todays_games
        return todays_games(day)
    return []
