import pandas as pd
import streamlit as st

from app import charts, services as sv, ui

BANK0 = 1000.0
SELECTIONS = {"all": "Todas", "HOME": "Local", "DRAW": "Empate", "AWAY": "Visitante"}


def _won(sel: str, result: str) -> bool:
    h, a = (int(x) for x in str(result).split("-"))
    return (sel == "HOME" and h > a) or (sel == "DRAW" and h == a) or (sel == "AWAY" and h < a)


def _simulate(decided: pd.DataFrame) -> dict:
    bank, peak, max_dd, staked, wins = BANK0, BANK0, 0.0, 0.0, 0
    dates, series, profit_by = [], [], []
    for r in decided.sort_values("date").itertuples(index=False):
        won = _won(r.selection, r.real_result)
        pnl = r.stake * (r.odds - 1) if won else -r.stake
        bank += pnl
        staked += r.stake
        wins += int(won)
        peak = max(peak, bank)
        max_dd = max(max_dd, (peak - bank) / peak if peak > 0 else 0.0)
        dates.append(r.date)
        series.append(bank)
        profit_by.append((r.league, r.stake, pnl))
    n = len(series)
    return {"n": n, "wins": wins, "hit": wins / n if n else 0.0, "bank": bank,
            "roi": (bank - BANK0) / BANK0, "yield": (bank - BANK0) / staked if staked else 0.0,
            "max_dd": max_dd, "dates": dates, "series": series,
            "by_league": pd.DataFrame(profit_by, columns=["league", "stake", "pnl"])}


ui.page_header("Selecciones de valor",
               "Partidos en los que el modelo ve más probabilidad que el mercado, con su "
               "resultado y un banco simulado. Para medir el modelo, no para apostar.",
               eyebrow="Fútbol · modelo vs mercado")
ui.set_accent("football")

picks_all, source = sv.picks()
if picks_all.empty:
    ui.empty_state("Todavía no hay selecciones",
                   "El refresco diario las genera. En local: python scripts/refresh_cloud.py "
                   "--skip-pipeline", "database")
    st.stop()

seasons = sorted(picks_all["season"].astype(str).unique().tolist(), reverse=True)
if st.session_state.get("pk_season") not in seasons:
    st.session_state["pk_season"] = seasons[0]
c1, c2, c3, c4 = st.columns([1.1, 1.2, 1.6, 0.8], vertical_alignment="bottom")
season = c1.selectbox("Temporada", seasons, key="pk_season")
picks = picks_all[picks_all["season"].astype(str) == season]
leagues = ["Todas"] + sorted(picks["league"].astype(str).unique().tolist())
if st.session_state.get("pk_league") not in leagues:
    st.session_state["pk_league"] = "Todas"
league = c2.selectbox("Liga", leagues, key="pk_league")
sel = c3.segmented_control("Selección", list(SELECTIONS), format_func=SELECTIONS.get,
                           default="all", key="pk_sel", required=True, width="stretch")
with c4.popover("Umbrales", icon=":material/tune:", width="stretch"):
    min_ev = st.slider("Valor mínimo (%)", 0.0, 20.0, 3.0, 0.5, key="pk_ev",
                       help="Diferencia mínima entre la probabilidad del modelo y la del mercado.")
    min_odds = st.slider("Cuota mínima", 1.0, 5.0, 1.4, 0.05, key="pk_odds",
                         help="Descarta cuotas muy bajas, donde el margen de la casa domina.")

f = picks[(picks["ev"] >= min_ev / 100) & (picks["odds"] >= min_odds)]
if league != "Todas":
    f = f[f["league"] == league]
if sel != "all":
    f = f[f["selection"] == sel]
f = f.sort_values("ev", ascending=False)
decided = f[f["real_result"].astype(str).str.contains("-", regex=False)]
sim = _simulate(decided) if len(decided) else None

