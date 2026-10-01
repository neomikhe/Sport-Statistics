from datetime import date

import pandas as pd
import streamlit as st

from app import charts, services as sv, ui
from app.ui import AWAY_COLOR, SPORTS
from core.markets import premium_picks
from core.predictions import top_situations

ALL_LEAGUES = "__all__"
SURFACES = {"hard": "Dura", "clay": "Tierra", "grass": "Hierba"}


# Enlace profundo (?sport=&home=&away=&league=); se valida antes de usarse.
def _apply_query_params() -> None:
    qp = st.query_params
    sig = tuple(sorted((k, qp.get(k)) for k in ("sport", "home", "away", "league")))
    if st.session_state.get("_an_qp") == sig:
        return
    st.session_state["_an_qp"] = sig
    sport = qp.get("sport")
    if sport in SPORTS:
        st.session_state["an_sport"] = sport
        if sport == "football" and qp.get("league"):
            st.session_state["an_football_league"] = qp.get("league")
        for side in ("home", "away"):
            v = qp.get(side)
            if v and str(v).isdigit():
                st.session_state[f"an_{sport}_{side}"] = int(v)


def _swap(sport: str) -> None:
    kh, ka = f"an_{sport}_home", f"an_{sport}_away"
    st.session_state[kh], st.session_state[ka] = st.session_state.get(ka), st.session_state.get(kh)


def _strength(sport: str, model, tid: int) -> float:
    if model is None:
        return 0.0
    if sport == "tennis":
        return model.rating(tid)
    return float(model.team_state(tid).get("elo", 1500.0))


def _ensure_pair(sport: str, ids: list) -> None:
    kh, ka = f"an_{sport}_home", f"an_{sport}_away"
    if st.session_state.get(kh) in ids and st.session_state.get(ka) in ids:
        return
    model = sv.model(sport)
    ranked = sorted(ids, key=lambda t: _strength(sport, model, t), reverse=True)
    if st.session_state.get(kh) not in ids:
        st.session_state[kh] = ranked[0]
    if st.session_state.get(ka) not in ids or st.session_state[ka] == st.session_state[kh]:
        st.session_state[ka] = next(t for t in ranked if t != st.session_state[kh])


def _options(sport: str) -> tuple:
    league = None
    if sport == "football":
        leagues = sv.football_leagues()
        opts = [ALL_LEAGUES] + leagues
        if st.session_state.get("an_football_league") not in opts:
            st.session_state["an_football_league"] = leagues[0] if leagues else ALL_LEAGUES
        league = st.selectbox("Liga", opts, key="an_football_league",
                              format_func=lambda x: "Todas las ligas" if x == ALL_LEAGUES else x)
        df = sv.entities("football") if league == ALL_LEAGUES else sv.league_teams(league)
        league = None if league == ALL_LEAGUES else league
    elif sport == "tennis":
        tour = st.segmented_control("Circuito", ["ATP", "WTA"], default="ATP", key="an_tn_tour",
                                    required=True)
        df = sv.tennis_players(tour)
    else:
        df = sv.entities(sport)
    if df.empty:
        return [], {}, league
    names = dict(zip(df["id"].astype(int), df["name"].astype(str)))
    return list(names), names, league


