"""
Partidos del día de MLB vía statsapi.mlb.com — gratis, sin clave, estable.

Los nombres que devuelve ("Boston Red Sox") coinciden con los de la BD
(RETROSHEET_TO_FULL), así que el emparejamiento con `entities` es casi directo.
"""
import json
import logging
import urllib.request
from datetime import date as _date

_log = logging.getLogger(__name__)
_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}"
_BOX_URL = "https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"


def todays_games(day=None, timeout: int = 15) -> list:
    """[{'home','away','time_utc','status'}] de la fecha (hoy por defecto).

    Best-effort: si no hay red, devuelve []."""
    d = (day or _date.today()).strftime("%Y-%m-%d")
    try:
        with urllib.request.urlopen(_URL.format(date=d), timeout=timeout) as r:
            raw = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        _log.warning("fixtures MLB: %s", e)
        return []

    def _logo(team):
        tid = team.get("id")
        return f"https://www.mlbstatic.com/team-logos/{tid}.svg" if tid else ""

    out = []
    for block in raw.get("dates", []):
        for g in block.get("games", []):
            teams = g.get("teams", {})
            ht, at = teams.get("home", {}).get("team", {}), teams.get("away", {}).get("team", {})
            home, away = ht.get("name", ""), at.get("name", "")
            if not home or not away:
                continue
            out.append({
                "home": home,
                "away": away,
                "time_utc": g.get("gameDate", ""),
                "status": g.get("status", {}).get("detailedState", ""),
                "home_logo": _logo(ht),
                "away_logo": _logo(at),
            })
    return out


def finished_boxscores(day=None, timeout: int = 15) -> list:
    """Resultados de los juegos FINALIZADOS de la fecha (runs/hits/HR/ponches por equipo).

    Para resolver el historial el mismo día sin esperar a Retrosheet. Best-effort:
    cualquier juego/fecha que falle se omite. Devuelve una lista de dicts con
    `date`, `home`, `away` y las estadísticas de ambos equipos.
    """
    d = (day or _date.today()).strftime("%Y-%m-%d")
    try:
        with urllib.request.urlopen(_URL.format(date=d), timeout=timeout) as r:
            sched = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        _log.warning("boxscores MLB (schedule): %s", e)
        return []

    out = []
    for block in sched.get("dates", []):
        for g in block.get("games", []):
            if g.get("status", {}).get("abstractGameState") != "Final":
                continue
            pk = g.get("gamePk")
            teams = g.get("teams", {})
            home = teams.get("home", {}).get("team", {}).get("name", "")
            away = teams.get("away", {}).get("team", {}).get("name", "")
            if not (pk and home and away):
                continue
            try:
                with urllib.request.urlopen(_BOX_URL.format(pk=pk), timeout=timeout) as r:
                    box = json.loads(r.read().decode("utf-8", "ignore"))
                bt = box["teams"]
                row = {"date": d, "home": home, "away": away}
                for side in ("home", "away"):
                    bat = bt[side]["teamStats"]["batting"]
                    row[f"{side}_runs"] = int(bat["runs"])
                    row[f"{side}_hits"] = int(bat["hits"])
                    row[f"{side}_hr"] = int(bat["homeRuns"])
                    row[f"{side}_so"] = int(bat["strikeOuts"])
                out.append(row)
            except Exception as e:
                _log.warning("boxscore MLB game %s: %s", pk, e)
    return out
