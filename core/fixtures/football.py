"""
Partidos del día de fútbol vía football-data.org — requiere clave GRATUITA.

La clave se lee de st.secrets['football_data_token'] o FOOTBALL_DATA_TOKEN.
Sin clave -> devuelve [] (degradación limpia, la app no rompe).
Free tier: 12 competiciones top, 10 req/min. Regístrate en football-data.org.
"""
import json
import logging
import os
import urllib.request
from datetime import date as _date

_log = logging.getLogger(__name__)
_URL = "https://api.football-data.org/v4/matches?dateFrom={d}&dateTo={d}"


def _token():
    try:
        import streamlit as st
        if "football_data_token" in st.secrets:
            return st.secrets["football_data_token"]
    except Exception:
        pass
    return os.getenv("FOOTBALL_DATA_TOKEN")


def _fetch_matches(day, timeout: int):
    """Lista cruda de partidos de la fecha desde football-data.org. [] sin clave/red."""
    token = _token()
    if not token:
        return []
    d = (day or _date.today()).strftime("%Y-%m-%d")
    req = urllib.request.Request(_URL.format(d=d), headers={"X-Auth-Token": str(token)})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore")).get("matches", [])
    except Exception as e:
        _log.warning("football-data.org: %s", e)
        return []


def todays_games(day=None, timeout: int = 15) -> list:
    """[{'home','away','time_utc','status','league'}] de la fecha. [] si no hay clave/red."""
    out = []
    for m in _fetch_matches(day, timeout):
        ht, at = m.get("homeTeam", {}), m.get("awayTeam", {})
        home, away = ht.get("name", ""), at.get("name", "")
        if not home or not away:
            continue
        out.append({
            "home": home,
            "away": away,
            "time_utc": m.get("utcDate", ""),
            "status": m.get("status", ""),
            "league": m.get("competition", {}).get("name", ""),
            "home_logo": ht.get("crest", "") or "",
            "away_logo": at.get("crest", "") or "",
        })
    return out


def finished_scores(day=None, timeout: int = 15) -> list:
    """Marcadores finales de la fecha (para resolver el historial el mismo día).

    [{'date','home','away','home_goals','away_goals'}] de los partidos FINISHED.
    Solo goles: córners/tarjetas se resuelven aparte con el CSV. [] sin clave/red.
    """
    d = (day or _date.today()).strftime("%Y-%m-%d")
    out = []
    for m in _fetch_matches(day, timeout):
        if m.get("status") != "FINISHED":
            continue
        ft = m.get("score", {}).get("fullTime", {})
        hg, ag = ft.get("home"), ft.get("away")
        home = m.get("homeTeam", {}).get("name", "")
        away = m.get("awayTeam", {}).get("name", "")
        if hg is None or ag is None or not home or not away:
            continue
        out.append({"date": d, "home": home, "away": away,
                    "home_goals": int(hg), "away_goals": int(ag)})
    return out
