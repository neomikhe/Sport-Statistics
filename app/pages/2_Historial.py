"""
Historial de rendimiento del modelo.

Cada partido analizado guarda sus 10 situaciones más probables; cuando el partido
termina, se verifica cuántas acertaron. Esta página muestra la fiabilidad real por
mercado (predicho vs. observado) para ir puliendo los cálculos. Los datos caducan
automáticamente tras unos meses.
"""
import html
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.auth import require_password       # noqa: E402
from app.ui import (inject_theme, page_header, kpi_card, section_header,  # noqa: E402
                    pill, calibration_bar, render_freshness, empty_state, icon,
                    brand_logo, sidebar_nav)
from core.history.store import (history_summary, recent_resolved,  # noqa: E402
                                history_trend)

_FAV = str(ROOT / "app" / "assets" / "favicon.png")
st.set_page_config(page_title="Historial", page_icon=_FAV, layout="wide")
require_password()
inject_theme("football")
st.sidebar.markdown(f"<div style='padding:6px 2px 10px;'>{brand_logo(scale=0.95)}</div>",
                    unsafe_allow_html=True)
sidebar_nav()

_SPORT_ES = {"football": "Fútbol", "baseball": "Béisbol",
             "basketball": "Baloncesto", "tennis": "Tenis"}


@st.cache_data(ttl=600)
def _summary():
    return history_summary()


@st.cache_data(ttl=600)
def _recent():
    return recent_resolved(200)


hcol, fcol = st.columns([3, 1])
with hcol:
    page_header("Historial de rendimiento",
                "Rendimiento histórico del modelo en predicciones ya resueltas", "clock")

summary = _summary()
if summary.empty:
    empty_state("Aún no hay predicciones resueltas",
                "Se registrarán conforme se jueguen y cierren los partidos analizados. "
                "Vuelve tras la próxima jornada.", "clock")
    st.stop()

rec = _recent()
with fcol:
    deportes = ["Todos los deportes"] + [_SPORT_ES.get(s, s)
                                         for s in sorted(summary["sport"].unique())]
    sport_sel = st.selectbox("Deporte", deportes, label_visibility="collapsed")

if sport_sel != "Todos los deportes":
    code = next((k for k, v in _SPORT_ES.items() if v == sport_sel), None)
    summary = summary[summary["sport"] == code]
    if not rec.empty:
        rec = rec[rec["sport"] == code]

render_freshness()

# ---------------------------------------------------------------- KPIs
total = int(summary["n"].sum())
aciertos = int(summary["aciertos"].sum())
tasa = aciertos / total if total else 0.0

spark = None
if not rec.empty:
    spark = rec.sort_values("match_date")["hit"].astype(int).cumsum().tolist()

k1, k2, k3 = st.columns(3)
with k1:
    kpi_card("Predicciones resueltas", f"{total:,}", "list", "En el periodo", spark)
with k2:
    kpi_card("Aciertos", f"{aciertos:,}", "check", "En el periodo", spark)
with k3:
    kpi_card("Tasa de acierto", f"{tasa * 100:.1f}%", "target",
             f"{aciertos} / {total}", spark)

# ---------------------------------------------- Fiabilidad por mercado
section_header("Fiabilidad por mercado", "activity")

_COLS = "1.6fr .5fr .7fr .8fr .7fr .7fr 1.7fr"


def _cell(content, mono=False, color="var(--text)", align="left", role="cell"):
    fam = "'IBM Plex Mono',monospace" if mono else "inherit"
    return (f"<div role='{role}' style='font-family:{fam};color:{color};text-align:{align};"
            f"font-size:.86rem;overflow:hidden;'>{content}</div>")


_HEADERS = [
    ("Grupo de mercado", "left", ""), ("Casos", "right", ""), ("Aciertos", "right", ""),
    ("Prob. media", "right", ""), ("Tasa real", "right", ""),
    ("Brier", "right", "Error cuadrático medio de la probabilidad. Más bajo = mejor "
                       "(mide filo, no solo sesgo)."),
    ("Calibración", "left", "Verde (derecha): el modelo acertó más de lo previsto. "
                            "Rojo (izquierda): fue demasiado optimista."),
]


def _head_cell(text, align, tip):
    ico = ("&nbsp;" + icon("info", 11, "var(--muted)")) if tip else ""
    attr = f" title=\"{html.escape(tip)}\"" if tip else ""
    cur = "help" if tip else "default"
    return _cell(f"<span{attr} style='color:var(--muted);font-size:.7rem;text-transform:uppercase;"
                 f"letter-spacing:.05em;cursor:{cur};'>{text}{ico}</span>", align=align,
                 role="columnheader")


head = "".join(_head_cell(h, a, tip) for h, a, tip in _HEADERS)
rows_html = (f"<div role='row' style='display:grid;grid-template-columns:{_COLS};gap:14px;"
             f"padding:0 16px 10px;'>{head}</div>")