def _selection(sport: str) -> dict | None:
    meta = SPORTS[sport]
    tennis = sport == "tennis"
    with st.container(border=True, key="an_form"):
        ids, names, league = _options(sport)
        if len(ids) < 2:
            ui.empty_state("Sin datos para este deporte",
                           "La base no tiene equipos o jugadores suficientes todavía.", "database")
            return None
        _ensure_pair(sport, ids)
        left, mid, right = st.columns([1, 0.16, 1], vertical_alignment="bottom")
        role_h, role_a = ("Jugador 1", "Jugador 2") if tennis else ("Local", "Visitante")
        fmt = names.get
        home = left.selectbox(f"{meta['entity']} · {role_h}", ids, key=f"an_{sport}_home",
                              format_func=fmt)
        mid.button(":material/swap_horiz:", key=f"an_{sport}_swap", on_click=_swap, args=(sport,),
                   help="Intercambiar", width="stretch")
        away = right.selectbox(f"{meta['entity']} · {role_a}", ids, key=f"an_{sport}_away",
                               format_func=fmt)
        choice = {"home": home, "away": away, "home_name": names[home], "away_name": names[away],
                  "league": league, "roles": (role_h, role_a)}
        if tennis:
            c1, c2 = st.columns(2)
            choice["surface"] = c1.segmented_control(
                "Superficie", list(SURFACES), format_func=SURFACES.get, default="hard",
                key="an_tn_surface", required=True, width="stretch")
            choice["best_of"] = 3
            if st.session_state.get("an_tn_tour", "ATP") == "ATP":
                choice["best_of"] = c2.segmented_control(
                    "Formato", [3, 5], format_func=lambda b: f"Al mejor de {b}", default=3,
                    key="an_tn_bo", required=True, width="stretch")
        choice["ai"] = sv.ai_enabled() and st.toggle(
            "Ajustar por bajas y lesiones (IA con búsqueda web)", key=f"an_{sport}_ai",
            help="Consulta el contexto actual y ajusta la fuerza de cada lado. "
                 "La probabilidad la sigue calculando el modelo.")
    return choice


_IMPACT = {"none": "Sin bajas relevantes", "low": "Bajas menores", "medium": "Bajas relevantes",
           "high": "Baja clave", "unknown": "Sin datos fiables"}


def _ai_adjust(sport: str, c: dict) -> tuple:
    from core.ai import adjust
    ctx = sv.ai_context(c["home_name"], c["away_name"], sport, c.get("league") or "")
    if not ctx:
        return None, {}
    hi, ai = ctx["home"]["impact"], ctx["away"]["impact"]
    if sport == "tennis":
        return ctx, {"elo_penalty": (adjust.elo_penalty(hi), adjust.elo_penalty(ai))}
    fn = {"football": adjust.lambda_multiplier, "basketball": adjust.points_multiplier,
          "baseball": adjust.runs_multiplier}[sport]
    return ctx, {"mult": (fn(hi), fn(ai))}


def _render_ai(ctx: dict, c: dict) -> None:
    ui.section("Contexto actual", "IA con búsqueda web · puede contener errores")
    cols = st.columns(2)
    for col, side, name in ((cols[0], "home", c["home_name"]), (cols[1], "away", c["away_name"])):
        d = ctx[side]
        tone = {"high": "bad", "medium": "warn"}.get(d["impact"], "info")
        body = "; ".join(d["absences"]) or "Sin bajas reportadas."
        if d.get("note"):
            body += f" — {d['note']}"
        with col:
            ui.render(ui.notice(body, tone, f"{name}: {_IMPACT.get(d['impact'], 'Sin datos fiables')}."))


def _tab_summary(fc) -> None:
    top = top_situations(fc.markets, 10)
    ui.section("Las 10 situaciones más probables", "prob. del modelo · cuota justa")
    ui.situation_list(top)
    prem = [m for m in premium_picks(fc.markets) if not m.get("aprox")][:10]
    ui.section("Alta probabilidad (70–99 %)")
    if prem:
        ui.chips([ui.pill(f"{ui.cap(m['mercado'])} · {ui.fmt_pct(m['prob'])}", "accent") for m in prem])
    else:
        ui.render(ui.notice("Ningún mercado cae entre 70 % y 99 %: enfrentamiento parejo, "
                            "no se fuerzan selecciones."))


def _tab_markets(fc) -> None:
    q = st.text_input("Buscar mercado", placeholder="Ej.: Over, hándicap, córners…",
                      key=f"an_q_{fc.sport}", label_visibility="collapsed")
    n = ui.market_groups(fc.markets, q)
    st.caption(f"{n} mercados · todos salen de la misma distribución del partido "
               "(coherentes entre sí). «aprox.» = aproximación (mitades, F5).")


