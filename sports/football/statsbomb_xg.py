"""
Integracion de StatsBomb Open Data para xG.

Pipeline:
  1. Descarga competitions.json
  2. Descarga matches/{competition_id}/{season_id}.json para cada (comp, season)
  3. Descarga events/{match_id}.json y suma xG por equipo
  4. Mapea team names StatsBomb -> football-data.co.uk usando team_mapping.json
  5. Insert en football_xg

NOTA: el mapeo manual se almacena en data/raw/statsbomb/team_mapping.json
y debe completarse para que la integracion sea util.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

import requests


REPO_RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
MAPPING_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "raw" / "statsbomb" / "team_mapping.json"
)


def load_team_mapping() -> Dict[str, str]:
    """
    Lee data/raw/statsbomb/team_mapping.json.
    Estructura: {"Manchester United": "Man United", ...}
        clave = nombre StatsBomb, valor = nombre football-data.co.uk corto.
    """
    if not MAPPING_FILE.exists():
        return {}
    return json.loads(MAPPING_FILE.read_text(encoding="utf-8"))


def save_team_mapping(mapping: Dict[str, str]) -> None:
    MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAPPING_FILE.write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def fetch_competitions() -> list:
    r = requests.get(f"{REPO_RAW}/competitions.json", timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_matches(competition_id: int, season_id: int) -> list:
    url = f"{REPO_RAW}/matches/{competition_id}/{season_id}.json"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return []
    return r.json()


def fetch_events(match_id: int) -> list:
    url = f"{REPO_RAW}/events/{match_id}.json"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return []
    return r.json()


def aggregate_xg_for_match(events: list, home_team: str, away_team: str) -> Optional[Dict[str, float]]:
    """Suma xG de todos los eventos de tipo 'Shot' por equipo."""
    home_xg, away_xg = 0.0, 0.0
    for ev in events:
        if ev.get("type", {}).get("name") != "Shot":
            continue
        team_name = ev.get("team", {}).get("name", "")
        xg = ev.get("shot", {}).get("statsbomb_xg", 0.0)
        if team_name == home_team:
            home_xg += xg
        elif team_name == away_team:
            away_xg += xg
    return {"home_xg": round(home_xg, 3), "away_xg": round(away_xg, 3)}


def process_competition(competition_id: int, season_id: int,
                        team_mapping: Dict[str, str], conn) -> int:
    """
    Procesa una competition+season completa: matches + events + agregacion + insert.
    Returns: numero de matches insertados.
    """
    matches = fetch_matches(competition_id, season_id)
    if not matches:
        return 0

    inserted = 0
    for match in matches:
        match_id = match.get("match_id")
        sb_home = match.get("home_team", {}).get("home_team_name", "")
        sb_away = match.get("away_team", {}).get("away_team_name", "")
        try:
            match_date = match.get("match_date", "")[:10]
        except Exception:
            match_date = None

        # Mapear nombres
        fd_home = team_mapping.get(sb_home)
        fd_away = team_mapping.get(sb_away)
        if not fd_home or not fd_away:
            continue  # sin mapeo, skip

        # Localizar match_id en football_matches via fd_home + fd_away + fecha
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.id FROM football_matches m
                JOIN entities h ON h.id = m.home_team_id
                JOIN entities a ON a.id = m.away_team_id
                WHERE m.date = %s AND h.external_id = %s AND a.external_id = %s
                """,
                (match_date, f"fd:{fd_home}", f"fd:{fd_away}"),
            )
            row = cur.fetchone()
        if not row:
            continue
        fd_match_id = row[0]

        # Descargar eventos y agregar xG
        events = fetch_events(match_id)
        if not events:
            continue
        agg = aggregate_xg_for_match(events, sb_home, sb_away)
        if agg is None:
            continue

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO football_xg
                    (match_id, statsbomb_match_id, home_xg, away_xg)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (match_id) DO UPDATE SET
                    home_xg = EXCLUDED.home_xg,
                    away_xg = EXCLUDED.away_xg,
                    fetched_at = NOW()
                """,
                (fd_match_id, match_id, agg["home_xg"], agg["away_xg"]),
            )
        inserted += 1
    conn.commit()
    return inserted
