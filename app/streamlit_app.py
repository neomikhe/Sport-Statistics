import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ASSETS = ROOT / "app" / "assets"
st.set_page_config(
    page_title="SportStatistics",
    page_icon=str(ASSETS / "favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

from app import ui  # noqa: E402
from app.auth import require_password  # noqa: E402

ui.inject_base_css()
require_password()

st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "logo_icon.svg"), size="large")

PAGES = [
    st.Page("views/home.py", title="Inicio", icon=":material/space_dashboard:",
            url_path="inicio", default=True),
    st.Page("views/fixtures.py", title="Partidos", icon=":material/event:", url_path="partidos"),
    st.Page("views/summary.py", title="Resumen", icon=":material/fact_check:", url_path="resumen"),
    st.Page("views/analyzer.py", title="Analizador", icon=":material/query_stats:",
            url_path="analizador"),
    st.Page("views/history.py", title="Rendimiento", icon=":material/verified:",
            url_path="rendimiento"),
    st.Page("views/picks.py", title="Valor", icon=":material/paid:", url_path="valor"),
]

st.navigation(PAGES, position="top").run()
ui.footer()