def _tab_distribution(fc) -> None:
    if fc.sport == "football":
        from sports.football.markets import top_scorelines
        ui.section("Mapa de marcadores", "probabilidad de cada resultado exacto")
        charts.score_heatmap(fc.extras["matrix"], fc.home, fc.away, key="an_heat")
        top = top_scorelines(fc.expected["home"], fc.expected["away"], rho=fc.extras["rho"], n=8)
        ui.table([("Marcador", ""), ("Probabilidad", "num"), ("Cuota justa", "num")],
                 [[ui.esc(f"{h} – {a}"), ui.fmt_pct(p, 2), ui.fmt_odds(p)] for h, a, p in top],
                 caption="Marcadores más probables")
    elif fc.sport == "basketball":
        ui.section("Distribución del margen", f"σ ≈ {fc.extras['sigma_margin']:.1f} puntos")
        charts.margin_normal(fc.expected["margin"], fc.extras["sigma_margin"], fc.home, fc.away,
                             "basketball", key="an_margin")
    elif fc.sport == "baseball":
        from sports.baseball.markets import run_matrix
        m = run_matrix(fc.expected["home"], fc.expected["away"], fc.extras["dispersion_r"])
        pmf = {}
        for h in range(m.shape[0]):
            for a in range(m.shape[1]):
                d = max(-8, min(8, h - a))
                pmf[d] = pmf.get(d, 0.0) + float(m[h, a])
        ui.section("Diferencia de carreras", "0 = empate tras 9 entradas (se decide en extras)")
        charts.diff_bars(pmf, fc.home, fc.away, "baseball", key="an_diff")
    else:
        from sports.tennis.markets import set_score_distribution
        dist = set_score_distribution(fc.extras["p_set"], fc.extras["best_of"])
        ui.section("Marcador por sets")
        charts.set_scores(dist, fc.home, fc.away, key="an_sets")


def _team_stats(sport: str, st_: dict) -> list:
    if sport == "football":
        out = [("Elo", f"{st_['elo']:.0f}"),
               ("Goles a favor · últ. 5", ui.fmt_num(st_.get("gf_5"), 1)),
               ("Goles en contra · últ. 5", ui.fmt_num(st_.get("ga_5"), 1))]
        if "dc_attack" in st_:
            out += [("Ataque vs liga", f"×{st_['dc_attack']:.2f}"),
                    ("Defensa vs liga", f"×{st_['dc_defense']:.2f}")]
        return out
    if sport == "basketball":
        return [("Elo", f"{st_['elo']:.0f}"), ("Ataque /100", f"{st_['ortg']:.1f}"),
                ("Defensa /100", f"{st_['drtg']:.1f}"), ("Neto", f"{st_['net']:+.1f}"),
                ("Ritmo", f"{st_['pace']:.1f}")]
    if sport == "baseball":
        return [("Elo", f"{st_['elo']:.0f}"), ("Carreras anotadas", f"{st_['rs']:.2f}"),
                ("Carreras permitidas", f"{st_['ra']:.2f}"), ("Estadio", f"×{st_['park']:.2f}")]
    surf = {SURFACES.get(k, k): v for k, v in st_.get("surfaces", {}).items()}
    return ([("Elo general", f"{st_['elo']:.0f}")]
            + [(f"Elo {k.lower()}", f"{v:.0f}") for k, v in surf.items()]
            + [("Partidos", f"{st_['matches']}")])


def _team_panel(fc, side: str, tid: int, color: str) -> None:
    name = fc.home if side == "home" else fc.away
    state = fc.ratings[side]
    if fc.sport == "tennis":
        rec = sv.tennis_recent(tid, 10)
        form = rec["res"].tolist()[:5] if not rec.empty else []
        ui.team_card(name, color, _team_stats("tennis", state), form)
        if not rec.empty:
            ui.table([("Fecha", ""), ("Torneo", ""), ("Rival", ""), ("Marcador", ""), ("", "")],
                     [[r.date.strftime("%d/%m/%y"), ui.esc(f"{r.tournament} · {r.round}"),
                       ui.esc(r.rival), ui.esc(r.score or ""), ui.result_pill(r.res == "G")]
                      for r in rec.itertuples()], lead=2)
        return
    rec = sv.recent_games(fc.sport, tid, 10)
    form = rec["res"].tolist()[::-1][:5] if not rec.empty else []
    ui.team_card(name, color, _team_stats(fc.sport, state), form)
    if rec.empty:
        return
    unit = SPORTS[fc.sport]["unit"]
    charts.team_trend(rec["date"].dt.strftime("%d/%m").tolist(), rec["f"].tolist(), rec["c"].tolist(),
                      f"{unit.capitalize()} a favor", f"{unit.capitalize()} en contra",
                      charts.accent(fc.sport) if side == "home" else AWAY_COLOR,
                      key=f"an_trend_{side}")
    rows = [[r.date.strftime("%d/%m/%y"), ui.esc(f"{'vs' if r.loc == 'L' else '@'} {r.rival}"),
             ui.esc(f"{r.f}–{r.c}"), ui.form_chips([r.res])]
            for r in rec.iloc[::-1].head(6).itertuples()]
    ui.table([("Fecha", ""), ("Rival", ""), ("Marcador", "num"), ("", "num")], rows, lead=1)


