"""
Partidos del día: fixtures de hoy + las 10 situaciones más probables de cada uno.

El registro completo en el historial lo hace el cron (scripts/log_todays_fixtures.py),
sin depender de que alguien abra esta página. Aquí se listan los partidos (columna
izquierda) y, al elegir uno, se muestran sus 10 situaciones (columna derecha).

Fuentes gratis y fiables: MLB (statsapi, sin clave) y fútbol (football-data.org,
con clave gratuita en el secret `football_data_token`).
"""
import html
import sys
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from app.auth import require_password  # noqa: E402
from app.ui import (inject_theme, page_header, brand_logo,  # noqa: E402
                    matchup_header, render_freshness, empty_state,
                    browser_tz, local_hm, skeleton_rows, sidebar_nav)
from app import charts  # noqa: E402
from core.fixtures import todays_fixtures  # noqa: E402
from core.fixtures.football import has_token as football_has_token  # noqa: E402
from core.fixtures.match import attach_entity_ids  # noqa: E402
from core.matchup import predict  # noqa: E402
from core.predictions import top_situations  # noqa: E402
from core.history.store import log_predictions  # noqa: E402

_FAV = str(ROOT / "app" / "assets" / "favicon.png")
st.set_page_config(page_title="Partidos del día", page_icon=_FAV, layout="wide")
require_password()

_SPORTS = {"Fútbol": "football", "Béisbol (MLB)": "baseball"}
st.sidebar.markdown(f"<div style='padding:6px 2px 10px;'>{brand_logo(scale=0.95)}</div>",
                    unsafe_allow_html=True)
sidebar_nav()
st.sidebar.markdown("<hr style='margin:12px 0'>"
                    "<div style='color:var(--muted);font-size:.7rem;text-transform:uppercase;"
                    "letter-spacing:.06em;margin-bottom:6px;'>Deportes</div>",
                    unsafe_allow_html=True)
label = st.sidebar.radio("Deporte", list(_SPORTS.keys()), label_visibility="collapsed")
sport = _SPORTS[label]
inject_theme(sport)
accent = charts.ACCENT[sport]


@st.cache_resource
def _engine():
    return get_sqlalchemy_engine()


@st.cache_data(ttl=1800)
def _fixtures(sport, d):
    return attach_entity_ids(_engine(), sport, todays_fixtures(sport, d))


@st.cache_data(ttl=1800)
def _situations(sport, home_id, away_id, day):
    mk = predict(sport, _engine(), home_id, away_id, game_date=day)
    return top_situations(mk, 10) if mk else []


hcol, dcol = st.columns([3, 1])
with hcol:
    page_header("Partidos del día",
                "Consulta los partidos programados y sus situaciones más probables.",
                "calendar")
with dcol:
    day = st.date_input("Fecha", value=date.today(), format="DD/MM/YYYY")

fixtures = _fixtures(sport, day)
render_freshness()


def _status_label(status):
    """(texto_es, color, en_vivo) según el estado del feed (statsapi / football-data)."""
    s = str(status or "").upper()
    if any(k in s for k in ("IN_PLAY", "PROGRESS", "LIVE", "PAUSED", "WARMUP")):
        return "EN VIVO", "#d98c8c", True
    if any(k in s for k in ("FINISH", "FINAL", "COMPLET")):
        return "Finalizado", "var(--muted)", False
    return "Programado", "var(--accent)", False


if not fixtures:
    if sport == "football" and not football_has_token():
        # Caso 1: falta la clave -> no podemos consultar nada.
        empty_state("API de fútbol no configurada",
                    "Agrega tu clave <b>football_data_token</b> (gratis en football-data.org) "
                    "en los Secrets para ver los partidos y predicciones.")
    elif sport == "football":
        # Caso 2: la clave SÍ está, pero ese día no hay partidos (p. ej. parón de verano).
        empty_state("Sin partidos de fútbol este día",
                    f"La API está configurada correctamente, pero no hay partidos "
                    f"programados el <b>{day.strftime('%d/%m/%Y')}</b> en las competiciones "
                    "del plan gratuito. Prueba con otra fecha.")
    else:
        empty_state("Sin partidos de MLB este día",
                    f"No hay partidos programados en MLB el "
                    f"<b>{day.strftime('%d/%m/%Y')}</b>. Prueba con otra fecha.")
    st.stop()


def _matchup(f):
    return (f"{f['away']} @ {f['home']}" if sport == "baseball"
            else f"{f['home']} vs {f['away']}")


st.markdown(f"<div style='color:var(--muted);font-size:.85rem;margin-bottom:10px;'>"
            f"{len(fixtures)} partidos</div>", unsafe_allow_html=True)

# Los botones de la lista se ven como filas de tarjeta (texto a la izquierda); el
# seleccionado (primary) lleva borde de acento. Así la lista es CLICABLE de verdad.
st.markdown("""<style>
section[data-testid="stMain"] .stButton>button{
  justify-content:flex-start !important; text-align:left !important;
  padding:11px 14px !important; font-weight:500 !important; border-radius:12px !important;
  background:var(--card) !important; border:1px solid var(--border) !important;
  color:#e6eaf0 !important; margin-bottom:8px !important;
}
section[data-testid="stMain"] .stButton>button:hover{
  border-color:rgba(var(--accent-rgb),0.45) !important; background:var(--card-2) !important;
}
section[data-testid="stMain"] .stButton>button[kind="primary"],
section[data-testid="stMain"] [data-testid="stBaseButton-primary"]{
  background:rgba(var(--accent-rgb),0.10) !important;
  border-color:rgba(var(--accent-rgb),0.55) !important; color:#fff !important;
}
</style>""", unsafe_allow_html=True)