for r in summary.sort_values("n", ascending=False).itertuples(index=False):
    prob_m = float(r.prob_media) * 100
    tasa_r = float(r.tasa_acierto) * 100
    calib = tasa_r - prob_m
    brier = float(r.brier) if r.brier is not None else 0.0
    dot = ("<span style='display:inline-block;width:7px;height:7px;border-radius:50%;"
           "background:var(--accent);margin-right:9px;vertical-align:middle;'></span>")
    cells = (
        _cell(f"{dot}{html.escape(str(r.grupo))}")
        + _cell(f"{int(r.n)}", mono=True, color="var(--muted)", align="right")
        + _cell(f"{int(r.aciertos)}", mono=True, align="right")
        + _cell(f"{prob_m:.1f}%", mono=True, color="var(--muted)", align="right")
        + _cell(f"{tasa_r:.1f}%", mono=True, color="#fff", align="right")
        + _cell(f"{brier:.3f}", mono=True, color="var(--muted)", align="right")
        + _cell(calibration_bar(calib))
    )
    rows_html += (f"<div role='row' style='display:grid;grid-template-columns:{_COLS};gap:14px;"
                  f"align-items:center;padding:11px 16px;border-top:1px solid "
                  f"rgba(255,255,255,0.04);'>{cells}</div>")

st.markdown(
    "<div style='overflow-x:auto;'><div role='table' aria-label='Fiabilidad por mercado' "
    "style='min-width:620px;background:var(--card);border:1px solid var(--border);"
    f"border-radius:14px;padding:14px 0 4px;'>{rows_html}</div></div>",
    unsafe_allow_html=True,
)
st.caption("**Calibración** = tasa real − probabilidad media (cerca de 0 = bien calibrado; "
           "rojo = el modelo es optimista). **Brier** = error cuadrático medio de la "
           "probabilidad (más bajo = mejor; mide filo, no solo sesgo).")

# ------------------------------------------------- Tendencia temporal
_trend = history_trend(code if sport_sel != "Todos los deportes" else None)
if len(_trend) >= 3:
    section_header("Tendencia de acierto (por semana)", "trending")
    tdf = _trend.copy()
    tdf["Tasa de acierto"] = (tdf["tasa"] * 100).round(1)
    tdf["Brier"] = (tdf["brier"]).round(3)
    st.line_chart(tdf.set_index("semana")[["Tasa de acierto"]], height=220,
                  color="#5c9a85")
    st.caption("Si la tasa de acierto cae de forma sostenida, es señal de deriva del "
               "modelo (o de datos) en ese periodo.")

# ------------------------------------------------- Últimas resueltas
section_header("Últimas resueltas", "list")
if not rec.empty:
    _RC = "1fr .9fr 2fr 2fr .7fr 1fr"
    rhead = "".join(_cell(f"<span style='color:var(--muted);font-size:.7rem;"
                          f"text-transform:uppercase;letter-spacing:.05em;'>{h}</span>", align=a,
                          role="columnheader")
                    for h, a in [("Fecha", "left"), ("Deporte", "left"),
                                 ("Enfrentamiento", "left"), ("Mercado", "left"),
                                 ("Prob.", "right"), ("Resultado", "left")])
    recent_html = (f"<div role='row' style='display:grid;grid-template-columns:{_RC};gap:12px;"
                   f"padding:0 16px 10px;'>{rhead}</div>")
    for r in rec.head(15).itertuples(index=False):
        badge = (pill("Acierto", "pos", "check") if r.hit
                 else pill("Fallo", "neg", "x"))
        matchup = f"{html.escape(str(r.home))} vs {html.escape(str(r.away))}"
        cells = (
            _cell(str(r.match_date), mono=True, color="var(--muted)")
            + _cell(_SPORT_ES.get(r.sport, r.sport), color="var(--muted)")
            + _cell(matchup)
            + _cell(f"<span style='color:var(--muted)'>{html.escape(str(r.mercado))}</span>")
            + _cell(f"{float(r.probability) * 100:.1f}%", mono=True, align="right")
            + _cell(badge)
        )
        recent_html += (f"<div role='row' style='display:grid;grid-template-columns:{_RC};gap:12px;"
                        f"align-items:center;padding:10px 16px;border-top:1px solid "
                        f"rgba(255,255,255,0.04);'>{cells}</div>")
    st.markdown(
        "<div style='overflow-x:auto;'><div role='table' aria-label='Últimas resueltas' "
        "style='min-width:640px;background:var(--card);border:1px solid var(--border);"
        f"border-radius:14px;padding:14px 0 4px;'>{recent_html}</div></div>",
        unsafe_allow_html=True,
    )
    st.download_button(
        "Descargar historial (CSV)", rec.to_csv(index=False).encode("utf-8"),
        file_name="historial_resueltas.csv", mime="text/csv",
        icon=":material/download:",
    )
else:
    st.caption("Sin resueltas recientes para este filtro.")

st.caption("Las estadísticas se basan en predicciones ya resueltas. El rendimiento pasado "
           "no garantiza resultados futuros.")
