from datetime import date, timedelta

import streamlit as st

from app import services as sv, ui
from app.ui import SPORTS
from core.predictions import top_situations

FEED_SPORTS = ["football", "baseball"]
DAYS = {"yesterday": "Ayer", "today": "Hoy", "tomorrow": "Mañana", "other": "Otra fecha"}
PER_ROW = 3


def _pick_day() -> date:
    c1, c2 = st.columns([1.4, 1], vertical_alignment="bottom")
    choice = c1.segmented_control("Día", list(DAYS), format_func=DAYS.get, default="today",
                                  key="fx_day", required=True, width="stretch")
    today = date.today()
    if choice == "other":
        return c2.date_input("Fecha", value=today, format="DD/MM/YYYY", key="fx_date")
    return today + timedelta(days={"yesterday": -1, "today": 0, "tomorrow": 1}[choice])


def _empty(sport: str, day: date) -> None:
    when = day.strftime("%d/%m/%Y")
    if sport == "football" and not sv.football_token():
        ui.empty_state("Agenda de fútbol sin configurar",
                       "Añade la clave gratuita football_data_token (football-data.org) en los "
                       "secretos para ver los partidos del día con sus probabilidades.", "calendar")
    elif sport == "football":
        ui.empty_state("Sin partidos de fútbol",
                       f"No hay partidos el {when} en las competiciones del plan gratuito. "
                       "Prueba con otra fecha.", "calendar")
    else:
        ui.empty_state("Sin partidos de MLB", f"No hay partidos programados el {when}.", "calendar")


@st.dialog("Análisis del partido", width="large")
def _match_dialog(sport: str, fx: dict, day: date) -> None:
    fc = sv.fixture_forecast(sport, fx, day)
    if fc is None:
        ui.empty_state("Sin datos del modelo", "Uno de los equipos no está en la base de datos.", "info")
        return
    hm, tzl = ui.local_hm(fx.get("time_utc"), ui.browser_tz())
    meta_left = " · ".join(x for x in (fx.get("league"), f"{hm} {tzl}".strip()) if x)
    ui.scorebug(fc, meta_left, fc.extras.get("method", "Modelo v2"),
                crests=(fx.get("home_logo", ""), fx.get("away_logo", "")))
    ui.notes(fc.notes, "warn")
    sits = top_situations(fc.markets, 10)
    ui.section("Las 10 situaciones más probables", "prob. · cuota justa")
    ui.situation_list(sits)
    logged = st.session_state.setdefault("_fx_logged", set())
    key = (sport, str(day), fx["home_id"], fx["away_id"])
    if sits and key not in logged:
        sv.log_situations(sport, day, fx, sits)
        logged.add(key)
    params = {"sport": sport, "home": str(fx["home_id"]), "away": str(fx["away_id"])}
    if sport == "football":
        params["league"] = fc.extras.get("league") or "__all__"
    st.space("small")
    if st.button("Abrir en el analizador", icon=":material/query_stats:", type="primary",
                 width="stretch", key="fx_open_an"):
        st.switch_page("views/analyzer.py", query_params=params)


def _groups(fixtures: list, sport: str) -> dict:
    out: dict = {}
    for i, f in enumerate(fixtures):
        out.setdefault(f.get("league") or SPORTS[sport]["short"], []).append((i, f))
    return out


def _card(sport: str, day: date, i: int, fx: dict, tz) -> None:
    fc = sv.fixture_forecast(sport, fx, day)
    hm, tzl = ui.local_hm(fx.get("time_utc"), tz)
    ui.fixture_card(fx, fc.win if fc else None, f"{hm} {tzl}".strip() or "—", ui.status_of(fx.get("status")))
    if fc is not None and st.button("Ver 10 situaciones", key=f"fx_{sport}_{day}_{i}",
                                    icon=":material/format_list_numbered:", type="tertiary",
                                    width="stretch"):
        _match_dialog(sport, fx, day)


ui.page_header("Partidos",
               "La agenda del día con la probabilidad de cada resultado según el modelo. "
               "Abre un partido para ver sus 10 situaciones más probables.", eyebrow="Agenda")

sport = st.segmented_control("Deporte", FEED_SPORTS, format_func=ui.sport_option,
                             default="football", key="fx_sport", required=True,
                             label_visibility="collapsed")
ui.set_accent(sport)
day = _pick_day()

with st.spinner("Cargando la agenda…"):
    fixtures = sv.fixtures(sport, day)
if not fixtures:
    _empty(sport, day)
    st.stop()

groups = _groups(fixtures, sport)
live = sum(1 for f in fixtures if ui.status_of(f.get("status"))[1] == "live")
no_data = sum(1 for f in fixtures if not (f.get("home_id") and f.get("away_id")))
chips = [ui.pill(f"{len(fixtures)} partidos", "accent"), ui.pill(f"{len(groups)} competiciones")]
if live:
    chips.append(ui.pill(f"{live} en vivo", "live"))
if no_data:
    chips.append(ui.pill(f"{no_data} sin datos del modelo", "warn"))
ui.chips(chips)

selected = list(groups)
if len(groups) > 1:
    picked = st.pills("Competición", list(groups), selection_mode="multi",
                      key=f"fx_leagues_{sport}_{day}", label_visibility="collapsed")
    selected = picked or list(groups)

tz = ui.browser_tz()
for league in selected:
    items = groups[league]
    ui.section(league, f"{len(items)} partido{'s' if len(items) != 1 else ''}")
    for start in range(0, len(items), PER_ROW):
        cols = st.columns(PER_ROW, gap="small")
        for col, (i, fx) in zip(cols, items[start:start + PER_ROW]):
            with col:
                _card(sport, day, i, fx, tz)

st.caption("Horas en tu zona horaria. «Sin datos del modelo»: algún equipo no está en la base "
           "(p. ej. ligas no cubiertas), así que no se estima.")
