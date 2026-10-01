import hmac
import os
import threading
import time

import streamlit as st

_AUTH_KEY = "_sportstats_authed"
_AUTH_TS = "_sportstats_authed_at"
_FAILS = "_sportstats_fails"

SESSION_TTL_S = 120 * 60
WINDOW_S = 600
MAX_FAILS = 5
MAX_TRACKED = 5000
LOCAL_ADDRESSES = {"127.0.0.1", "localhost", "::1"}


def _configured_password() -> str | None:
    try:
        if "app_password" in st.secrets:
            return str(st.secrets["app_password"]) or None
    except Exception:  # noqa: BLE001
        pass
    return os.getenv("APP_PASSWORD") or None


# Sin clave solo se entra si la app escucha únicamente en local.
def _is_local_only() -> bool:
    return str(st.get_option("server.address") or "") in LOCAL_ADDRESSES


_STORE = {"lock": threading.Lock(), "by_client": {}}


def _attempts() -> dict:
    return _STORE


def _client() -> str:
    try:
        ip = st.context.ip_address
    except Exception:  # noqa: BLE001
        ip = None
    return ip if isinstance(ip, str) and ip else "anon"


# Máximo MAX_FAILS fallos por cliente en WINDOW_S (ventana deslizante).
def _wait_seconds(client: str, now: float) -> float:
    store = _attempts()
    with store["lock"]:
        recent = [t for t in store["by_client"].get(client, []) if now - t < WINDOW_S]
        store["by_client"][client] = recent
        if len(recent) < MAX_FAILS:
            return 0.0
        return WINDOW_S - (now - recent[-MAX_FAILS])


def _record_failure(client: str, now: float) -> None:
    store = _attempts()
    with store["lock"]:
        if len(store["by_client"]) > MAX_TRACKED:
            store["by_client"].clear()
        store["by_client"].setdefault(client, []).append(now)


def _clear_failures(client: str) -> None:
    store = _attempts()
    with store["lock"]:
        store["by_client"].pop(client, None)


def _matches(entered: str, password: str) -> bool:
    return hmac.compare_digest(str(entered).encode("utf-8"), str(password).encode("utf-8"))


def require_password() -> None:
    password = _configured_password()
    if not password:
        if _is_local_only():
            return
        _render_blocked()
        st.stop()

    now = time.time()
    if st.session_state.get(_AUTH_KEY):
        if now - st.session_state.get(_AUTH_TS, 0) <= SESSION_TTL_S:
            st.session_state[_AUTH_TS] = now
            return
        st.session_state[_AUTH_KEY] = False

    _render_login_screen(password)
    st.stop()


_LOGIN_CSS = """
<style>
[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl']{display:none;}
[data-testid='stForm']{
  background:var(--surface) !important; border:1px solid var(--line-2) !important;
  border-radius:18px !important; padding:30px 28px 24px !important;
  box-shadow:0 30px 80px -30px rgba(0,0,0,.8) !important; position:relative; overflow:hidden;
}
[data-testid='stForm']::before{content:""; position:absolute; left:0; right:0; top:0; height:3px;
  background:linear-gradient(90deg, var(--volt), rgba(197,242,74,.15));}
.ss-login{text-align:center; margin:2px 0 18px;}
.ss-login .t{font:800 2.3rem/.95 var(--f-display); text-transform:uppercase; color:var(--text);
  letter-spacing:.02em; margin-top:14px;}
.ss-login .t span{color:var(--volt);}
.ss-login .d{color:var(--text-2); font-size:.92rem; line-height:1.5; margin-top:10px;}
.ss-login-err{display:flex; align-items:center; gap:7px; margin:2px 0 6px; color:#f3a2a4; font-size:.84rem;}
</style>
"""

_MARK = ("<svg width='44' height='36' viewBox='0 0 40 32' fill='none' aria-hidden='true'>"
         "<g transform='skewX(-12)'>"
         "<rect x='6' y='14' width='5' height='14' rx='1.5' fill='#c5f24a' opacity='.45'/>"
         "<rect x='14' y='8' width='5' height='20' rx='1.5' fill='#c5f24a' opacity='.72'/>"
         "<rect x='22' y='2' width='5' height='26' rx='1.5' fill='#c5f24a'/>"
         "<rect x='30' y='11' width='5' height='17' rx='1.5' fill='#c5f24a' opacity='.58'/>"
         "</g></svg>")

_ERR_ICON = ("<svg width='15' height='15' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
             "stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
             "<circle cx='12' cy='12' r='10'/><line x1='12' x2='12' y1='8' y2='12'/>"
             "<line x1='12' x2='12.01' y1='16' y2='16'/></svg>")


def _head(text: str) -> str:
    return (f"<div class='ss ss-login'>{_MARK}<div class='t'>Sport<span>Statistics</span></div>"
            f"<div class='d'>{text}</div></div>")


def _error(text: str) -> str:
    return f"<div class='ss-login-err' role='alert'>{_ERR_ICON}<span>{text}</span></div>"


def _render_blocked() -> None:
    st.html(_LOGIN_CSS)
    _, center, _ = st.columns([1, 1.25, 1])
    with center:
        st.space("large")
        with st.container(border=True):
            st.html(_head("Acceso no configurado. Define <b>app_password</b> en los secretos "
                          "(o la variable APP_PASSWORD). Para usarla sin clave en tu equipo, "
                          "arráncala con <code>--server.address 127.0.0.1</code>."))


def _render_login_screen(password: str) -> None:
    st.html(_LOGIN_CSS)
    client = _client()
    _, center, _ = st.columns([1, 1.25, 1])
    with center:
        st.space("large")
        with st.form("login_form"):
            st.html(_head("Acceso privado. Introduce la clave para continuar."))
            entered = st.text_input("Clave", type="password", placeholder="••••••••",
                                    max_chars=512)
            wait = _wait_seconds(client, time.time())
            if wait > 0:
                st.html(_error(f"Demasiados intentos. Espera {int(wait // 60) + 1} min."))
            elif st.session_state.get(_FAILS, 0) > 0:
                st.html(_error("Clave incorrecta"))
            submitted = st.form_submit_button("Entrar", type="primary", width="stretch",
                                              icon=":material/lock_open:")

        if not submitted or _wait_seconds(client, time.time()) > 0:
            return
        if _matches(entered, password):
            _clear_failures(client)
            st.session_state[_AUTH_KEY] = True
            st.session_state[_AUTH_TS] = time.time()
            st.session_state[_FAILS] = 0
        else:
            _record_failure(client, time.time())
            st.session_state[_FAILS] = st.session_state.get(_FAILS, 0) + 1
            time.sleep(1.0)
        st.rerun()