def _tab_teams(fc, c: dict) -> None:
    h, a = fc.ratings["home"], fc.ratings["away"]
    if fc.sport == "basketball":
        rows = [("Ataque /100", h["ortg"], a["ortg"], lambda v: f"{v:.1f}", True),
                ("Defensa /100", h["drtg"], a["drtg"], lambda v: f"{v:.1f}", False),
                ("Ritmo", h["pace"], a["pace"], lambda v: f"{v:.1f}", True),
                ("Elo", h["elo"], a["elo"], lambda v: f"{v:.0f}", True)]
    elif fc.sport == "baseball":
        rows = [("Carreras anotadas", h["rs"], a["rs"], lambda v: f"{v:.2f}", True),
                ("Carreras permitidas", h["ra"], a["ra"], lambda v: f"{v:.2f}", False),
                ("Elo", h["elo"], a["elo"], lambda v: f"{v:.0f}", True)]
    elif fc.sport == "tennis":
        s = fc.extras["surface"]
        rows = [("Elo general", h["elo"], a["elo"], lambda v: f"{v:.0f}", True),
                (f"Elo {SURFACES.get(s, s).lower()}", h["surfaces"].get(s, 1500.0),
                 a["surfaces"].get(s, 1500.0), lambda v: f"{v:.0f}", True),
                ("Partidos en la base", h["matches"], a["matches"], lambda v: f"{v:.0f}", True)]
    else:
        rows = [("Elo", h["elo"], a["elo"], lambda v: f"{v:.0f}", True),
                ("Goles esperados", fc.expected["home"], fc.expected["away"], lambda v: f"{v:.2f}", True),
                ("Puntos últ. 5", h.get("form_5", 0), a.get("form_5", 0), lambda v: f"{v:.0f}", True)]
    ui.compare_rows(rows)
    st.space("small")
    col_h, col_a = st.columns(2, gap="medium")
    with col_h:
        _team_panel(fc, "home", c["home"], "var(--accent)")
    with col_a:
        _team_panel(fc, "away", c["away"], AWAY_COLOR)


def _tab_odds(fc, c: dict) -> None:
    from core.betting.ev import expected_value
    from core.betting.kelly import kelly_fractional

    outcomes = [("home", fc.home), ("draw", "Empate"), ("away", fc.away)]
    outcomes = [(k, n) for k, n in outcomes if fc.win.get(k) is not None]
    st.caption("Introduce cuotas decimales (idealmente de cierre). El modelo NO las usa para "
               "predecir: solo mide cuánto discrepa del mercado. Por defecto: cuota justa −5 %.")
    cols = st.columns(len(outcomes))
    odds = {}
    for col, (k, n) in zip(cols, outcomes):
        fair = 1.0 / max(fc.win[k], 1e-6)
        odds[k] = col.number_input(f"Cuota {n[:18]}", min_value=1.01, max_value=500.0,
                                   value=round(min(max(fair * 0.95, 1.01), 500.0), 2), step=0.05,
                                   key=f"an_odds_{fc.sport}_{c['home']}_{c['away']}_{k}")
    inv = {k: 1.0 / o for k, o in odds.items()}
    margin = sum(inv.values()) - 1.0
    rows = []
    for k, n in outcomes:
        pm, mk = fc.win[k], inv[k] / sum(inv.values())
        ev = expected_value(pm, odds[k])
        kelly = min(kelly_fractional(pm, odds[k], 0.25), 0.05)
        tone = "good" if ev > 0 else "neutral"
        rows.append([ui.esc(n), ui.fmt_pct(pm), ui.fmt_pct(mk), f"{(pm - mk) * 100:+.1f} pp",
                     ui.pill(f"{ev * 100:+.1f}%", tone), ui.fmt_pct(kelly)])
    ui.table([("Resultado", ""), ("Modelo", "num"), ("Mercado", "num"), ("Diferencia", "num"),
              ("Valor esperado", "num"), ("Kelly ¼", "num")], rows)
    ui.render(ui.notice(
        f"Margen de la casa en estas cuotas: {margin * 100:.1f} %. Medido fuera de muestra en "
        "fútbol, la cuota de cierre es más precisa que el modelo y apostar sus «ventajas» perdió "
        "dinero: cuando discrepan, suele acertar el mercado. Úsalo como termómetro, no como señal.",
        "warn", "Con escepticismo."))


