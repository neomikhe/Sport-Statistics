"""
Tema visual + componentes del dashboard (rediseño MATE / formal).

Estética "sports-data terminal": fondo slate casi negro, superficies planas (sin
glassmorphism ni glows), acentos APAGADOS por deporte, tipografía IBM Plex Sans/Mono
(seria y técnica) e ICONOS SVG (Lucide) en vez de emojis.

El CSS es ESTÁTICO (no interpola datos de usuario) → sin riesgo XSS. Los componentes
(hero, cabecera H2H) SÍ escapan los nombres que vienen de la BD.
"""
import html

import streamlit as st

_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');

:root {
  --accent: __ACCENT__;
  --accent-rgb: __ACCENT_RGB__;
  --bg: #0a0d13;
  --card: #131923;
  --card-2: #1a2130;
  --border: rgba(255, 255, 255, 0.07);
  --text: #e6eaf0;
  --muted: #939eae;
}

/* ---------- Tipografía (IBM Plex: formal + técnica) ---------- */
html, body, .stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button, .stApp select {
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 600;
  letter-spacing: 0;
  color: #ffffff;
}
[data-testid="stMetricValue"], code, kbd, pre {
  font-family: 'IBM Plex Mono', monospace !important;
}
.stApp p, .stApp li { line-height: 1.65; color: var(--muted); }

/* ---------- Fondo mate (plano, mínimo degradado) ---------- */
.stApp {
  background:
    linear-gradient(180deg, rgba(__ACCENT_RGB__, 0.035), transparent 260px),
    var(--bg) !important;
  color: var(--text) !important;
}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
  background-color: #0c1017 !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  font-family: 'IBM Plex Sans', sans-serif !important;
  font-weight: 600 !important;
}

/* ---------- Métricas: tarjetas MATE (sin blur, sin glow, sin salto) ---------- */
[data-testid="stMetric"] {
  background: var(--card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  padding: 16px 18px !important;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25) !important;
  transition: border-color .2s ease, background-color .2s ease !important;
}
[data-testid="stMetric"]:hover {
  border-color: rgba(__ACCENT_RGB__, 0.45) !important;
  background: var(--card-2) !important;
}
[data-testid="stMetricLabel"] {
  color: var(--muted) !important;
  font-size: 0.72rem !important;
  font-weight: 500 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
}
[data-testid="stMetricValue"] {
  font-weight: 600 !important;
  color: #ffffff !important;
  font-size: 1.55rem !important;
}

/* ---------- Tablas ---------- */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  overflow: hidden !important;
}
div[data-testid="stTable"] table {
  background-color: var(--card) !important;
  border-radius: 12px !important;
  overflow: hidden !important;
  border: 1px solid var(--border) !important;
}
div[data-testid="stTable"] th {
  background-color: rgba(255, 255, 255, 0.025) !important;
  color: var(--muted) !important;
  font-weight: 600 !important;
  padding: 11px 15px !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
  text-transform: uppercase !important;
  font-size: .72rem !important;
  letter-spacing: .05em !important;
}
div[data-testid="stTable"] td {
  padding: 11px 15px !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04) !important;
  color: var(--text) !important;
}

/* ---------- Botones: mate (sin glow, sin transform) ---------- */
.stButton>button, [data-testid="stFormSubmitButton"] button {
  border-radius: 8px !important;
  font-weight: 600 !important;
  font-family: 'IBM Plex Sans', sans-serif !important;
  border: 1px solid rgba(__ACCENT_RGB__, 0.35) !important;
  background: rgba(__ACCENT_RGB__, 0.10) !important;
  color: var(--accent) !important;
  transition: background-color .2s ease, border-color .2s ease, color .2s ease !important;
  padding: 9px 18px !important;
}
.stButton>button:hover, [data-testid="stFormSubmitButton"] button:hover {
  background: rgba(__ACCENT_RGB__, 0.20) !important;
  border-color: var(--accent) !important;
  color: #ffffff !important;
}

/* ---------- Inputs ---------- */
input, textarea, select, div[data-baseweb="select"] {
  border-radius: 8px !important;
  border: 1px solid var(--border) !important;
  background: #0c1017 !important;
  color: #eef1f6 !important;
}
div[data-baseweb="select"] > div { background-color: #0c1017 !important; color: #eef1f6 !important; }
[data-testid="stNumberInput"] input { font-family: 'IBM Plex Mono', monospace !important; }

/* ---------- Alertas (mate) ---------- */
div[data-testid="stInfo"] {
  background-color: rgba(95, 143, 168, 0.10) !important;
  color: #a9c3d1 !important; border: 1px solid rgba(95, 143, 168, 0.22) !important; border-radius: 10px !important;
}
div[data-testid="stWarning"] {
  background-color: rgba(179, 152, 92, 0.10) !important;
  color: #d0bd8a !important; border: 1px solid rgba(179, 152, 92, 0.22) !important; border-radius: 10px !important;
}
div[data-testid="stSuccess"] {
  background-color: rgba(92, 154, 133, 0.10) !important;
  color: #96c3b2 !important; border: 1px solid rgba(92, 154, 133, 0.22) !important; border-radius: 10px !important;
}
div[data-testid="stError"] {
  background-color: rgba(176, 96, 96, 0.10) !important;
  color: #d19a9a !important; border: 1px solid rgba(176, 96, 96, 0.22) !important; border-radius: 10px !important;
}

/* ---------- Sliders ---------- */
.stSlider [data-testid="stSliderTickBar"] { background-color: rgba(255, 255, 255, 0.05) !important; }
.stSlider [role="slider"] { background-color: var(--accent) !important; border: 2px solid #0a0d13 !important; }

/* ---------- Chrome ---------- */
#MainMenu, [data-testid="stDecoration"] { visibility: hidden; }
footer { display: none; }

/* ---------- Scrollbars ---------- */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: rgba(10, 13, 19, 0.6); }
::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.08); border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