ui.render(ui.notice(
    "Medido fuera de muestra, la cuota de cierre es más precisa que el modelo y apostar sus "
    "«ventajas» perdió dinero. Un ROI positivo en pocos cientos de picks es ruido; lo que mide "
    "ventaja real es batir la cuota de cierre de forma sostenida.", "warn", "Léelo con escepticismo."))
st.space("small")

pct = ui.fmt_pct
ui.kpis([
    {"label": "Selecciones", "value": f"{len(f):,}".replace(",", "."), "sub": f"{len(decided)} decididas"},
    {"label": "Acierto", "value": pct(sim["hit"]) if sim else "—",
     "sub": f"{sim['wins']} de {sim['n']}" if sim else "sin decididas"},
    {"label": "Yield", "value": f"{sim['yield'] * 100:+.1f}%" if sim else "—",
     "sub": "beneficio / apostado", "spark": sim["series"][-30:] if sim else None},
    {"label": "Banco final", "value": f"{sim['bank']:,.0f}".replace(",", ".") if sim else "—",
     "sub": f"ROI {sim['roi'] * 100:+.1f}% sobre {BANK0:,.0f}".replace(",", ".") if sim else ""},
    {"label": "Caída máxima", "value": pct(sim["max_dd"]) if sim else "—",
     "sub": "desde el máximo del banco"},
])

if sim and sim["n"] > 1:
    left, right = st.columns([1.6, 1], gap="medium")
    with left:
        ui.section("Banco simulado", f"Kelly fraccional · banco inicial {BANK0:,.0f}".replace(",", "."))
        charts.bankroll(sim["dates"], sim["series"], BANK0, key="pk_bank")
    with right:
        ui.section("Yield por liga")
        g = sim["by_league"].groupby("league").agg(stake=("stake", "sum"), pnl=("pnl", "sum"),
                                                   n=("pnl", "size"))
        g = g[g["n"] >= 5]
        if len(g) >= 2:
            charts.yield_by_group(g.index.tolist(), (g["pnl"] / g["stake"]).tolist(),
                                  g["n"].tolist(), key="pk_yield")
        else:
            st.caption("Hacen falta al menos 2 ligas con 5+ selecciones decididas.")

ui.section("Selecciones", f"{len(f)} · ordenadas por valor")
if f.empty:
    ui.empty_state("Ninguna selección cumple los filtros", "Relaja los umbrales o cambia de liga.", "search")
else:
    show = f[["date", "league", "home", "away", "selection", "prob_model", "odds", "ev", "stake",
              "real_result"]].copy()
    show["selection"] = show["selection"].map(SELECTIONS).fillna(show["selection"])
    show["prob_model"] = show["prob_model"] * 100
    show["ev"] = show["ev"] * 100
    show["real_result"] = show["real_result"].replace({"pending": "Pendiente"})
    st.dataframe(
        show, hide_index=True, width="stretch", height=420,
        column_config={
            "date": st.column_config.DateColumn("Fecha", format="DD/MM/YY"),
            "league": st.column_config.TextColumn("Liga"),
            "home": st.column_config.TextColumn("Local"),
            "away": st.column_config.TextColumn("Visitante"),
            "selection": st.column_config.TextColumn("Selección"),
            "prob_model": st.column_config.ProgressColumn("Prob. modelo", format="%.1f%%",
                                                          min_value=0, max_value=100),
            "odds": st.column_config.NumberColumn("Cuota", format="%.2f"),
            "ev": st.column_config.NumberColumn("Valor", format="%+.1f%%"),
            "stake": st.column_config.NumberColumn("Stake", format="%.1f"),
            "real_result": st.column_config.TextColumn("Resultado"),
        })
    st.download_button("Descargar CSV", ui.csv_bytes(show),
                       file_name=f"selecciones_{season}.csv", mime="text/csv",
                       icon=":material/download:")
st.caption(f"Fuente: {source}. Pipeline: Elo + GLM Poisson → probabilidades 1X2 → filtro de "
           "valor → Kelly fraccional con tope.")
