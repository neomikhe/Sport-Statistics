import json
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from app import services as sv, ui
from app.ui import SPORTS

EVAL_FILE = Path(__file__).resolve().parents[2] / "core" / "forecast" / "eval_v2.json"
DESCRIPTIONS = {
    "football": "Poisson + ratings Dixon-Coles por liga. 1X2, goles, hándicap, córners y tarjetas.",
    "basketball": "Ratings por posesión + Elo. Ganador, hándicap, totales y margen de victoria.",
    "baseball": "Carreras con estadio neutral, abridores y binomial negativa. ML, run line y totales.",
    "tennis": "Elo general + superficie con K dinámico. Ganador, sets, aces y dobles faltas.",
}


def _status_chips() -> None:
    chips = []
    if not sv.db_ok():
        chips.append(ui.pill("Base de datos sin conexión", "bad"))
    fr = ui.freshness(sv.meta("last_refresh"))
    if fr:
        chips.append(ui.pill(fr[0], fr[1]))
    try:
        health = json.loads(sv.meta("model_health") or "null")
    except ValueError:
        health = None
    if health and health.get("status") == "degraded":
        chips.append(ui.pill("Modelo de fútbol degradado: conviene re-entrenar", "bad"))
    elif health:
        chips.append(ui.pill("Modelo de fútbol estable", "good"))
    if chips:
        ui.chips(chips)
    from app.refresh import render_refresh_button
    render_refresh_button()


def _sports() -> None:
    ui.section("Deportes", "datos disponibles en la base")
    cov = sv.coverage()
    cols = st.columns(len(SPORTS), gap="small")
    for col, (key, meta) in zip(cols, SPORTS.items()):
        c = cov.get(key, {})
        last = c.get("last")
        facts = [("Partidos", f"{c.get('n', 0):,}".replace(",", "."))]
        if last is not None:
            facts.append(("Hasta", last.strftime("%d/%m/%Y")))
        with col:
            ui.sport_tile(key, meta["label"], DESCRIPTIONS[key], facts)
            st.page_link("views/analyzer.py", label=f"Analizar {meta['label'].lower()}",
                         icon=meta["icon"], query_params={"sport": key}, width="stretch")


def _models() -> None:
    if not EVAL_FILE.exists():
        return
    try:
        ev = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    ui.section("Modelos v2", f"evaluados fuera de muestra · {ev.get('generated', '')}")
    rows = []
    for r in ev.get("rows", []):
        better = r["v2"] < r["v1"]
        rows.append([ui.esc(SPORTS.get(r["sport"], {}).get("label", r["sport"])), ui.esc(r["metric"]),
                     ui.esc(r["sample"]), f"{r['v1']:.4f}", f"{r['v2']:.4f}",
                     ui.pill(f"{(r['v2'] - r['v1']):+.4f}", "good" if better else "bad")])
    ui.table([("Deporte", ""), ("Métrica (menor = mejor)", ""), ("Muestra", ""), ("v1", "num"),
              ("v2", "num"), ("Cambio", "num")], rows, lead=1,
             caption="Comparativa de modelos v1 y v2")
    st.caption("Log-loss y NLL: cuánto se sorprende el modelo con lo que pasó de verdad. "
               "Detalles y método en scripts/eval_forecast_v2.py.")


def _performance() -> None:
    data = sv.history(None, date.today() - timedelta(days=30))
    s = data["summary"]
    if s is None or s.empty:
        return
    n = int(s["n"].sum())
    rate = float(s["aciertos"].sum()) / n if n else 0.0
    prom = float((s["prob_media"] * s["n"]).sum() / n) if n else 0.0
    ui.section("Rendimiento · 30 días", "predicciones del día ya resueltas")
    ui.kpis([
        {"label": "Resueltas", "value": f"{n:,}".replace(",", ".")},
        {"label": "Real", "value": ui.fmt_pct(rate)},
        {"label": "Prometido", "value": ui.fmt_pct(prom)},
        {"label": "Calibración", "value": f"{(rate - prom) * 100:+.1f} pp", "sub": "≈0 es ideal"},
    ])
    st.page_link("views/history.py", label="Ver el historial completo", icon=":material/verified:")


def _last_summary() -> None:
    dates = sv.summary_dates(1)
    if not dates:
        return
    s, _ = sv.day_summary(dates[0])
    if not s:
        return
    t = s["totals"]
    ui.section("Último cierre del día", f"{dates[0]:%d/%m/%Y} · 23:00 (Pacífico)")
    ui.kpis([
        {"label": "Partidos", "value": str(t["matches"])},
        {"label": "Pick principal", "value": f"{t['main_hits']}/{t['main_resolved']}"},
        {"label": "Situaciones acertadas", "value": f"{t['hits']}/{t['resolved']}"},
    ])
    st.page_link("views/summary.py", label="Ver el resumen del día", icon=":material/fact_check:")


def _today() -> None:
    ui.section("Hoy en la agenda", date.today().strftime("%d/%m/%Y"))
    tz = ui.browser_tz()
    shown = 0
    for sport in ("football", "baseball"):
        fx = [f for f in sv.fixtures(sport, date.today()) if f.get("home_id") and f.get("away_id")]
        fx = sorted(fx, key=lambda f: str(f.get("time_utc", "")))[:3]
        if not fx:
            continue
        cols = st.columns(3, gap="small")
        for col, f in zip(cols, fx):
            fc = sv.fixture_forecast(sport, f, date.today())
            hm, tzl = ui.local_hm(f.get("time_utc"), tz)
            with col:
                ui.fixture_card(f, fc.win if fc else None,
                                f"{SPORTS[sport]['short']} · {hm} {tzl}".strip(),
                                ui.status_of(f.get("status")))
        shown += len(fx)
    if not shown:
        st.caption("Sin partidos con datos del modelo hoy (o la agenda no está configurada).")
    st.page_link("views/fixtures.py", label="Ver todos los partidos", icon=":material/event:")


ui.set_accent(None)
ui.page_header("Probabilidades con criterio",
               "Pronósticos calibrados para fútbol, NBA, MLB y tenis. La meta no es acertar "
               "siempre: es que cuando el modelo dice 70 %, pase 7 de cada 10 veces.",
               eyebrow="SportStatistics")
_status_chips()

a, b, c = st.columns(3, gap="small")
a.page_link("views/fixtures.py", label="Partidos de hoy", icon=":material/event:", width="stretch")
b.page_link("views/analyzer.py", label="Analizar un enfrentamiento", icon=":material/query_stats:",
            width="stretch")
c.page_link("views/history.py", label="¿Se cumplen las probabilidades?", icon=":material/verified:",
            width="stretch")

_sports()
_last_summary()
_models()
_performance()
_today()
