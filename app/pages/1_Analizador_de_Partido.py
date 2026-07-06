"""
Analizador interactivo de partido para los 4 deportes.

Eliges deporte + 2 equipos/jugadores, y el sistema calcula las probabilidades
reales basadas en los modelos entrenados:
  - Futbol:    GLM Poisson + simulacion exacta -> 1X2, O/U 2.5, BTTS, top marcadores
  - NBA:       Ridge dual + Monte Carlo Normal -> ML, spread, total puntos
  - Tenis:     Elo por superficie + Barnett-Clarke -> prob ganador
  - Beisbol:   Pythagorean + Elo logistico -> prob ML

Ejecutar:
    streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from app.auth import require_password  # noqa: E402
from app.ui import inject_theme, matchup_header, section_header  # noqa: E402
from app import charts  # noqa: E402
from core.ai import gemini as _gemini  # noqa: E402
from core.ai import adjust as _adjust  # noqa: E402

st.set_page_config(page_title="Analizador", page_icon=":material/query_stats:", layout="wide")
require_password()

# ---------- Sidebar ----------
sport_label = st.sidebar.radio(
    "Deporte",
    ["Fútbol", "Baloncesto", "Béisbol", "Tenis"],
    index=0,
)

# Inyecta el tema visual dinámico del deporte
inject_theme(sport_label)

st.title("Analizador de partido")
st.caption(
    "Selecciona un deporte y dos equipos/jugadores para ver "
    "probabilidades de cada mercado disponible."
)

def _render_comparison_bar(title, home_val, away_val, format_str="{:.1f}", suffix="", color="#5c9a85"):
    total = home_val + away_val
    pct = (home_val / total * 100) if total > 0 else 50
    st.markdown(
        f"""
        <div style="background: rgba(13, 20, 38, 0.45); border: 1px solid rgba(255,255,255,0.04); border-radius: 12px; padding: 12px 16px; margin-bottom: 8px; font-family: 'Inter', sans-serif;">
            <div style="display: flex; justify-content: space-between; font-weight: 700; font-size: 13px; color: #ffffff; margin-bottom: 6px;">
                <span>{format_str.format(home_val)}{suffix}</span>
                <span style="color: #94a3b8; font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em;">{title}</span>
                <span>{format_str.format(away_val)}{suffix}</span>
            </div>
            <div style="height: 5px; background: rgba(255,255,255,0.06); border-radius: 99px; overflow: hidden; display: flex;">
                <div style="width: {pct}%; background: {color};"></div>
                <div style="width: {100-pct}%; background: #64748b;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

@st.cache_resource
def _engine():
    return get_sqlalchemy_engine()


engine = _engine()


@st.cache_data(ttl=600)
def _entities(sport_code: str) -> pd.DataFrame:
    return pd.read_sql(
        """
        SELECT id, name, country FROM entities
        WHERE sport_id = (SELECT id FROM sports WHERE code = %(sport)s)
        ORDER BY name
        """,
        _engine(),
        params={"sport": sport_code},
    )



# ============================================================
#  FÚTBOL
# ============================================================

def _football_team_stats(team_id: int, n: int = 10):
    df = pd.read_sql(
        """
        SELECT date,
            CASE WHEN home_team_id = %(tid)s THEN home_goals ELSE away_goals END AS gf,
            CASE WHEN home_team_id = %(tid)s THEN away_goals ELSE home_goals END AS ga
        FROM football_matches
        WHERE (home_team_id = %(tid)s OR away_team_id = %(tid)s)
          AND home_goals IS NOT NULL
        ORDER BY date DESC
        LIMIT %(n)s
        """,
        engine,
        params={"tid": team_id, "n": n},
        parse_dates=["date"],
    )
    if df.empty:
        return {"gf_5": 1.4, "gf_10": 1.4, "ga_5": 1.4, "ga_10": 1.4, "form_5": 6}
    last5, last10 = df.head(5), df.head(10)
    return {
        "gf_5": float(last5["gf"].mean()),
        "gf_10": float(last10["gf"].mean()),
        "ga_5": float(last5["ga"].mean()),
        "ga_10": float(last10["ga"].mean()),
        "form_5": int(sum(
            3 if r["gf"] > r["ga"] else (1 if r["gf"] == r["ga"] else 0)
            for _, r in last5.iterrows()
        )),
    }


def _football_latest_elo(team_id: int) -> float:
    df = pd.read_sql(
        """
        SELECT elo FROM football_elo
        WHERE team_id = %(tid)s
        ORDER BY date DESC LIMIT 1
        """,
        engine,
        params={"tid": team_id},
    )
    return float(df["elo"].iloc[0]) if not df.empty else 1500.0


def _football_recent_matches(team_id: int, n: int = 10):
    """Últimos n partidos del equipo (orden cronológico) para gráfica + tabla."""
    df = pd.read_sql(
        """
        SELECT m.date,
            CASE WHEN m.home_team_id = %(tid)s THEN ea.name ELSE eh.name END AS rival,
            CASE WHEN m.home_team_id = %(tid)s THEN m.home_goals ELSE m.away_goals END AS gf,
            CASE WHEN m.home_team_id = %(tid)s THEN m.away_goals ELSE m.home_goals END AS ga,
            CASE WHEN m.home_team_id = %(tid)s THEN 'L' ELSE 'V' END AS loc
        FROM football_matches m
        JOIN entities eh ON eh.id = m.home_team_id
        JOIN entities ea ON ea.id = m.away_team_id
        WHERE (m.home_team_id = %(tid)s OR m.away_team_id = %(tid)s)
          AND m.home_goals IS NOT NULL
        ORDER BY m.date DESC
        LIMIT %(n)s
        """,
        engine, params={"tid": team_id, "n": n}, parse_dates=["date"],
    )
    if df.empty:
        return df
    df = df.sort_values("date").reset_index(drop=True)
    df["GF"] = df["gf"].astype(int)
    df["GA"] = df["ga"].astype(int)
    df["Fecha"] = df["date"].dt.strftime("%Y-%m-%d")
    df["Rival"] = df["loc"] + " vs " + df["rival"].str.slice(0, 16)
    df["Marcador"] = df["GF"].astype(str) + "-" + df["GA"].astype(str)
    df["Res"] = [("G" if g > c else ("E" if g == c else "P"))
                 for g, c in zip(df["GF"], df["GA"])]
    return df