/* ---------- Expanders (mate) ---------- */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important; border-radius: 12px !important;
  background: var(--card) !important; overflow: hidden !important;
}
[data-testid="stExpander"] summary {
  font-family: 'IBM Plex Sans', sans-serif !important; font-weight: 600 !important;
  padding: 12px 16px !important; transition: color .2s ease !important;
}
[data-testid="stExpander"] summary:hover { color: var(--accent) !important; }

/* ---------- Radio como segmentos ---------- */
[data-testid="stRadio"] [role="radiogroup"] { gap: .4rem !important; }
[data-testid="stRadio"] [role="radiogroup"] > label {
  border: 1px solid var(--border) !important; border-radius: 8px !important;
  padding: 7px 12px !important; margin: 0 !important;
  transition: background-color .2s ease, border-color .2s ease !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:hover {
  border-color: rgba(__ACCENT_RGB__, 0.45) !important; background: rgba(__ACCENT_RGB__, 0.08) !important;
}

/* ---------- Tabs ---------- */
button[data-baseweb="tab"] { font-family: 'IBM Plex Sans', sans-serif !important; font-weight: 600 !important; }
[data-baseweb="tab-highlight"] { background: var(--accent) !important; }

/* ---------- Divisores ---------- */
hr { border: none !important; height: 1px !important; background: var(--border) !important; }

/* ---------- Dropdown de selects ---------- */
ul[role="listbox"] { background: #0c1017 !important; border: 1px solid var(--border) !important; border-radius: 10px !important; }
li[role="option"]:hover { background: rgba(__ACCENT_RGB__, 0.10) !important; }

/* ---------- Enlaces ---------- */
.stApp a { color: var(--accent) !important; text-decoration: none !important; }
.stApp a:hover { text-decoration: underline !important; }

/* ---------- Foco accesible (WCAG) ---------- */
:focus-visible { outline: 2px solid rgba(__ACCENT_RGB__, 0.55) !important; outline-offset: 2px !important; }

/* ---------- Encabezados de sección con icono SVG (componente section_header) ---------- */
.ss-sec {
  display: flex; align-items: center; gap: 9px; margin: 1.7rem 0 .75rem;
  font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; font-size: .95rem;
  color: #eef1f6; letter-spacing: .005em;
}
.ss-sec svg { color: var(--accent); flex: none; }

/* Markdown headers residuales: marcador de acento sobrio */
.stApp h3, .stApp h4 { border-left: 2px solid var(--accent) !important; padding-left: 11px !important; margin-top: 1.5rem !important; }

/* ===================== RESPONSIVE ===================== */
@media (max-width:640px){
  .block-container, [data-testid="stMainBlockContainer"]{ padding:1.2rem 1rem 3rem; }
  [data-testid="stHorizontalBlock"]{ flex-wrap:wrap; gap:.75rem; }
  [data-testid="stHorizontalBlock"] > div{ flex:1 1 100% !important; min-width:100% !important; }
  .stApp h1{ font-size:1.7rem; }
  [data-testid="stMetricValue"]{ font-size:1.3rem; }
}
@media (prefers-reduced-motion: reduce){ *{ transition:none !important; animation:none !important; } }
</style>
"""

# Paleta MATE por deporte (acentos apagados/terrosos, no vibrantes).
_THEMES = {
    "football":   {"accent": "#5c9a85", "rgb": "92, 154, 133"},
    "basketball": {"accent": "#bd8560", "rgb": "189, 133, 96"},
    "tennis":     {"accent": "#b3985c", "rgb": "179, 152, 92"},
    "baseball":   {"accent": "#5f8fa8", "rgb": "95, 143, 168"},
}


def _theme_key(sport: str) -> str:
    key = str(sport).lower()
    if any(w in key for w in ("futbol", "fútbol", "soccer", "football")):
        return "football"
    if any(w in key for w in ("baloncesto", "basket", "nba")):
        return "basketball"
    if any(w in key for w in ("tenis", "tennis")):
        return "tennis"
    if any(w in key for w in ("béisbol", "beisbol", "baseball", "mlb")):
        return "baseball"
    return "football"


def inject_theme(sport: str = "football") -> None:
    """Inyecta el tema mate dinámico según el deporte seleccionado."""
    t = _THEMES[_theme_key(sport)]
    css = (_THEME_CSS.replace("__ACCENT__", t["accent"])
                     .replace("__ACCENT_RGB__", t["rgb"]))
    st.markdown(css, unsafe_allow_html=True)


# ======================================================================
#  Iconos SVG (Lucide) — reemplazan a los emojis para dar formalidad
# ======================================================================
_ICONS = {
    "search":     '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "chart":      '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "trophy":     '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    "target":     '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "list":       '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
    "star":       '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "trending":   '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "sliders":    '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/>',
    "scale":      '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    "lock":       '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "activity":   '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "info":       '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "alert":      '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "medal":      '<path d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><path d="M11 12 5.44 2.63"/><path d="m13 12 5.56-9.37"/><path d="M8 7h8"/><circle cx="12" cy="17" r="5"/><path d="M12 18v-2h-.5"/>',
    "refresh":    '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "bot":        '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
    "check":      '<path d="M20 6 9 17l-5-5"/>',
}


def icon(name: str, size: int = 18, color: str = "currentColor", stroke: float = 1.75) -> str:
    """Devuelve el markup SVG de un icono Lucide (24x24). Uso inline en HTML."""
    inner = _ICONS.get(name, _ICONS["chart"])
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="vertical-align:middle;flex:none">{inner}</svg>')


def section_header(title: str, name: str = "chart") -> None:
    """Encabezado de sección: icono SVG de acento + título (sin emojis)."""
    st.markdown(
        f'<div class="ss-sec">{icon(name, 17, "var(--accent)")}'
        f'<span>{html.escape(str(title))}</span></div>',
        unsafe_allow_html=True,
    )


def render_hero(title: str, subtitle: str = "", badge: str = "") -> None:
    """Cabecera de marca para la portada (mate). Texto estático → se escapa igual."""
    badge_html = (
        f"<div style='display:inline-flex;align-items:center;gap:6px;margin-top:14px;"
        f"padding:5px 12px;border-radius:6px;background:rgba(var(--accent-rgb),0.10);"
        f"border:1px solid rgba(var(--accent-rgb),0.25);color:var(--accent);"
        f"font-family:IBM Plex Mono,monospace;font-size:12px;font-weight:500;'>"
        f"{icon('activity', 13, 'var(--accent)')}<span>{html.escape(str(badge))}</span></div>"
    ) if badge else ""
    st.markdown(
        f"""
        <div style="position:relative;overflow:hidden;border-radius:16px;padding:32px 28px;margin:2px 0 22px;
                    background:var(--card);border:1px solid var(--border);">
          <div style="position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--accent);"></div>
          <div style="font-family:'IBM Plex Sans',sans-serif;font-size:2.1rem;font-weight:600;
                      color:#fff;line-height:1.15;letter-spacing:-.01em;">{html.escape(str(title))}</div>
          <div style="margin-top:.5rem;color:var(--muted);font-size:1rem;max-width:640px;">
              {html.escape(str(subtitle))}</div>
          {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def matchup_header(home, away, accent: str = "#5c9a85",
                   accent_rgb: str = "92, 154, 133", subtitle: str = "") -> None:
    """Cabecera de enfrentamiento (H2H) mate. Nombres de BD → escapados (XSS-safe)."""
    sub = (
        f"<div style='position:relative;margin-top:12px;color:var(--muted);font-size:12px;"
        f"letter-spacing:.06em;text-transform:uppercase;'>{html.escape(str(subtitle))}</div>"
    ) if subtitle else ""
    st.markdown(
        f"""
        <div style="position:relative;overflow:hidden;border-radius:14px;padding:22px 20px;margin-bottom:20px;
                    text-align:center;background:var(--card);border:1px solid rgba({accent_rgb},0.18);">
          <div style="position:absolute;left:0;right:0;top:0;height:2px;background:rgba({accent_rgb},0.55);"></div>
          <div style="display:flex;justify-content:center;align-items:center;gap:12px;max-width:640px;margin:0 auto;">
            <div style="flex:1;text-align:right;"><span style="font-family:'IBM Plex Sans',sans-serif;
                 font-size:21px;font-weight:600;color:#fff;">{html.escape(str(home))}</span></div>
            <div style="font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:12px;letter-spacing:.05em;
                 background:rgba({accent_rgb},0.12);border:1px solid rgba({accent_rgb},0.30);color:{accent};
                 padding:5px 12px;border-radius:6px;">VS</div>
            <div style="flex:1;text-align:left;"><span style="font-family:'IBM Plex Sans',sans-serif;
                 font-size:21px;font-weight:600;color:#fff;">{html.escape(str(away))}</span></div>
          </div>
          {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )
