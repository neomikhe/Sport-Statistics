from datetime import timedelta

import streamlit as st

from app import services as sv, ui
from core.history.summary import today_local

WEEKDAYS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


def _pick_day():
    today = today_local()
    published = sv.summary_dates(14)
    options = sorted({today, today - timedelta(days=1), *published}, reverse=True)[:14]
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    labels = {today: "Hoy", today - timedelta(days=1): "Ayer"}
    day = c1.selectbox("Día", options, key="sm_day",
                       format_func=lambda d: labels.get(d, f"{WEEKDAYS[d.weekday()]} {d:%d/%m}"))
    other = c2.date_input("Otra fecha", value=None, format="DD/MM/YYYY", key="sm_other",
                          max_value=today)
    return other or day


def _kpis(t: dict) -> None:
    rate = t["hits"] / t["resolved"] if t["resolved"] else None
    ui.kpis([
        {"label": "Partidos", "value": str(t["matches"]),
         "sub": f"{t['resolved_matches']} ya resueltos"},
        {"label": "Pick principal", "value": f"{t['main_hits']}/{t['main_resolved']}",
         "sub": "la situación más probable de cada partido"},
        {"label": "Situaciones acertadas", "value": ui.fmt_pct(rate) if rate is not None else "—",
         "sub": f"{t['hits']} de {t['resolved']}"},
        {"label": "Prometido", "value": ui.fmt_pct(t["promised"]) if t["promised"] else "—",
         "sub": "probabilidad media de lo resuelto"},
    ])


ui.set_accent(None)
ui.page_header("Resumen del día",
               "Cada noche a las 23:00 (hora del Pacífico) se cierran los partidos del día y se "
               "comprueba qué predicciones acertaron.", eyebrow="Cierre diario")

day = _pick_day()
summary, published = sv.day_summary(day)
if not summary:
    ui.empty_state("Sin partidos registrados ese día",
                   "El historial registra los partidos de fútbol y MLB con datos del modelo. "
                   "Prueba con otra fecha.", "calendar")
    st.stop()

ui.chips([ui.pill(f"Publicado · {summary.get('generated_at', '')}", "good") if published
          else ui.pill("Provisional: el cierre se publica a las 23:00", "warn")])
_kpis(summary["totals"])

matches = summary["matches"]
won = [m for m in matches if m["main"]["hit"] is True]
lost = [m for m in matches if m["main"]["hit"] is False]
pending = [m for m in matches if m["main"]["hit"] is None]
won.sort(key=lambda m: (-m["hits"], m["home"]))
lost.sort(key=lambda m: (-m["hits"], m["home"]))

if won:
    ui.section("Partidos que acertaron", f"{len(won)} · se cumplió la situación más probable")
    ui.summary_cards(won)
if lost:
    ui.section("Partidos que fallaron", f"{len(lost)} · no se cumplió la situación más probable")
    ui.summary_cards(lost)
if pending:
    ui.section("Pendientes", f"{len(pending)} · aún sin resultado")
    ui.summary_cards(pending)
st.caption("✓ acierto · ✗ fallo · • pendiente. El pick principal es la situación más probable "
           "del partido (primera de la lista).")