def _render_team_detail(col, name, team_id, elo, stats):
    """Panel de un equipo: métricas + evolución de goles + últimos resultados."""
    with col:
        st.markdown(f"#### {name}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Elo", f"{elo:.0f}")
        m2.metric("Forma últ.5", f"{stats['form_5']}/15")
        m3.metric("GF–GA últ.5", f"{stats['gf_5']:.1f}–{stats['ga_5']:.1f}")

        recent = _football_recent_matches(team_id, n=10)
        if recent.empty:
            st.caption("Sin partidos recientes.")
            return
        charts.trend(recent, "Fecha", "GF", "GA",
                     "Goles a favor", "Goles en contra", charts.ACCENT["football"])
        tbl = recent.iloc[::-1][["Fecha", "Rival", "Marcador", "Res"]].head(6)
        st.dataframe(tbl, hide_index=True, use_container_width=True)


# ============================================================
#  Helpers compartidos: render de mercados + paneles por equipo
# ============================================================

# Grupos que contienen la probabilidad de victoria (moneyline) por deporte.
_ML_GROUPS = ("1X2", "Ganador (ML)", "Ganador")


def _render_win_bar(markets, home_name, away_name, accent, sport=None):
    """Barra apilada de probabilidad de victoria (estilo Sofascore, deporte-agnóstico).

    Si `sport` es 2-way (NBA/MLB) y existe su calibrador, calibra P(gana local).
    """
    grp = next((g for g in _ML_GROUPS if any(m["grupo"] == g for m in markets)), None)
    if grp is None:
        return
    probs = {m["mercado"]: m["prob"] for m in markets if m["grupo"] == grp}
    p_home = probs.get("Gana local", probs.get(f"Gana {home_name}"))
    p_away = probs.get("Gana visitante", probs.get(f"Gana {away_name}"))
    if p_home is None or p_away is None:
        return
    p_draw = probs.get("Empate")
    calibrated = False
    if sport is not None and p_draw is None:      # 2-way: NBA/MLB
        cal = _binary_calibrator(sport)
        if cal is not None:
            p_home = cal.calibrate_home(p_home)
            p_away = 1.0 - p_home
            calibrated = True
    labels, values, colors = [home_name], [p_home], [accent]
    if p_draw is not None:
        labels.append("Empate")
        values.append(p_draw)
        colors.append("#475569")
    labels.append(away_name)
    values.append(p_away)
    colors.append("#94a3b8")
    section_header("Probabilidad de victoria", "target")
    charts.win_probability(labels, values, colors)
    if calibrated:
        st.caption("Moneyline **calibrado** (isotónica sobre histórico).")


def _render_top_gauge(markets, accent):
    """Donut radial del mercado más probable."""
    from core.markets import top_markets

    top = top_markets(markets, n=1)
    if not top:
        return
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        charts.gauge(top[0]["prob"], accent, label=top[0]["mercado"])


def _render_markets_section(markets, partido, accent="#5c9a85"):
    """Top 3 mercados + tabla completa + picks premium 70–99% (deporte-agnóstico)."""
    from core.markets import premium_picks, top_markets

    section_header("3 mercados más probables", "trophy")
    for col, mk in zip(st.columns(3), top_markets(markets, n=3)):
        col.metric(mk["mercado"], f"{mk['prob']*100:.1f} %", help=mk["grupo"])
    _render_top_gauge(markets, accent)

    section_header("Todos los mercados", "list")
    df = pd.DataFrame(markets)
    df["Mercado"] = [m + ("  (aprox.)" if ap else "")
                     for m, ap in zip(df["mercado"], df["aprox"])]
    df["Prob."] = (df["prob"] * 100).map("{:.1f} %".format)
    st.dataframe(
        df.rename(columns={"grupo": "Grupo"})[["Grupo", "Mercado", "Prob."]],
        hide_index=True, use_container_width=True, height=340,
    )

    section_header("Picks premium (70%–99%)", "star")
    prem = premium_picks(markets)
    if prem:
        dfp = pd.DataFrame([{"Partido": partido, "Pick": x["mercado"],
                             "Probabilidad": f"{x['prob']*100:.1f} %"} for x in prem])
        st.dataframe(dfp, hide_index=True, use_container_width=True)
    else:
        st.info("Ningún mercado cae en 70%–99%: enfrentamiento parejo, no se fuerzan picks.")


def _recent_scores(table, col_home, col_away, team_id, n=10):
    """Últimos n partidos de un equipo (basketball/baseball) para gráfica + tabla.

    `table`/`col_*` son literales internos (no entrada de usuario)."""
    df = pd.read_sql(
        f"""
        SELECT g.date,
            CASE WHEN g.home_team_id = %(t)s THEN ea.name ELSE eh.name END AS rival,
            CASE WHEN g.home_team_id = %(t)s THEN g.{col_home} ELSE g.{col_away} END AS f,
            CASE WHEN g.home_team_id = %(t)s THEN g.{col_away} ELSE g.{col_home} END AS c,
            CASE WHEN g.home_team_id = %(t)s THEN 'L' ELSE 'V' END AS loc
        FROM {table} g
        JOIN entities eh ON eh.id = g.home_team_id
        JOIN entities ea ON ea.id = g.away_team_id
        WHERE (g.home_team_id = %(t)s OR g.away_team_id = %(t)s)
          AND g.{col_home} IS NOT NULL
        ORDER BY g.date DESC
        LIMIT %(n)s
        """,
        engine, params={"t": team_id, "n": n}, parse_dates=["date"],
    )
    if df.empty:
        return df
    df = df.sort_values("date").reset_index(drop=True)
    df["F"] = df["f"].astype(int)
    df["C"] = df["c"].astype(int)
    df["Fecha"] = df["date"].dt.strftime("%Y-%m-%d")
    df["Rival"] = df["loc"] + " vs " + df["rival"].str.slice(0, 16)
    df["Marcador"] = df["F"].astype(str) + "-" + df["C"].astype(str)
    df["Res"] = [("G" if a > b else ("E" if a == b else "P"))
                 for a, b in zip(df["F"], df["C"])]
    return df