_apply_query_params()
ui.page_header("Analizador",
               "Elige deporte y enfrentamiento: el modelo calcula al instante la probabilidad "
               "de cada mercado y su cuota justa.", eyebrow="Pronóstico a medida")

if "an_sport" not in st.session_state:
    st.session_state["an_sport"] = "football"
sport = st.segmented_control("Deporte", list(SPORTS), format_func=ui.sport_option,
                             key="an_sport", required=True, width="stretch",
                             label_visibility="collapsed")
ui.set_accent(sport)

if not sv.db_ok():
    ui.empty_state("Base de datos no disponible",
                   "No se pudo conectar con la base de datos. Revisa la conexión o los secretos.",
                   "database")
    st.stop()

choice = _selection(sport)
if choice is None:
    st.stop()
if choice["home"] == choice["away"]:
    ui.render(ui.notice("Elige dos contendientes distintos.", "warn"))
    st.stop()

ctx, adj = (None, {})
if choice.get("ai"):
    ctx, adj = _ai_adjust(sport, choice)
fc = sv.forecast(sport, choice["home"], choice["away"], choice["home_name"], choice["away_name"],
                 league=choice.get("league"), surface=choice.get("surface", "hard"),
                 best_of=int(choice.get("best_of") or 3), game_date=date.today(), **adj)
if fc is None:
    ui.empty_state("Modelo no disponible",
                   "Falta el modelo entrenado o no hay datos suficientes para este deporte.", "alert")
    st.stop()

if sport == "tennis":
    left = f"Tenis · {SURFACES.get(fc.extras['surface'], '')} · al mejor de {fc.extras['best_of']}"
else:
    left = f"{SPORTS[sport]['label']} · {choice.get('league') or fc.extras.get('league') or SPORTS[sport]['short']}"
right = fc.extras.get("method", "Modelo v2")
ui.scorebug(fc, left, right, roles=choice["roles"])
ui.notes(fc.notes, "warn")
if choice.get("ai"):
    if ctx:
        _render_ai(ctx, choice)
    else:
        ui.render(ui.notice("Contexto IA no disponible ahora mismo (sin datos fiables o límite de "
                            "la API). Se muestra la probabilidad base del modelo."))

st.space("small")
labels = ["Resumen", "Mercados", "Sets" if sport == "tennis" else "Marcador",
          "Jugadores" if sport == "tennis" else "Equipos", "Cuotas"]
t_sum, t_mk, t_dist, t_team, t_odds = st.tabs(labels, key="an_tabs", on_change="rerun")
if t_sum.open:
    with t_sum:
        _tab_summary(fc)
if t_mk.open:
    with t_mk:
        _tab_markets(fc)
if t_dist.open:
    with t_dist:
        _tab_distribution(fc)
if t_team.open:
    with t_team:
        _tab_teams(fc, choice)
if t_odds.open:
    with t_odds:
        _tab_odds(fc, choice)

data_note = pd.Timestamp(fc.extras["data_until"]).strftime("%d/%m/%Y") if fc.extras.get("data_until") else None
st.caption("Probabilidades del modelo, sin cuotas. Un favorito del 75 % pierde 1 de cada 4 veces."
           + (f" Datos hasta el {data_note}." if data_note else ""))
