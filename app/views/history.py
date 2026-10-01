from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

from app import charts, services as sv, ui
from app.ui import SPORTS

PERIODS = {"7": "7 días", "30": "30 días", "90": "90 días", "all": "Todo"}


def _calibration_label(gap_pp: float) -> tuple:
    a = abs(gap_pp)
    if a <= 3:
        return "bien calibrado", "up"
    if a <= 7:
        return "vigilar", "warn"
    return "descalibrado", "down"


def _reliability(points: pd.DataFrame):
    p = points["probability"].astype(float).to_numpy()
    y = points["hit"].astype(float).to_numpy()
    bins = np.clip((p * 10).astype(int), 0, 9)
    pred, obs, cnt = [], [], []
    for b in range(10):
        mask = bins == b
        if mask.sum() >= 5:
            pred.append(float(p[mask].mean()))
            obs.append(float(y[mask].mean()))
            cnt.append(int(mask.sum()))
    return pred, obs, cnt


ui.page_header("Rendimiento",
               "Lo que el modelo prometió frente a lo que pasó. Un modelo honesto no es el que "
               "más acierta: es aquel cuyo 70 % se cumple 7 de cada 10 veces.",
               eyebrow="Historial verificado")
ui.set_accent(None)

c1, c2 = st.columns([1.6, 1], vertical_alignment="bottom")
sport_opts = ["all"] + list(SPORTS)
sport = c1.segmented_control("Deporte", sport_opts, default="all", key="hi_sport", required=True,
                             format_func=lambda s: "Todos" if s == "all" else ui.sport_option(s),
                             width="stretch")
period = c2.segmented_control("Periodo", list(PERIODS), format_func=PERIODS.get, default="30",
                              key="hi_period", required=True, width="stretch")
since = None if period == "all" else date.today() - timedelta(days=int(period))
code = None if sport == "all" else sport
if code:
    ui.set_accent(code)

data = sv.history(code, since)
summary = data["summary"]
if summary is None or summary.empty:
    ui.empty_state("Aún no hay predicciones resueltas en este periodo",
                   "Se registran automáticamente los partidos del día (fútbol y MLB) y se "
                   "resuelven al terminar. Prueba con un periodo más largo.", "clock")
    st.stop()

n = int(summary["n"].sum())
hits = int(summary["aciertos"].sum())
rate = hits / n if n else 0.0
prom = float((summary["prob_media"] * summary["n"]).sum() / n) if n else 0.0
brier = float((summary["brier"].astype(float) * summary["n"]).sum() / n) if n else 0.0
gap = (rate - prom) * 100
gap_txt, gap_dir = _calibration_label(gap)
trend = data["trend"]
spark = (trend["tasa"].astype(float).tolist()[-12:] if trend is not None and len(trend) >= 2 else None)

ui.kpis([
    {"label": "Predicciones resueltas", "value": f"{n:,}".replace(",", "."), "sub": "en el periodo"},
    {"label": "Tasa real de acierto", "value": ui.fmt_pct(rate), "sub": f"{hits:,} de {n:,}".replace(",", "."),
     "spark": spark},
    {"label": "Probabilidad prometida", "value": ui.fmt_pct(prom), "sub": "media de lo predicho"},
    {"label": "Calibración", "value": f"{gap:+.1f} pp",
     "sub": "real − prometido (≈0 es ideal)", "delta": gap_txt, "delta_dir": gap_dir},
    {"label": "Brier", "value": f"{brier:.3f}", "sub": "error cuadrático (más bajo = mejor)"},
])

left, right = st.columns(2, gap="medium")
with left:
    ui.section("Fiabilidad", "tramos de 10 pp · tamaño = nº de casos")
    points = data["points"]
    if points is not None and len(points) >= 20:
        charts.reliability(*_reliability(points), key="hi_rel")
    else:
        st.caption("Aún no hay suficientes casos para el diagrama.")
with right:
    ui.section("Tendencia semanal", "real vs prometido")
    if trend is not None and len(trend) >= 2:
        charts.weekly_trend(pd.to_datetime(trend["semana"]), trend["tasa"].astype(float),
                            trend["prob_media"].astype(float), key="hi_trend")
    else:
        st.caption("Hace falta más de una semana de datos para la tendencia.")

ui.section("Por mercado", "ordenado por nº de casos")
rows = []
for r in summary.sort_values("n", ascending=False).itertuples(index=False):
    pm, tr = float(r.prob_media), float(r.tasa_acierto)
    rows.append([ui.esc(r.grupo), ui.esc(SPORTS.get(r.sport, {}).get("label", r.sport)),
                 f"{int(r.n):,}".replace(",", "."), ui.fmt_pct(pm), ui.fmt_pct(tr),
                 ui.gap_cell((tr - pm) * 100), f"{float(r.brier):.3f}"])
ui.table([("Mercado", ""), ("Deporte", ""), ("Casos", "num"), ("Prometido", "num"),
          ("Real", "num"), ("Calibración", "num"), ("Brier", "num")], rows,
         caption="Fiabilidad por grupo de mercado")
st.caption("Calibración = tasa real − probabilidad media prometida. Derecha: el modelo se quedó "
           "corto; izquierda: fue optimista. Verde ≤ 3 pp · ámbar ≤ 7 pp · rojo > 7 pp.")

rec = data["recent"]
if rec is not None and not rec.empty:
    ui.section("Últimas resueltas")
    rows = [[pd.Timestamp(r.match_date).strftime("%d/%m"), ui.esc(f"{r.home} vs {r.away}"),
             ui.esc(r.mercado), ui.fmt_pct(float(r.probability)), ui.result_pill(r.hit)]
            for r in rec.head(20).itertuples(index=False)]
    ui.table([("Fecha", ""), ("Partido", ""), ("Situación", ""), ("Prob.", "num"), ("Resultado", "")],
             rows, lead=1, caption="Últimas predicciones resueltas")
    st.download_button("Descargar CSV", ui.csv_bytes(rec),
                       file_name="historial_resueltas.csv", mime="text/csv",
                       icon=":material/download:")

st.caption("El rendimiento pasado no garantiza el futuro. Los partidos se caducan tras unos meses.")