def _render_score_panel(col, name, elo, recent, for_label, against_label,
                        accent=charts.ACCENT["basketball"]):
    """Panel NBA/MLB: Elo + medias + evolución a favor/contra + últimos resultados."""
    with col:
        st.markdown(f"#### {name}")
        if recent.empty:
            st.metric("Elo", f"{elo:.0f}")
            st.caption("Sin partidos recientes.")
            return
        m1, m2, m3 = st.columns(3)
        m1.metric("Elo", f"{elo:.0f}")
        m2.metric("A favor (med.)", f"{recent['F'].mean():.1f}")
        m3.metric("En contra (med.)", f"{recent['C'].mean():.1f}")
        charts.trend(recent, "Fecha", "F", "C", for_label, against_label, accent)
        st.dataframe(recent.iloc[::-1][["Fecha", "Rival", "Marcador", "Res"]].head(6),
                     hide_index=True, use_container_width=True)


def _tennis_recent(player_id, n=10):
    return pd.read_sql(
        """
        SELECT m.date, m.surface,
            CASE WHEN m.player1_id = %(p)s THEN e2.name ELSE e1.name END AS rival,
            CASE WHEN m.winner_id = %(p)s THEN 1 ELSE 0 END AS won,
            m.score
        FROM tennis_matches m
        JOIN entities e1 ON e1.id = m.player1_id
        JOIN entities e2 ON e2.id = m.player2_id
        WHERE (m.player1_id = %(p)s OR m.player2_id = %(p)s)
        ORDER BY m.date DESC
        LIMIT %(n)s
        """,
        engine, params={"p": player_id, "n": n}, parse_dates=["date"],
    )


def _render_tennis_detail(p1_id, p1_name, p2_id, p2_name):
    for col, pid, name in zip(st.columns(2), [p1_id, p2_id], [p1_name, p2_name]):
        with col:
            st.markdown(f"#### {name}")
            se = pd.read_sql(
                """
                SELECT DISTINCT ON (surface) surface, elo
                FROM tennis_elo WHERE player_id = %(p)s
                ORDER BY surface, date DESC
                """,
                engine, params={"p": pid},
            )
            if not se.empty:
                st.caption("Elo por superficie")
                charts.bars(se["surface"].tolist(), se["elo"].tolist(),
                            charts.ACCENT["tennis"], height=180)
            rec = _tennis_recent(pid, n=10)
            if rec.empty:
                st.caption("Sin partidos recientes.")
                continue
            st.metric("Win-rate últ.10", f"{rec['won'].mean()*100:.0f} %")
            tbl = rec.assign(
                Fecha=rec["date"].dt.strftime("%Y-%m-%d"),
                Res=rec["won"].map({1: "G", 0: "P"}),
                Rival=rec["rival"].str.slice(0, 16),
            ).rename(columns={"surface": "Sup.", "score": "Marcador"})
            st.dataframe(tbl[["Fecha", "Rival", "Sup.", "Marcador", "Res"]].head(6),
                         hide_index=True, use_container_width=True)


# ============================================================
#  Contexto IA (Gemini + búsqueda web) — los 4 deportes
# ============================================================

_IMPACT_BADGE = {
    "none": "Sin bajas relevantes",
    "low": "Bajas menores",
    "medium": "Bajas relevantes",
    "high": "Baja clave",
    "unknown": "Sin datos fiables",
}


def _ai_checkbox(sport_word: str) -> bool:
    """Checkbox de contexto IA (solo aparece si hay clave de Gemini configurada)."""
    if not _gemini.is_enabled():
        return False
    return st.checkbox(
        f"Ajustar por bajas/lesiones de {sport_word} (IA con búsqueda web)",
        help="Consulta contexto actual (lesiones, sanciones, descansos) y ajusta la fuerza. "
             "El número lo sigue calculando el modelo, no la IA.",
    )


@st.cache_data(ttl=21600, show_spinner="Consultando bajas y contexto actual…")
def _ai_context(home, away, sport, league=""):
    """Contexto cacheado 6h (no llama a la API en cada rerun)."""
    return _gemini.match_context(home, away, sport, league)


def _render_ai_context(home, away, ctx, adj_home="", adj_away=""):
    """Pinta el contexto IA por lado. adj_* es un texto ya formateado (p.ej. '×0.90' o '−45 Elo')."""
    section_header("Contexto actual (IA + búsqueda web)", "bot")
    cols = st.columns(2)
    for col, name, side, adj in [(cols[0], home, "home", adj_home), (cols[1], away, "away", adj_away)]:
        with col:
            d = ctx[side]
            st.markdown(f"**{name}** — {_IMPACT_BADGE.get(d['impact'], 'Sin datos fiables')}")
            for absence in d["absences"]:
                st.markdown(f"- {absence}")
            if d["note"]:
                st.caption(d["note"])
            if adj:
                st.caption(f"Ajuste aplicado: {adj}")
    st.caption("Contexto obtenido por IA con búsqueda web: puede tener errores u omisiones. "
               "La probabilidad la calcula el modelo, no la IA.")


@st.cache_resource
def _football_calibrator():
    """Calibrador isotónico 1X2 (o None si aún no se entrenó). Sin sklearn en runtime."""
    from core.calibration.isotonic import load_calibrator
    return load_calibrator(ROOT / "data" / "models" / "football_calibrator_v1.joblib")


@st.cache_resource
def _binary_calibrator(sport):
    """Calibrador binario del moneyline (NBA/MLB/tenis) o None. Sin sklearn en runtime."""
    from core.calibration.isotonic import load_binary_calibrator
    return load_binary_calibrator(ROOT / "data" / "models" / f"{sport}_calibrator_v1.joblib")


