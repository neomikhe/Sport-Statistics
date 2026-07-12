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


_LOGIN_CSS = """
<style>
[data-testid='stSidebar']{display:none;}
[data-testid='stAppViewContainer']{
  background:
    radial-gradient(120% 80% at 50% 120%, rgba(92,154,133,0.06), transparent 60%),
    radial-gradient(circle at 50% 100%, rgba(255,255,255,0.025) 0.5px, transparent 0.6px) 0 0/22px 22px,
    #0a0d13 !important;
}
/* La tarjeta de login = el formulario */
[data-testid='stForm']{
  background:#131923 !important; border:1px solid rgba(255,255,255,0.08) !important;
  border-radius:16px !important; padding:30px 30px 26px !important;
  box-shadow:0 24px 70px rgba(0,0,0,0.45) !important;
}
[data-testid='stForm'] [data-testid='stTextInput'] label{
  text-transform:uppercase; letter-spacing:.08em; font-size:.7rem; color:var(--muted);
}
[data-testid='stFormSubmitButton'] button{
  background:rgba(92,154,133,0.14) !important; border:1px solid rgba(92,154,133,0.40) !important;
  color:#eafff4 !important; padding:11px 18px !important; margin-top:4px;
}
[data-testid='stFormSubmitButton'] button:hover{
  background:rgba(92,154,133,0.24) !important; border-color:#5c9a85 !important;
}
</style>
"""

_LOGIN_ERROR = (
    "<div style='display:flex;align-items:center;gap:7px;margin:2px 0 6px;color:#d98c8c;"
    "font-size:.82rem;'>"
    "<svg width='15' height='15' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
    "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' style='flex:none'>"
    "<circle cx='12' cy='12' r='10'/><line x1='12' x2='12' y1='8' y2='12'/>"
    "<line x1='12' x2='12.01' y1='16' y2='16'/></svg>"
    "<span>Clave incorrecta</span></div>"
)


def _render_login_screen(password: str) -> None:
    """Pantalla de login dedicada: tarjeta centrada, con marca (mockup)."""
    from app.ui import brand_logo

    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 1.3, 1])
    with center:
        st.markdown("<div style='height:11vh'></div>", unsafe_allow_html=True)
        with st.form("login_form"):
            st.markdown(
                f"<div style='display:flex;justify-content:center;margin:2px 0 18px;'>"
                f"{brand_logo(scale=1.6, stacked=True)}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<div style='text-align:center;color:var(--muted);font-size:.92rem;"
                "line-height:1.5;margin-bottom:20px;'>Acceso privado. Introduce la clave "
                "para continuar.</div>",
                unsafe_allow_html=True,
            )
            entered = st.text_input("Clave", type="password",
                                    placeholder="••••••••", label_visibility="visible")
            if st.session_state.get(_FAILS, 0) > 0:
                st.markdown(_LOGIN_ERROR, unsafe_allow_html=True)
            submitted = st.form_submit_button("Entrar", type="primary",
                                              width="stretch")

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
                st.rerun()
