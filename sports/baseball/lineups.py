"""
Cliente para MLB Stats API: lineups + starting pitchers.

API publica oficial:
    https://statsapi.mlb.com/api/v1/schedule?date=YYYY-MM-DD&hydrate=probablePitcher,team

No requiere auth ni rate-limit estricto (uso responsable).
"""
from datetime import date, datetime
from typing import List, Optional

import requests


BASE_URL = "https://statsapi.mlb.com/api/v1"


def fetch_schedule(target_date: date, hydrate: str = "probablePitcher,team") -> dict:
    """Trae el schedule del dia con probable pitchers."""
    url = f"{BASE_URL}/schedule"
    params = {
        "sportId": 1,           # MLB
        "date": target_date.isoformat(),
        "hydrate": hydrate,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def parse_starters(schedule_json: dict) -> List[dict]:
    """
    Extrae lista de partidos con sus probable pitchers.

    Returns
    -------
    [
        {
            "game_pk": 745432,
            "game_date": date,
            "home_team": "Los Angeles Dodgers",
            "away_team": "San Francisco Giants",
            "home_starter_name": "Yoshinobu Yamamoto",
            "away_starter_name": "Logan Webb",
            "home_starter_id": 660271,
            "away_starter_id": 657277,
            "home_starter_throws": "R",
            "away_starter_throws": "R",
        },
        ...
    ]
    """
    out = []
    for date_block in schedule_json.get("dates", []):
        for game in date_block.get("games", []):
            game_pk = game.get("gamePk")
            try:
                game_date = datetime.fromisoformat(
                    game["gameDate"].replace("Z", "+00:00")
                ).date()
            except (KeyError, ValueError):
                continue

            home = game.get("teams", {}).get("home", {})
            away = game.get("teams", {}).get("away", {})

            home_team = home.get("team", {}).get("name", "")
            away_team = away.get("team", {}).get("name", "")

            hp = home.get("probablePitcher", {})
            ap = away.get("probablePitcher", {})

            out.append({
                "game_pk": game_pk,
                "game_date": game_date,
                "home_team": home_team,
                "away_team": away_team,
                "home_starter_name": hp.get("fullName"),
                "away_starter_name": ap.get("fullName"),
                "home_starter_id": hp.get("id"),
                "away_starter_id": ap.get("id"),
                "home_starter_throws": hp.get("pitchHand", {}).get("code"),
                "away_starter_throws": ap.get("pitchHand", {}).get("code"),
            })
    return out


def fetch_starters_for_date(target_date: Optional[date] = None) -> List[dict]:
    """Convenience: trae directamente la lista de starters del dia."""
    if target_date is None:
        target_date = date.today()
    return parse_starters(fetch_schedule(target_date))


def store_to_db(starters: List[dict], conn) -> int:
    """Inserta o actualiza la lista de starters en mlb_starters."""
    if not starters:
        return 0

    from psycopg2.extras import execute_values

    rows = []
    for s in starters:
        rows.append((
            s["game_date"],
            s["game_pk"],
            s["home_team"],
            s["away_team"],
            s["home_starter_name"],
            s["away_starter_name"],
            s["home_starter_id"],
            s["away_starter_id"],
            s["home_starter_throws"],
            s["away_starter_throws"],
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO mlb_starters
                (game_date, game_pk, home_team, away_team,
                 home_starter_name, away_starter_name,
                 home_starter_id, away_starter_id,
                 home_starter_throws, away_starter_throws)
            VALUES %s
            ON CONFLICT (game_date, home_team, away_team) DO UPDATE SET
                home_starter_name = EXCLUDED.home_starter_name,
                away_starter_name = EXCLUDED.away_starter_name,
                home_starter_id = EXCLUDED.home_starter_id,
                away_starter_id = EXCLUDED.away_starter_id,
                home_starter_throws = EXCLUDED.home_starter_throws,
                away_starter_throws = EXCLUDED.away_starter_throws,
                fetched_at = NOW()
            """,
            rows,
        )
    conn.commit()
    return len(rows)
