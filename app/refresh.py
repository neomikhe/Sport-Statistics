"""
Botón "Actualizar base de datos" para el dashboard.

NO ejecuta el pipeline en la web (sería lento y agotaría la RAM del tier free):
dispara el workflow de GitHub Actions (refresh.yml) vía API y sondea el progreso
que `scripts/refresh_cloud.py` va escribiendo en app_meta['refresh_status'].

Requiere en st.secrets (ver .streamlit/secrets.toml.example):
    github_token  -> PAT con permiso Actions: write sobre el repo
    github_repo   -> "tu-usuario/SportStatistics"

Si no están configurados (p. ej. en local), el botón sencillamente no aparece.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

WORKFLOW_FILE = "refresh.yml"
REF = "main"
WAIT_TIMEOUT_S = 480   # 8 min máximo de espera bloqueante
POLL_EVERY_S = 4


def _secret(key: str):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key.upper())


def _config():
    return _secret("github_token"), _secret("github_repo")


def _trigger(token: str, repo: str):
    """Dispara workflow_dispatch. Devuelve (ok, mensaje)."""
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    req = urllib.request.Request(
        url,
        data=json.dumps({"ref": REF}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sportstatistics-app",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status in (201, 204), f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode(errors='ignore')[:160]}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _read_status(engine):
    try:
        df = pd.read_sql("SELECT value FROM app_meta WHERE key = 'refresh_status'", engine)
        return json.loads(df["value"].iloc[0]) if not df.empty else None
    except Exception:
        return None


def _parse_ts(value):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _wait_for_completion(engine, started):
    """Sondea app_meta y pinta la barra hasta que el job termina o se agota el tiempo."""
    deadline = time.time() + WAIT_TIMEOUT_S
    with st.status("Actualizando base de datos…", expanded=True) as status:
        bar = st.progress(0.0)
        while time.time() < deadline:
            s = _read_status(engine)
            ts = _parse_ts(s.get("ts")) if s else None
            is_new = ts is not None and ts > started

            if is_new and s["state"] == "running":
                total = max(int(s.get("total", 1)), 1)
                step = int(s.get("step", 0))
                bar.progress(min(step / total, 0.99))
                status.update(label=f"Paso {step}/{total} · {s.get('label', '')}")
            elif is_new and s["state"] == "done":
                bar.progress(1.0)
                status.update(label=":material/check_circle: Base de datos actualizada", state="complete")
                st.cache_data.clear()
                time.sleep(1.0)
                st.rerun()
                return
            elif is_new and s["state"] == "error":
                status.update(label=f"Error en el refresco: {s.get('label', '')}", state="error")
                return
            else:
                status.update(label="En cola, esperando a que arranque el job…")
            time.sleep(POLL_EVERY_S)

        status.update(
            label="El refresco sigue en segundo plano. Recarga en un par de minutos.",
            state="error",
        )


def render_refresh_button() -> None:
    """Pinta el botón en la barra lateral (solo si hay token+repo configurados)."""
    token, repo = _config()
    if not (token and repo):
        return

    st.sidebar.divider()
    if st.sidebar.button(":material/sync: Actualizar base de datos", width="stretch"):
        ok, msg = _trigger(token, repo)
        if not ok:
            st.sidebar.error(f"No se pudo lanzar el refresco: {msg}")
            return
        st.session_state["_refresh_started"] = datetime.now(timezone.utc)
        from core.database.connection import get_sqlalchemy_engine
        _wait_for_completion(get_sqlalchemy_engine(), st.session_state["_refresh_started"])
