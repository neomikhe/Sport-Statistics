"""
Gate de contraseña para el dashboard (acceso privado).

La contraseña se lee de st.secrets["app_password"] (en la nube) o de la variable
de entorno APP_PASSWORD (local). Si NO hay contraseña configurada, el acceso es
libre: asi `streamlit run` en local funciona sin friccion.

Seguridad:
  - Comparacion en tiempo constante (hmac.compare_digest) -> sin timing attacks.
  - Retardo ESCALANTE tras cada fallo -> ralentiza la fuerza bruta.
  - Sesion con CADUCIDAD por inactividad -> si dejas la pestaña abierta, expira.

Uso (en cada pagina, justo despues de st.set_page_config):
    from app.auth import require_password
    require_password()
"""
import hmac
import os
import time

import streamlit as st

_AUTH_KEY = "_sportstats_authed"
_AUTH_TS = "_sportstats_authed_at"
_FAILS = "_sportstats_fails"

SESSION_TTL_S = 120 * 60   # caduca la sesion tras 2 h de inactividad
MAX_FAIL_DELAY_S = 8       # tope del retardo anti-fuerza-bruta


def _configured_password() -> str | None:
    try:
        if "app_password" in st.secrets:
            return str(st.secrets["app_password"])
    except Exception:
        pass
    return os.getenv("APP_PASSWORD")


def require_password() -> None:
    """Bloquea la pagina hasta introducir la clave. Sesion con caducidad."""
    password = _configured_password()
    if not password:
        return  # sin clave configurada -> modo local sin friccion

    now = time.time()
    if st.session_state.get(_AUTH_KEY):
        if now - st.session_state.get(_AUTH_TS, 0) <= SESSION_TTL_S:
            st.session_state[_AUTH_TS] = now   # renueva por actividad
            return
        st.session_state[_AUTH_KEY] = False    # sesion caducada -> re-login

    _render_login_screen(password)
    st.stop()


def _render_login_screen(password: str) -> None:
    """Pantalla de login dedicada: centrada y sin la navegacion lateral visible."""
    st.markdown(
        "<style>[data-testid='stSidebar']{display:none;}</style>",
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 1.4, 1])
    with center:
        st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div style=\"display:flex;align-items:center;gap:11px;"
            "font-family:'IBM Plex Sans',system-ui,sans-serif;font-size:1.7rem;"
            "font-weight:600;color:#fff;\">"
            "<svg width='26' height='26' viewBox='0 0 24 24' fill='none' stroke='#5c9a85' "
            "stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round'>"
            "<rect width='18' height='11' x='3' y='11' rx='2' ry='2'/>"
            "<path d='M7 11V7a5 5 0 0 1 10 0v4'/></svg>"
            "<span>SportStatistics</span></div>",
            unsafe_allow_html=True,
        )
        st.caption("Acceso privado. Introduce la clave para continuar.")

        with st.form("login_form"):
            entered = st.text_input("Clave de acceso", type="password")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if submitted:
            if hmac.compare_digest(entered, password):
                st.session_state[_AUTH_KEY] = True
                st.session_state[_AUTH_TS] = time.time()
                st.session_state[_FAILS] = 0
                st.rerun()
            else:
                fails = st.session_state.get(_FAILS, 0) + 1
                st.session_state[_FAILS] = fails
                time.sleep(min(fails, MAX_FAIL_DELAY_S))  # retardo escalante
                st.error("Clave incorrecta.")