if "pdd_idx" not in st.session_state or st.session_state["pdd_idx"] >= len(fixtures):
    st.session_state["pdd_idx"] = 0

_tz = browser_tz()   # zona del navegador (para mostrar hora local, no UTC)
left, right = st.columns([1, 1.15], gap="large")

with left:
    for i, f in enumerate(fixtures):
        hm, tzlabel = local_hm(f.get("time_utc"), _tz)
        _, _, est_live = _status_label(f.get("status"))
        extra = []
        if f.get("league"):
            extra.append(str(f["league"]))
        if est_live:
            extra.append("EN VIVO")
        if not (f.get("home_id") and f.get("away_id")):
            extra.append("sin datos")
        suffix = ("   ·   " + "  ·  ".join(extra)) if extra else ""
        label = f"{hm} {tzlabel}   ·   {_matchup(f)}{suffix}"
        if st.button(label, key=f"pdd_{i}", width="stretch",
                     type="primary" if i == st.session_state["pdd_idx"] else "secondary"):
            st.session_state["pdd_idx"] = i
            st.rerun()

idx = st.session_state["pdd_idx"]

with right:
    f = fixtures[idx]
    if not (f.get("home_id") and f.get("away_id")):
        empty_state("Sin datos del modelo",
                     "Uno de los equipos no está en la base de datos, así que no hay "
                     "predicción para este partido.", "info")
    else:
        _hm, _tzl = local_hm(f.get("time_utc"), _tz)
        sub = (f"{f.get('league','')} · {_hm} {_tzl}" if f.get("league")
               else f"{_hm} {_tzl}")
        matchup_header(f["home"], f["away"], accent,
                       charts.ACCENT_RGB.get(sport, "92,154,133"), subtitle=sub,
                       home_logo=f.get("home_logo", ""), away_logo=f.get("away_logo", ""))
        st.markdown("<div style='display:flex;align-items:center;justify-content:space-between;"
                    "margin:2px 4px 10px;'><span style='color:#eef1f6;font-weight:600;"
                    "font-size:.95rem;'>10 situaciones más probables</span>"
                    "<span style='color:var(--muted);font-size:.72rem;text-transform:uppercase;"
                    "letter-spacing:.05em;'>Probabilidades del modelo</span></div>",
                    unsafe_allow_html=True)
        # Skeleton mientras se calcula (carga percibida), luego se reemplaza.
        _ph = st.empty()
        _ph.markdown(skeleton_rows(10), unsafe_allow_html=True)
        sits = _situations(sport, f["home_id"], f["away_id"], day)
        if not sits:
            _ph.empty()
            empty_state("Sin mercados", "No se pudieron calcular los mercados de este partido.",
                        "info")
        else:
            rows = ""
            for i, m in enumerate(sits, 1):
                pct = m["prob"] * 100
                rows += (
                    "<div style='display:flex;align-items:center;gap:12px;padding:9px 4px;"
                    "border-bottom:1px solid rgba(255,255,255,.05)'>"
                    f"<span style='width:22px;height:22px;flex:none;display:flex;align-items:center;"
                    f"justify-content:center;border-radius:6px;background:rgba(var(--accent-rgb),0.12);"
                    f"color:{accent};font-family:\"IBM Plex Mono\",monospace;font-size:.72rem;"
                    f"font-weight:600;'>{i}</span>"
                    f"<span style='flex:1.2;color:#e6eaf0;font-size:.9rem;line-height:1.3;'>{html.escape(str(m['mercado']))}</span>"
                    f"<span role='progressbar' aria-valuenow='{pct:.0f}' aria-valuemin='0' aria-valuemax='100' "
                    "style='position:relative;flex:1;height:6px;background:rgba(255,255,255,.06);border-radius:99px'>"
                    f"<span style='display:block;width:{pct:.0f}%;height:100%;background:{accent};border-radius:99px'></span>"
                    "<span title='50%' style='position:absolute;left:50%;top:-2px;width:1px;height:10px;"
                    "background:rgba(255,255,255,.22)'></span></span>"
                    f"<span style='width:52px;text-align:right;font-family:\"IBM Plex Mono\",monospace;"
                    f"color:#fff;font-weight:600;'>{pct:.1f}%</span></div>"
                )
            _ph.markdown(f"<div style='background:var(--card);border:1px solid var(--border);"
                         f"border-radius:14px;padding:8px 16px;'>{rows}</div>",
                         unsafe_allow_html=True)
            log_predictions(sport, day, f["home"], f["away"], sits, f["home_id"], f["away_id"])

st.caption("Las probabilidades se calculan con el modelo estadístico propio. Si un equipo "
           "aparece como «sin datos», no hay información suficiente en la base para estimarlo.")
