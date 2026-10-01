from typing import Optional


LEAGUE_AVG_FIP = 4.20
ADJUSTMENT_FACTOR = 0.5


def get_starter_fip(conn, pitcher_name: str, season: int) -> Optional[float]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT fip FROM mlb_pitcher_stats
            WHERE pitcher_name = %s AND season = %s
            """,
            (pitcher_name, season),
        )
        row = cur.fetchone()
        return float(row[0]) if row and row[0] is not None else None


def adjust_winrate_by_starter(
    base_winrate: float,
    starter_fip: Optional[float],
    league_avg_fip: float = LEAGUE_AVG_FIP,
    factor: float = ADJUSTMENT_FACTOR,
) -> float:
    if starter_fip is None or starter_fip <= 0:
        return base_winrate

    multiplier = (league_avg_fip / starter_fip) ** factor
    adjusted = base_winrate * multiplier
    return max(0.05, min(0.95, adjusted))


def matchup_adjustment(
    home_winrate: float,
    home_starter_fip: Optional[float],
    away_starter_fip: Optional[float],
    league_avg_fip: float = LEAGUE_AVG_FIP,
) -> float:
    home_adj = adjust_winrate_by_starter(home_winrate, home_starter_fip, league_avg_fip)
    if away_starter_fip is not None and away_starter_fip > 0:
        rival_factor = (away_starter_fip / league_avg_fip) ** ADJUSTMENT_FACTOR
        home_adj = home_adj * rival_factor

    return max(0.10, min(0.90, home_adj))


STARTER_SHARE = 0.60


def adjust_runs(e_home_runs: float, e_away_runs: float,
                home_fip: Optional[float], away_fip: Optional[float],
                league_fip: float = LEAGUE_AVG_FIP,
                starter_share: float = STARTER_SHARE):
    def blend(fip):
        if fip is None or fip <= 0:
            return 1.0
        ratio = fip / league_fip
        return starter_share * ratio + (1.0 - starter_share)

    e_away = max(0.5, e_away_runs * blend(home_fip))
    e_home = max(0.5, e_home_runs * blend(away_fip))
    return e_home, e_away


def lookup_starter_fips(engine, home_id: int, away_id: int, game_date):
    import pandas as pd

    q = """
        SELECT
          (SELECT fip FROM mlb_pitcher_stats WHERE pitcher_id = s.home_starter_id
           ORDER BY season DESC LIMIT 1) AS home_fip,
          (SELECT fip FROM mlb_pitcher_stats WHERE pitcher_id = s.away_starter_id
           ORDER BY season DESC LIMIT 1) AS away_fip
        FROM mlb_starters s
        WHERE s.game_date = %(d)s
          AND s.home_team = (SELECT name FROM entities WHERE id = %(h)s)
          AND s.away_team = (SELECT name FROM entities WHERE id = %(a)s)
        LIMIT 1
    """
    try:
        df = pd.read_sql(q, engine, params={"h": int(home_id), "a": int(away_id),
                                            "d": str(game_date)})
    except Exception:
        return None, None
    if df.empty:
        return None, None

    def _f(v):
        return None if pd.isna(v) else float(v)

    return _f(df["home_fip"].iloc[0]), _f(df["away_fip"].iloc[0])