def _render_market_comparison(ph, pdr, pa, home_name, away_name):
    """Compara la probabilidad del MODELO con la del MERCADO (línea de cierre).

    El modelo NO usa cuotas para predecir; esto solo VALIDA la calidad de la
    probabilidad y dimensiona con Kelly. Incluye el veredicto OOS honesto.
    """
    from core.betting.ev import expected_value
    from core.betting.kelly import kelly_fractional

    with st.expander("Comparar con el mercado (cuotas 1X2)"):
        st.caption("Introduce las cuotas decimales de cierre. El modelo NO las usa para "
                   "predecir: esto solo mide si tu probabilidad discrepa del mercado.")
        cc1, cc2, cc3 = st.columns(3)
        oh = cc1.number_input(f"Cuota {home_name[:12]}", min_value=1.01, value=2.00, step=0.05)
        od = cc2.number_input("Cuota empate", min_value=1.01, value=3.40, step=0.05)
        oa = cc3.number_input(f"Cuota {away_name[:12]}", min_value=1.01, value=3.80, step=0.05)
        inv = [1.0 / oh, 1.0 / od, 1.0 / oa]
        s = sum(inv)
        mkt = [x / s for x in inv]
        rows = []
        for name, pm, mk, price in zip([home_name, "Empate", away_name],
                                       [ph, pdr, pa], mkt, [oh, od, oa]):
            ev = expected_value(pm, price)
            f = min(kelly_fractional(pm, price, 0.25), 0.05)
            rows.append({
                "Resultado": name,
                "Modelo": f"{pm*100:.1f}%",
                "Mercado": f"{mk*100:.1f}%",
                "Edge": f"{(pm-mk)*100:+.1f}%",
                "EV @cuota": f"{ev*100:+.1f}%",
                "Kelly ¼": f"{f*100:.1f}%",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption(
            "**Realidad medida (OOS 2024-25):** la línea de cierre es MÁS acertada que el "
            "modelo (log-loss 0.98 vs 1.01) y apostar los 'edges' del modelo dio **−12.8% ROI**. "
            "Cuando modelo y mercado discrepan, **suele acertar el mercado**. Trata el 'valor' "
            "con máximo escepticismo."
        )


def show_football():
    st.subheader("Fútbol")
    st.caption(
        "Datos disponibles: **Premier League, La Liga, Serie A, Bundesliga, Ligue 1** "
        "(temporadas 2015-16 a 2025-26). NO incluye Liga MX, MLS, Argentina, Brasil, etc."
    )

    leagues_df = pd.read_sql(
        "SELECT DISTINCT league FROM football_matches ORDER BY league",
        engine,
    )
    leagues = ["(todas)"] + leagues_df["league"].tolist()
    league = st.selectbox("Liga", leagues)

    if league == "(todas)":
        teams_df = _entities("football")[["id", "name"]]
    else:
        teams_df = pd.read_sql(
            """
            SELECT DISTINCT e.id, e.name FROM entities e
            JOIN football_matches m
              ON m.home_team_id = e.id OR m.away_team_id = e.id
            WHERE m.league = %(lg)s
              AND e.sport_id = (SELECT id FROM sports WHERE code = 'football')
            ORDER BY e.name
            """,
            engine,
            params={"lg": league},
        )

    if teams_df.empty:
        st.warning("Sin equipos para esta liga.")
        return

    col1, col2 = st.columns(2)
    home_name = col1.selectbox("Equipo local", teams_df["name"].tolist())
    away_options = teams_df[teams_df["name"] != home_name]["name"].tolist()
    away_name = col2.selectbox("Equipo visitante", away_options)

    use_ai = _ai_checkbox("fútbol")

    if not st.button("Calcular probabilidades", type="primary"):
        return

    from sports.football.markets import (
        all_markets, top_markets, premium_picks, top_scorelines as top_scores
    )

    model_path = ROOT / "data" / "models" / "football_poisson_v1.joblib"
    if not model_path.exists():
        st.error("Falta el modelo entrenado: ejecuta `python scripts/train_football_model.py`")
        return
    with st.spinner("Calculando probabilidades…"):   # un único feedback que cubre todo el cómputo
        model = joblib.load(model_path)
        home_id = int(teams_df[teams_df["name"] == home_name]["id"].iloc[0])
        away_id = int(teams_df[teams_df["name"] == away_name]["id"].iloc[0])
        home_elo = _football_latest_elo(home_id)
        away_elo = _football_latest_elo(away_id)
        home_stats = _football_team_stats(home_id)
        away_stats = _football_team_stats(away_id)
        features = pd.DataFrame([{
            "home_elo": home_elo, "away_elo": away_elo,
            "home_gf_5": home_stats["gf_5"], "home_gf_10": home_stats["gf_10"],
            "home_ga_5": home_stats["ga_5"], "home_ga_10": home_stats["ga_10"],
            "away_gf_5": away_stats["gf_5"], "away_gf_10": away_stats["gf_10"],
            "away_ga_5": away_stats["ga_5"], "away_ga_10": away_stats["ga_10"],
            "home_form_5": home_stats["form_5"],
            "away_form_5": away_stats["form_5"],
            "home_rest": 7, "away_rest": 7,
        }])
        pred = model.predict_lambda(features)
        lh, la = float(pred["lambda_home"].iloc[0]), float(pred["lambda_away"].iloc[0])

    # --- Ajuste opcional por contexto IA (bajas/lesiones, búsqueda web) ---
    if use_ai:
        ctx = _ai_context(home_name, away_name, "football", league if league != "(todas)" else "")
        if ctx:
            mh = _adjust.lambda_multiplier(ctx["home"]["impact"])
            ma = _adjust.lambda_multiplier(ctx["away"]["impact"])
            _render_ai_context(home_name, away_name, ctx,
                               f"×{mh:.2f}" if mh != 1 else "", f"×{ma:.2f}" if ma != 1 else "")
            lh, la = lh * mh, la * ma
        else:
            st.info("Contexto IA no disponible ahora mismo (sin datos fiables o límite de la "
                    "API). Se muestra la probabilidad base del modelo.")

    RHO = -0.10  # Dixon-Coles (spec ρ≈-0.10): mejora la calibración de marcadores bajos
    markets = all_markets(lh, la, rho=RHO)   # Dixon-Coles es instantáneo (ya cubierto por el spinner)

    def pget(mercado):
        return next(x["prob"] for x in markets if x["mercado"] == mercado)

    st.markdown(f"### {home_name} vs {away_name}")
    
    matchup_header(home_name, away_name, "#5c9a85", "92, 154, 133",
                   subtitle=f"{league} · Fútbol" if league and league != "(todas)" else "Fútbol")
    
    # Renderizamos las barras comparativas
    _render_comparison_bar("Rating ELO", home_elo, away_elo, format_str="{:.0f}", color="#5c9a85")
    _render_comparison_bar("Expectativa de Goles (λ)", lh, la, format_str="{:.2f}", color="#5c9a85")
    
    section_header("Métricas y Cuotas del Modelo", "activity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Elo local", f"{home_elo:.0f}")
    c2.metric("Elo visitante", f"{away_elo:.0f}")
    c3.metric("λ goles local", f"{lh:.2f}")
    c4.metric("λ goles visit", f"{la:.2f}")

    section_header("3 mercados más probables", "trophy")
    for col, mk in zip(st.columns(3), top_markets(markets, n=3)):
        col.metric(mk["mercado"], f"{mk['prob']*100:.1f} %", help=mk["grupo"])
    _render_top_gauge(markets, charts.ACCENT["football"])

    section_header("Resultado 1X2", "medal")
    ph, pdr, pa = pget("Gana local"), pget("Empate"), pget("Gana visitante")
    cal = _football_calibrator()
    if cal is not None:
        ph, pdr, pa = (float(x) for x in cal.transform([[ph, pdr, pa]])[0])
        st.caption("Probabilidades 1X2 **calibradas** (isotónica sobre histórico). "
                   "El resto de mercados salen de la matriz Dixon-Coles del modelo.")
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{home_name} gana", f"{ph*100:.1f} %")
    c2.metric("Empate", f"{pdr*100:.1f} %")
    c3.metric(f"{away_name} gana", f"{pa*100:.1f} %")
    section_header("Probabilidad de victoria", "target")
    charts.win_probability([home_name, "Empate", away_name], [ph, pdr, pa],
                           [charts.ACCENT["football"], "#475569", "#94a3b8"])
    _render_market_comparison(ph, pdr, pa, home_name, away_name)

    section_header("Todos los mercados", "list")
    st.caption("Todos salen de la MISMA matriz de marcadores (Dixon-Coles, ρ=−0.10). "
               "Los de 1ª mitad/mitades son aproximación (mitades independientes ~45/55).")
    df_mk = pd.DataFrame(markets)
    df_mk["Mercado"] = [m + ("  (aprox.)" if ap else "")
                        for m, ap in zip(df_mk["mercado"], df_mk["aprox"])]
    df_mk["Prob."] = (df_mk["prob"] * 100).map("{:.1f} %".format)
    st.dataframe(
        df_mk.rename(columns={"grupo": "Grupo"})[["Grupo", "Mercado", "Prob."]],
        hide_index=True, use_container_width=True, height=380,
    )

    section_header("Picks premium (70%–99%)", "star")
    prem = premium_picks(markets)
    if prem:
        df_prem = pd.DataFrame([
            {"Partido": f"{home_name} vs {away_name}", "Pick": x["mercado"],
             "Probabilidad": f"{x['prob']*100:.1f} %"} for x in prem
        ])
        st.dataframe(df_prem, hide_index=True, use_container_width=True)
    else:
        st.info("Ningún mercado cae en 70%–99%: partido parejo, no se fuerzan picks.")

    section_header("Marcadores más probables", "target")
    top = top_scores(lh, la, rho=RHO, n=10)
    df_top = pd.DataFrame([{"Marcador": f"{h} - {a}", "_p": p} for h, a, p in top])
    df_top["Probabilidad"] = (df_top["_p"] * 100).map("{:.2f} %".format)
    cc1, cc2 = st.columns(2)
    cc1.dataframe(df_top[["Marcador", "Probabilidad"]], hide_index=True, use_container_width=True)
    with cc2:
        charts.bars(df_top["Marcador"].tolist(), df_top["_p"].tolist(),
                    charts.ACCENT["football"], height=320, horizontal=True, pct=True)

    st.caption(
        "Probabilidades del modelo (Elo + Poisson/Dixon-Coles), **calibradas y sin usar "
        "cuotas**. Un favorito del 75% pierde 1 de cada 4 veces. El modelo NO usa xG, lesiones "
        "ni alineaciones (no disponibles), así que su margen de error es mayor."
    )

    st.divider()
    section_header("Detalle por equipo", "trending")
    tcol1, tcol2 = st.columns(2)
    _render_team_detail(tcol1, home_name, home_id, home_elo, home_stats)
    _render_team_detail(tcol2, away_name, away_id, away_elo, away_stats)


# ============================================================
#  BALONCESTO
# ============================================================

def _basketball_latest_elo(team_id: int) -> float:
    """Calcula Elo en memoria para todos los partidos hasta hoy y devuelve el de team_id."""
    from sports.basketball.elo import BasketballEloSystem
    df = pd.read_sql(
        """
        SELECT date, home_team_id, away_team_id, home_score, away_score
        FROM basketball_games
        WHERE home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY date
        """,
        engine,
        parse_dates=["date"],
    )
    if df.empty:
        return 1500.0
    elo = BasketballEloSystem()
    for _, r in df.iterrows():
        d = r["date"]
        season = f"{d.year}-{str(d.year + 1)[-2:]}" if d.month >= 10 else f"{d.year - 1}-{str(d.year)[-2:]}"
        elo.process_game(d, season, int(r["home_team_id"]), int(r["away_team_id"]),
                         int(r["home_score"]), int(r["away_score"]))
    return elo.get(team_id)


@st.cache_data(ttl=600)
def _all_nba_elos() -> dict:
    """Cache: devuelve {team_id: elo} para todos los equipos NBA."""
    from sports.basketball.elo import BasketballEloSystem
    df = pd.read_sql(
        """
        SELECT date, home_team_id, away_team_id, home_score, away_score
        FROM basketball_games
        WHERE home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY date
        """,
        _engine(),
        parse_dates=["date"],
    )
    if df.empty:
        return {}
    elo = BasketballEloSystem()
    for _, r in df.iterrows():
        d = r["date"]
        season = f"{d.year}-{str(d.year + 1)[-2:]}" if d.month >= 10 else f"{d.year - 1}-{str(d.year)[-2:]}"
        elo.process_game(d, season, int(r["home_team_id"]), int(r["away_team_id"]),
                         int(r["home_score"]), int(r["away_score"]))
    teams = set(df["home_team_id"]).union(set(df["away_team_id"]))
    return {int(t): float(elo.get(int(t))) for t in teams}


def show_basketball():
    st.subheader("Baloncesto NBA")
    st.caption("Datos: 30 equipos NBA, temporadas 2019-20 a 2025-26 (Regular Season + Playoffs).")

    teams = _entities("basketball")
    if teams.empty:
        st.error("No hay equipos NBA. Ejecuta `python scripts/download_basketball_data.py`")
        return

    col1, col2 = st.columns(2)
    home_name = col1.selectbox("Equipo local", teams["name"].tolist(), key="nba_h")
    away_options = teams[teams["name"] != home_name]["name"].tolist()
    away_name = col2.selectbox("Equipo visitante", away_options, key="nba_a")

    use_ai = _ai_checkbox("la NBA")

    if not st.button("Calcular probabilidades", type="primary", key="nba_btn"):
        return

    from sports.basketball.simulation import expected_scores
    from sports.basketball.markets import all_markets

    elos = _all_nba_elos()
    home_id = int(teams[teams["name"] == home_name]["id"].iloc[0])
    away_id = int(teams[teams["name"] == away_name]["id"].iloc[0])
    home_elo = elos.get(home_id, 1500.0)
    away_elo = elos.get(away_id, 1500.0)

    avg_total = pd.read_sql(
        "SELECT AVG(home_score + away_score) AS t FROM basketball_games WHERE home_score IS NOT NULL",
        engine,
    )["t"].iloc[0]
    total_mean = float(avg_total) if avg_total is not None else 225.0

    e_home, e_away = expected_scores(home_elo, away_elo, total_mean=total_mean)

    if use_ai:
        ctx = _ai_context(home_name, away_name, "basketball")
        if ctx:
            mh = _adjust.points_multiplier(ctx["home"]["impact"])
            ma = _adjust.points_multiplier(ctx["away"]["impact"])
            _render_ai_context(home_name, away_name, ctx,
                               f"×{mh:.3f}" if mh != 1 else "", f"×{ma:.3f}" if ma != 1 else "")
            e_home, e_away = e_home * mh, e_away * ma
        else:
            st.info("Contexto IA no disponible ahora mismo. Se muestra la probabilidad base.")

    with st.spinner("Simulando 20.000 partidos (Monte Carlo)…"):
        markets = all_markets(e_home, e_away, rng=np.random.default_rng(42))
    partido = f"{home_name} vs {away_name}"

    st.markdown(f"### {partido}")
    
    matchup_header(home_name, away_name, "#bd8560", "189, 133, 96",
                   subtitle="Baloncesto · NBA")
    
    # Renderizamos las barras comparativas
    _render_comparison_bar("Rating ELO", home_elo, away_elo, format_str="{:.0f}", color="#bd8560")
    _render_comparison_bar("Puntos Esperados", e_home, e_away, format_str="{:.1f}", color="#bd8560")
    
    section_header("Métricas del Modelo", "activity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Elo local", f"{home_elo:.0f}")
    c2.metric("Elo visitante", f"{away_elo:.0f}")
    c3.metric("Pts esp. local", f"{e_home:.1f}")
    c4.metric("Pts esp. visit.", f"{e_away:.1f}")
    st.caption(f"Margen esperado: **{home_name} {e_home - e_away:+.1f}** · "
               f"total esperado **{e_home + e_away:.0f}** puntos.")

    _render_win_bar(markets, home_name, away_name, charts.ACCENT["basketball"], sport="basketball")
    _render_markets_section(markets, partido, charts.ACCENT["basketball"])

    st.caption(
        "Probabilidades del modelo (Elo + Normal σ≈11), **calibradas, sin cuotas**. Un "
        "favorito del 80% pierde 1 de cada 5. NO usa Net Rating, ritmo real ni el parte de "
        "lesiones/descanso del día (no disponibles): el margen de error es mayor."
    )

    st.divider()
    section_header("Detalle por equipo", "trending")
    t1, t2 = st.columns(2)
    _render_score_panel(t1, home_name, home_elo,
                        _recent_scores("basketball_games", "home_score", "away_score", home_id),
                        "Puntos a favor", "Puntos en contra")
    _render_score_panel(t2, away_name, away_elo,
                        _recent_scores("basketball_games", "home_score", "away_score", away_id),
                        "Puntos a favor", "Puntos en contra")


# ============================================================
#  TENIS
# ============================================================

def show_tennis():
    st.subheader("Tenis (ATP + WTA)")
    st.caption("Datos: Sackmann tennis_atp / tennis_wta, 2021-2024 (~22.400 partidos).")

    players = _entities("tennis")
    if players.empty:
        st.error("No hay jugadores. Ejecuta `python scripts/ingest_tennis_data.py`")
        return

    col1, col2 = st.columns(2)
    p1_name = col1.selectbox("Jugador 1", players["name"].tolist(), key="tn_p1")
    p2_options = players[players["name"] != p1_name]["name"].tolist()
    p2_name = col2.selectbox("Jugador 2", p2_options, key="tn_p2")

    col3, col4 = st.columns(2)
    surface = col3.selectbox("Superficie", ["hard", "clay", "grass", "carpet"])
    best_of = col4.radio("Formato", [3, 5], horizontal=True, key="tn_bo")

    use_ai = _ai_checkbox("tenis")

    if not st.button("Calcular probabilidades", type="primary", key="tn_btn"):
        return

    from sports.tennis.elo import expected_score
    from sports.tennis.barnett_clarke import estimate_serve_return_from_elo
    from sports.tennis.markets import all_markets, p_set_from_match

    p1_id = int(players[players["name"] == p1_name]["id"].iloc[0])
    p2_id = int(players[players["name"] == p2_name]["id"].iloc[0])

    elo_query = """
        WITH last AS (
            SELECT player_id, surface, MAX(date) AS d
            FROM tennis_elo
            WHERE player_id IN %(ids)s
              AND surface = %(s)s
            GROUP BY player_id, surface
        )
        SELECT te.player_id, te.elo
        FROM tennis_elo te
        JOIN last l ON l.player_id = te.player_id AND l.surface = te.surface AND l.d = te.date
        WHERE te.surface = %(s)s
    """
    elos = pd.read_sql(
        elo_query, engine,
        params={"ids": (p1_id, p2_id), "s": surface},
    )
    e1 = float(elos[elos["player_id"] == p1_id]["elo"].iloc[0]) if not elos[elos["player_id"] == p1_id].empty else 1500.0
    e2 = float(elos[elos["player_id"] == p2_id]["elo"].iloc[0]) if not elos[elos["player_id"] == p2_id].empty else 1500.0

    if use_ai:
        ctx = _ai_context(p1_name, p2_name, "tennis")
        if ctx:
            ph = _adjust.elo_penalty(ctx["home"]["impact"])
            pa = _adjust.elo_penalty(ctx["away"]["impact"])
            _render_ai_context(p1_name, p2_name, ctx,
                               f"−{ph:.0f} Elo" if ph else "", f"−{pa:.0f} Elo" if pa else "")
            e1, e2 = e1 - ph, e2 - pa
        else:
            st.info("Contexto IA no disponible ahora mismo. Se muestra la probabilidad base.")

    surface_avg_spw = {"hard": 0.62, "clay": 0.59, "grass": 0.66, "carpet": 0.63}[surface]
    prob_elo = expected_score(e1, e2)
    ps, _ = estimate_serve_return_from_elo(e1, e2, surface_avg_spw=surface_avg_spw)
    # p_set coherente con la prob. de partido del Elo por superficie (fiable),
    # para que los mercados por sets reflejen al favorito correcto.
    p_set = p_set_from_match(prob_elo, best_of=int(best_of))

    with st.spinner("Calculando probabilidades…"):
        markets = all_markets(p_set, best_of=int(best_of), name_a=p1_name, name_b=p2_name)
    partido = f"{p1_name} vs {p2_name} ({surface}, BO{best_of})"

    # Calibración del display de prob. de ganar (los mercados siguen sobre p_set crudo).
    cal_t = _binary_calibrator("tennis")
    tennis_calibrated = cal_t is not None
    if tennis_calibrated:
        prob_elo = cal_t.calibrate_home(prob_elo)

    st.markdown(f"### {partido}")
    
    matchup_header(p1_name, p2_name, "#b3985c", "179, 152, 92",
                   subtitle=f"Tenis · {str(surface).title()} · BO{best_of}")
    
    # Renderizamos las barras comparativas
    _render_comparison_bar(f"Rating ELO ({surface})", e1, e2, format_str="{:.0f}", color="#b3985c")
    _render_comparison_bar("Probabilidad de Ganar", prob_elo * 100, (1 - prob_elo) * 100, format_str="{:.1f}", suffix="%", color="#b3985c")
    if tennis_calibrated:
        st.caption("Probabilidad de ganar **calibrada** (isotónica sobre histórico).")
    
    section_header("Métricas del Modelo", "activity")
    c1, c2 = st.columns(2)
    c1.metric(f"Elo {p1_name.split()[-1]} ({surface})", f"{e1:.0f}")
    c2.metric(f"Elo {p2_name.split()[-1]} ({surface})", f"{e2:.0f}")
    st.caption(
        f"Prob. de ganar (Elo por superficie): **{p1_name} {prob_elo*100:.1f}%** · "
        f"{p2_name} {(1-prob_elo)*100:.1f}%. P(ganar un set) {p1_name} = {p_set*100:.1f}%. "
        f"SPW estimado {p1_name} = {ps*100:.0f}%."
    )

    _render_markets_section(markets, partido, charts.ACCENT["tennis"])

    st.caption(
        "Mercados por sets derivados de P(ganar un set) (Barnett-Clarke + Elo por "
        "superficie; la superficie ya está incluida). **Sin cuotas**. Sin splits finos de "
        "saque/resto ni fatiga del día; el total de games no se modela (no se inventa)."
    )

    st.divider()
    section_header("Detalle por jugador", "trending")
    _render_tennis_detail(p1_id, p1_name, p2_id, p2_name)


# ============================================================
#  BÉISBOL
# ============================================================

@st.cache_data(ttl=600)
def _all_mlb_elos() -> dict:
    from sports.baseball.elo import BaseballEloSystem
    df = pd.read_sql(
        """
        SELECT date, home_team_id, away_team_id, home_runs, away_runs
        FROM baseball_games
        WHERE home_runs IS NOT NULL AND away_runs IS NOT NULL
        ORDER BY date
        """,
        _engine(),
        parse_dates=["date"],
    )
    if df.empty:
        return {}
    elo = BaseballEloSystem()
    for _, r in df.iterrows():
        elo.process_game(
            r["date"], str(r["date"].year),
            int(r["home_team_id"]), int(r["away_team_id"]),
            int(r["home_runs"]), int(r["away_runs"]),
        )
    teams = set(df["home_team_id"]).union(set(df["away_team_id"]))
    return {int(t): float(elo.get(int(t))) for t in teams}


@st.cache_data(ttl=600)
def _mlb_team_pythag() -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT g.date, eh.name AS home, ea.name AS away,
               g.home_runs, g.away_runs,
               g.home_team_id, g.away_team_id
        FROM baseball_games g
        JOIN entities eh ON eh.id = g.home_team_id
        JOIN entities ea ON ea.id = g.away_team_id
        WHERE g.home_runs IS NOT NULL
        """,
        _engine(),
        parse_dates=["date"],
    )
    if df.empty:
        return df
    df["year"] = df["date"].dt.year
    last_year = df["year"].max()
    df = df[df["year"] == last_year]

    h = df[["home_team_id", "home", "home_runs", "away_runs"]].rename(
        columns={"home_team_id": "tid", "home": "team", "home_runs": "rs", "away_runs": "ra"}
    )
    a = df[["away_team_id", "away", "away_runs", "home_runs"]].rename(
        columns={"away_team_id": "tid", "away": "team", "away_runs": "rs", "home_runs": "ra"}
    )
    combined = pd.concat([h, a], ignore_index=True)
    return combined.groupby(["tid", "team"]).agg(
        RS=("rs", "sum"), RA=("ra", "sum"), G=("rs", "count")
    ).reset_index()


def show_baseball():
    st.subheader("Béisbol MLB")
    st.caption("Datos: 30 equipos MLB, temporadas 2018-2024 (Retrosheet, ~15.161 partidos).")

    teams = _entities("baseball")
    if teams.empty:
        st.error("No hay equipos MLB. Ejecuta `python scripts/download_retrosheet_data.py`")
        return

    col1, col2 = st.columns(2)
    home_name = col1.selectbox("Equipo local", teams["name"].tolist(), key="mlb_h")
    away_options = teams[teams["name"] != home_name]["name"].tolist()
    away_name = col2.selectbox("Equipo visitante", away_options, key="mlb_a")

    use_ai = _ai_checkbox("la MLB")

    if not st.button("Calcular probabilidades", type="primary", key="mlb_btn"):
        return

    from sports.baseball.elo import expected_home_score
    from sports.baseball.markets import all_markets

    home_id = int(teams[teams["name"] == home_name]["id"].iloc[0])
    away_id = int(teams[teams["name"] == away_name]["id"].iloc[0])

    elos = _all_mlb_elos()
    home_elo = elos.get(home_id, 1500.0)
    away_elo = elos.get(away_id, 1500.0)

    # Carreras esperadas a nivel equipo: ofensiva propia ajustada por la defensa
    # rival, relativa a la media de la liga (estilo Log5 para carreras).
    pyth_df = _mlb_team_pythag()
    league_rpg = (float(pyth_df["RS"].sum()) / float(pyth_df["G"].sum())
                  if (not pyth_df.empty and pyth_df["G"].sum() > 0) else 4.5)

    def _rates(tid):
        row = pyth_df[pyth_df["tid"] == tid]
        if row.empty or int(row["G"].iloc[0]) == 0:
            return league_rpg, league_rpg
        g = int(row["G"].iloc[0])
        return float(row["RS"].iloc[0]) / g, float(row["RA"].iloc[0]) / g

    h_rs, h_ra = _rates(home_id)
    a_rs, a_ra = _rates(away_id)
    e_home_runs = max(0.5, h_rs * a_ra / league_rpg * 1.03)   # leve ventaja local
    e_away_runs = max(0.5, a_rs * h_ra / league_rpg)

    if use_ai:
        ctx = _ai_context(home_name, away_name, "baseball")
        if ctx:
            mh = _adjust.runs_multiplier(ctx["home"]["impact"])
            ma = _adjust.runs_multiplier(ctx["away"]["impact"])
            _render_ai_context(home_name, away_name, ctx,
                               f"×{mh:.2f}" if mh != 1 else "", f"×{ma:.2f}" if ma != 1 else "")
            e_home_runs, e_away_runs = e_home_runs * mh, e_away_runs * ma
        else:
            st.info("Contexto IA no disponible ahora mismo. Se muestra la probabilidad base.")

    with st.spinner("Simulando 20.000 partidos (Monte Carlo)…"):
        markets = all_markets(e_home_runs, e_away_runs, rng=np.random.default_rng(42))
    partido = f"{home_name} vs {away_name}"

    st.markdown(f"### {home_name} (local) vs {away_name}")
    
    matchup_header(home_name, away_name, "#5f8fa8", "95, 143, 168",
                   subtitle="Béisbol · MLB")
    
    # Renderizamos las barras comparativas
    _render_comparison_bar("Rating ELO", home_elo, away_elo, format_str="{:.0f}", color="#5f8fa8")
    _render_comparison_bar("Carreras Esperadas", e_home_runs, e_away_runs, format_str="{:.2f}", color="#5f8fa8")
    
    section_header("Métricas del Modelo", "activity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Elo local", f"{home_elo:.0f}")
    c2.metric("Elo visitante", f"{away_elo:.0f}")
    c3.metric("Carreras esp. local", f"{e_home_runs:.2f}")
    c4.metric("Carreras esp. visit.", f"{e_away_runs:.2f}")

    _render_win_bar(markets, home_name, away_name, charts.ACCENT["baseball"], sport="baseball")
    _render_markets_section(markets, partido, charts.ACCENT["baseball"])

    st.caption(
        "Modelo a nivel equipo (carreras esperadas desde RS/RA, binomial negativa), "
        "**calibrado y sin cuotas**. En béisbol el ganador directo es casi un volado: el ML "
        "rara vez pasa de ~62%; el valor está en totales y run line. NO usa abridor, bullpen, "
        f"parque ni clima (no disponibles). (Elo: local {expected_home_score(home_elo, away_elo)*100:.0f}%.)"
    )

    st.divider()
    section_header("Detalle por equipo", "trending")
    t1, t2 = st.columns(2)
    _render_score_panel(t1, home_name, home_elo,
                        _recent_scores("baseball_games", "home_runs", "away_runs", home_id),
                        "Carreras a favor", "Carreras en contra", charts.ACCENT["baseball"])
    _render_score_panel(t2, away_name, away_elo,
                        _recent_scores("baseball_games", "home_runs", "away_runs", away_id),
                        "Carreras a favor", "Carreras en contra", charts.ACCENT["baseball"])


# ============================================================
#  Dispatcher
# ============================================================
if "Fútbol" in sport_label:
    show_football()
elif "Baloncesto" in sport_label:
    show_basketball()
elif "Béisbol" in sport_label:
    show_baseball()
elif "Tenis" in sport_label:
    show_tennis()
