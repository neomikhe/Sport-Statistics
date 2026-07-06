"""
Streamlit dashboard MVP para SportStatistics.

Muestra picks de futbol generados por el pipeline, con filtrado interactivo
por EV minimo, liga y seleccion. Grafica la evolucion del bankroll simulado.

Ejecutar:
    venv\\Scripts\\activate
    streamlit run app/streamlit_app.py --server.address 127.0.0.1
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="SportStatistics",
    page_icon=":material/query_stats:",
    layout="wide",
)

from app.auth import require_password  # noqa: E402
from app.refresh import render_refresh_button  # noqa: E402
from app.ui import inject_theme, render_hero  # noqa: E402
from app import charts  # noqa: E402

inject_theme()
require_password()

ROOT = Path(__file__).resolve().parent.parent
BANKROLL_INITIAL = 1000.0

# ----------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------
render_hero("SportStatistics",
            "Análisis estadístico cuantitativo de eventos deportivos")

st.info(
    "**Herramienta educativa de analisis estadistico.** No constituye consejo de "
    "apuestas ni garantiza resultados. Las 'selecciones de valor' son discrepancias "
    "entre el modelo y el mercado, no recomendaciones.",
    icon=":material/info:",
)

# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------
st.sidebar.header("Controles")
# Esta portada muestra picks de FÚTBOL (el único deporte con pipeline de picks).
# NBA, MLB y tenis están en la página "Analizador de partido".
st.sidebar.caption("Picks de fútbol. Los 4 deportes están en **Analizador de partido**.")
inject_theme("football")

# Botón de refresco bajo demanda (solo aparece si hay token+repo en st.secrets).
render_refresh_button()

PICKS_COLS = ["season", "date", "league", "home", "away", "selection",
              "prob_model", "odds", "ev", "kelly_frac", "stake", "real_result"]
NUM_COLS = ["prob_model", "odds", "ev", "kelly_frac", "stake"]


@st.cache_data(ttl=300)
def load_picks():
    """Devuelve (DataFrame, last_refresh, fuente). Prefiere la BD (refrescada por
    el cron); si no hay BD/datos, cae a los CSV locales de data/processed/."""
    try:
        from core.database.connection import get_sqlalchemy_engine
        eng = get_sqlalchemy_engine()
        df = pd.read_sql(
            f"SELECT {', '.join(PICKS_COLS)} FROM football_picks",
            eng, parse_dates=["date"],
        )
        if not df.empty:
            df[NUM_COLS] = df[NUM_COLS].astype(float)
            meta = pd.read_sql(
                "SELECT value FROM app_meta WHERE key = 'last_refresh'", eng
            )
            last = meta["value"].iloc[0] if not meta.empty else None
            return df, last, "BD en la nube"
    except Exception:
        pass

    files = sorted((ROOT / "data" / "processed").glob("picks_football_*.csv"))
    if not files:
        return None, None, None
    frames = []
    for f in files:
        d = pd.read_csv(f, parse_dates=["date"])
        d.insert(0, "season", f.stem.replace("picks_football_", ""))
        frames.append(d)
    return pd.concat(frames, ignore_index=True)[PICKS_COLS], None, "CSV local"


@st.cache_data(ttl=600)
def _model_health():
    """Estado de salud del modelo (lo sella scripts/monitor_drift.py)."""
    import json
    from core.database.meta import get_meta
    raw = get_meta("model_health")
    try:
        return json.loads(raw) if raw else None
    except Exception:
        return None


picks_all, last_refresh, source = load_picks()

_health = _model_health()
if _health and _health.get("status") == "degraded":
    st.warning(
        f"**Modelo degradado**: el log-loss reciente ({_health.get('recent_log_loss')}) "
        f"supera su línea base ({_health.get('baseline_log_loss')}). "
        "Conviene re-entrenar (`python scripts/retrain_all.py`).",
        icon=":material/warning:",
    )

if picks_all is None or picks_all.empty:
    st.warning(
        "No hay picks todavia. Refresca los datos:\n\n"
        "```\npython scripts/refresh_cloud.py --skip-pipeline\n```"
    )
    st.stop()

if last_refresh:
    st.caption(f":material/sync: Última actualización: **{last_refresh}** · fuente: {source}")

seasons = sorted(picks_all["season"].unique().tolist(), reverse=True)
season = st.sidebar.selectbox("Temporada", seasons)

# ----------------------------------------------------------------------
# Datos + filtros (en un desplegable, para que la vista quede limpia)
# ----------------------------------------------------------------------
picks = picks_all[picks_all["season"] == season].copy()

with st.sidebar.expander(":material/tune: Filtros", expanded=False):
    leagues = ["(todas)"] + sorted(picks["league"].unique().tolist())
    league_sel = st.selectbox("Liga", leagues)
    sel_options = ["(todas)"] + sorted(picks["selection"].unique().tolist())
    sel_sel = st.selectbox("Selección", sel_options)
    min_ev_pct = st.slider(
        "Valor mínimo del modelo (%)", 0.0, 20.0, 3.0, 0.5,
        help="Diferencia mínima entre la probabilidad del modelo y la implícita del mercado.",
    )
    min_odds = st.slider(
        "Cuota mínima", 1.00, 5.00, 1.40, 0.05,
        help="Descarta cuotas muy bajas, donde el margen del mercado domina la señal.",
    )

filtered = picks[
    (picks["ev"] >= min_ev_pct / 100)
    & (picks["odds"] >= min_odds)
].copy()
if league_sel != "(todas)":
    filtered = filtered[filtered["league"] == league_sel]
if sel_sel != "(todas)":
    filtered = filtered[filtered["selection"] == sel_sel]
filtered = filtered.sort_values("ev", ascending=False).reset_index(drop=True)

# ----------------------------------------------------------------------
# KPIs
# ----------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Picks totales", f"{len(picks):,}")
col2.metric("Tras filtros", f"{len(filtered):,}")
col3.metric(
    "EV medio",
    f"{filtered['ev'].mean() * 100:.2f} %" if len(filtered) else "-",
)
col4.metric(
    "Cuota media",
    f"{filtered['odds'].mean():.2f}" if len(filtered) else "-",
)

# ----------------------------------------------------------------------
# Tabla de picks
# ----------------------------------------------------------------------
st.subheader(f"Picks de {season}")
if len(filtered) == 0:
    st.info("Ningun pick cumple los filtros actuales.")
else:
    display = filtered[[
        "date", "league", "home", "away", "selection",
        "prob_model", "odds", "ev", "stake", "real_result",
    ]].copy()
    display["ev_pct"] = (display["ev"] * 100).round(2)
    display = display.drop(columns=["ev"])
    display = display.rename(columns={
        "prob_model": "prob", "ev_pct": "EV %",
        "real_result": "resultado",
    })
    display["prob"] = display["prob"].round(3)
    display["odds"] = display["odds"].round(2)
    display["stake"] = display["stake"].round(2)
    st.dataframe(display, width="stretch", hide_index=True)

# ----------------------------------------------------------------------
# Simulacion bankroll
# ----------------------------------------------------------------------
decided = filtered[filtered["real_result"] != "pending"].copy()
if len(decided) > 0:
    st.subheader("Simulacion bankroll (picks decididos)")

    bank = BANKROLL_INITIAL
    rows = []
    wins = losses = 0
    for _, p in decided.sort_values("date").iterrows():
        h, a = map(int, p["real_result"].split("-"))
        won = (
            (p["selection"] == "HOME" and h > a)
            or (p["selection"] == "DRAW" and h == a)
            or (p["selection"] == "AWAY" and h < a)
        )
        if won:
            bank += p["stake"] * (p["odds"] - 1)
            wins += 1
        else:
            bank -= p["stake"]
            losses += 1
        rows.append({"date": p["date"], "bankroll": bank})

    hist = pd.DataFrame(rows)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ganados", wins)
    c2.metric("Perdidos", losses)
    c3.metric("Hit-rate", f"{100 * wins / (wins + losses):.1f} %")
    c4.metric(
        "ROI",
        f"{(bank - BANKROLL_INITIAL) / BANKROLL_INITIAL * 100:+.2f} %",
        delta=f"{bank - BANKROLL_INITIAL:+.2f}",
    )

    charts.bankroll(hist["date"], hist["bankroll"], baseline=BANKROLL_INITIAL)

    st.caption(
        "AVISO: el ROI en muestras <500 picks es altamente ruidoso. "
        "Lo que realmente mide edge es CLV (valor vs cuota de cierre) sostenido "
        "en 200+ picks. ROI positivo aqui NO significa que el modelo sea bueno."
    )
else:
    st.info("Los picks aun no tienen resultado (temporada en curso).")

# ----------------------------------------------------------------------
# Info lateral
# ----------------------------------------------------------------------
with st.expander("Como funciona esto"):
    st.markdown(
        """
        **Pipeline:**
        1. Datos de football-data.co.uk (cuotas Pinnacle cierre) ingestados a PostgreSQL.
        2. Elo dinamico por equipo.
        3. Feature engineering (rolling goles, forma, descanso).
        4. Modelo GLM Poisson entrenado sobre 9 temporadas.
        5. Monte Carlo 10k para cada partido -> probabilidades 1X2.
        6. Filtro EV >= umbral + staking Kelly fraccional.

        **Lo que NO es esto:**
        - No es un sistema de "aciertos". Lo que importa es EV, no win-rate.
        - No predice el futuro. Estima probabilidades con incertidumbre.
        - No garantiza ganar dinero real.

        Bind a `127.0.0.1` por defecto. Nunca expongas este dashboard a internet.
        """
    )
