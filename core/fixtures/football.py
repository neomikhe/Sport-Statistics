"""
Partidos del día de fútbol vía football-data.org — requiere clave GRATUITA.

La clave se lee de st.secrets['football_data_token'] o FOOTBALL_DATA_TOKEN, y se envía
en la cabecera `X-Auth-Token` (como exige el proveedor).
Sin clave -> devuelve [] (degradación limpia, la app no rompe).

THROTTLING AUTOMÁTICO (petición expresa del proveedor): tras cada respuesta se leen las
cabeceras de cuota que devuelve el servidor:
  - X-Requests-Available-Minute : peticiones que quedan en el minuto en curso
  - X-RequestCounter-Reset      : segundos hasta que se reinicia el contador
Si la cuota llega a 0, esperamos al reset ANTES de la siguiente llamada; y si aun así
llega un 429, esperamos lo que indique el servidor y reintentamos una vez.
Free tier: 12 competiciones top, 10 req/min.
"""
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import date as _date

_log = logging.getLogger(__name__)
_URL = "https://api.football-data.org/v4/matches?dateFrom={d}&dateTo={d}"

_MAX_WAIT_S = 65.0          # tope de espera (el contador del proveedor es por minuto)
_rate = {"remaining": None, "reset_at": 0.0}   # cuota informada por el servidor


def _token():
    try:
        import streamlit as st
        if "football_data_token" in st.secrets:
            return st.secrets["football_data_token"]
    except Exception:
        pass
    return os.getenv("FOOTBALL_DATA_TOKEN")


def has_token() -> bool:
    """¿Hay clave configurada? Permite distinguir «sin API» de «sin partidos ese día»."""
    return bool(_token())


def _remember_quota(headers) -> None:
    """Guarda la cuota que el servidor informa en sus cabeceras de respuesta."""
    try:
        rem = headers.get("X-Requests-Available-Minute")
        if rem is not None:
            _rate["remaining"] = int(rem)
        reset = headers.get("X-RequestCounter-Reset")
        if reset is not None:
            _rate["reset_at"] = time.time() + int(reset)
    except (TypeError, ValueError):
        pass


def _reset_wait(headers, default: float = 60.0) -> float:
    """Segundos a esperar según el servidor (X-RequestCounter-Reset o Retry-After)."""
    for h in ("X-RequestCounter-Reset", "Retry-After"):
        try:
            v = headers.get(h) if headers else None
            if v is not None:
                return min(float(v) + 1.0, _MAX_WAIT_S)
        except (TypeError, ValueError):
            continue
    return default


def _throttle() -> None:
    """Si el servidor dijo que no quedan peticiones este minuto, espera al reset."""
    if _rate["remaining"] is not None and _rate["remaining"] <= 0:
        wait = min(max(0.0, _rate["reset_at"] - time.time()) + 1.0, _MAX_WAIT_S)
        if wait > 0:
            _log.info("football-data.org: cuota agotada; espero %.0fs al reset", wait)
            time.sleep(wait)
        _rate["remaining"] = None


def _get(req, timeout: int):
    """GET respetando la cuota informada. Devuelve la lista de `matches`."""
    _throttle()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        _remember_quota(r.headers)
        return json.loads(r.read().decode("utf-8", "ignore")).get("matches", [])


def _fetch_matches(day, timeout: int):
    """Lista cruda de partidos de la fecha desde football-data.org. [] sin clave/red."""
    token = _token()
    if not token:
        return []
    d = (day or _date.today()).strftime("%Y-%m-%d")
    req = urllib.request.Request(_URL.format(d=d), headers={"X-Auth-Token": str(token)})
    try:
        return _get(req, timeout)
    except urllib.error.HTTPError as e:
        if e.code == 429:   # rate limit: esperar lo que diga el servidor y reintentar 1 vez
            wait = _reset_wait(getattr(e, "headers", None))
            _log.warning("football-data.org: 429 (rate limit); espero %.0fs y reintento", wait)
            time.sleep(wait)
            _rate["remaining"] = None
            try:
                return _get(req, timeout)
            except Exception as e2:
                _log.warning("football-data.org (reintento): %s", e2)
                return []
        _log.warning("football-data.org: HTTP %s", e.code)
        return []
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
