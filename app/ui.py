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
  --accent: #5c9a85;            /* default (fútbol); inject_theme lo sobreescribe */
  --accent-rgb: 92, 154, 133;
  --bg: #0a0d13;
  --card: #131923;
  --card-2: #1a2130;
  --border: rgba(255, 255, 255, 0.07);
  --text: #e6eaf0;
  --muted: #a4b0c2;             /* gris de soporte (contraste ~8:1 sobre el fondo) */
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
    linear-gradient(180deg, rgba(var(--accent-rgb), 0.035), transparent 260px),
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
  border-color: rgba(var(--accent-rgb), 0.45) !important;
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
  border: 1px solid rgba(var(--accent-rgb), 0.35) !important;
  background: rgba(var(--accent-rgb), 0.10) !important;
  color: var(--accent) !important;
  transition: background-color .2s ease, border-color .2s ease, color .2s ease !important;
  padding: 9px 18px !important;
}
.stButton>button:hover, [data-testid="stFormSubmitButton"] button:hover {
  background: rgba(var(--accent-rgb), 0.20) !important;
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
/* Oculta el nav automático ("streamlit app"); usamos uno de marca (sidebar_nav). */
[data-testid="stSidebarNav"] { display: none; }

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
  border-color: rgba(var(--accent-rgb), 0.45) !important; background: rgba(var(--accent-rgb), 0.08) !important;
}

/* ---------- Tabs ---------- */
button[data-baseweb="tab"] { font-family: 'IBM Plex Sans', sans-serif !important; font-weight: 600 !important; }
[data-baseweb="tab-highlight"] { background: var(--accent) !important; }

/* ---------- Divisores ---------- */
hr { border: none !important; height: 1px !important; background: var(--border) !important; }

/* ---------- Dropdown de selects ---------- */
ul[role="listbox"] { background: #0c1017 !important; border: 1px solid var(--border) !important; border-radius: 10px !important; }
li[role="option"]:hover { background: rgba(var(--accent-rgb), 0.10) !important; }

/* ---------- Enlaces ---------- */
.stApp a { color: var(--accent) !important; text-decoration: none !important; }
.stApp a:hover { text-decoration: underline !important; }

/* ---------- Foco accesible (WCAG) — consistente en todos los controles ---------- */
:focus-visible { outline: 2px solid var(--accent) !important; outline-offset: 3px !important; }
.stButton>button:focus-visible, [data-testid="stFormSubmitButton"] button:focus-visible,
input:focus-visible, textarea:focus-visible, select:focus-visible,
[role="option"]:focus-visible, [data-baseweb="select"]:focus-within {
  outline: 2px solid var(--accent) !important; outline-offset: 3px !important;
}

/* ---------- Encabezados de sección con icono SVG (componente section_header) ---------- */
.ss-sec {
  display: flex; align-items: center; gap: 9px; margin: 1.7rem 0 .75rem;
  font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; font-size: .95rem;
  color: #eef1f6; letter-spacing: .005em;
}
.ss-sec svg { color: var(--accent); flex: none; }

/* Markdown headers residuales: marcador de acento sobrio */
.stApp h3, .stApp h4 { border-left: 2px solid var(--accent) !important; padding-left: 11px !important; margin-top: 1.5rem !important; }

/* ---------- Skeletons (carga percibida) ---------- */
@keyframes ss-shimmer { 0%{background-position:-400px 0} 100%{background-position:400px 0} }
.ss-skel {
  background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.09) 37%,
             rgba(255,255,255,0.04) 63%);
  background-size: 800px 100%; animation: ss-shimmer 1.4s infinite linear; border-radius: 6px;
}

/* ===================== RESPONSIVE ===================== */
@media (max-width:640px){
  .block-container, [data-testid="stMainBlockContainer"]{ padding:1.2rem 1rem 3rem; }
  [data-testid="stHorizontalBlock"]{ flex-wrap:wrap; gap:.75rem; }
  [data-testid="stHorizontalBlock"] > div{ flex:1 1 100% !important; min-width:100% !important; }
  .stApp h1{ font-size:1.7rem; }
  [data-testid="stMetricValue"]{ font-size:1.3rem; }
  /* Cabecera de página compacta en móvil (recupera área útil). */
  .ss-ph{ margin:2px 0 10px !important; gap:10px !important; }
  .ss-ph-ico{ width:34px !important; height:34px !important; }
  .ss-ph-ico svg{ width:18px !important; height:18px !important; }
  .ss-ph-title{ font-size:1.2rem !important; }
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
    """Inyecta el tema mate. El bloque grande de CSS es ESTÁTICO (usa var(--accent)),
    y solo se sobreescribe el ACENTO por deporte con un override minúsculo. Así, al
    alternar deportes, el navegador no re-parsea toda la hoja de estilos: cambia dos
    variables CSS y repinta al instante -> sin flicker/CLS (Layout Shift)."""
    t = _THEMES[_theme_key(sport)]
    st.markdown(_THEME_CSS, unsafe_allow_html=True)
    st.markdown(
        f"<style>:root{{--accent:{t['accent']};--accent-rgb:{t['rgb']};}}</style>",
        unsafe_allow_html=True,
    )


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
    "calendar":   '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    "clock":      '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "percent":    '<line x1="19" x2="5" y1="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    "coins":      '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>',
    "layout":     '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    "x":          '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
}

# Colores de estado (mate): positivo / negativo / neutro. (rgb, texto)
_PILL_COLORS = {
    "pos":     ("92, 154, 133", "#96c3b2"),
    "neg":     ("176, 96, 96", "#d99a9a"),
    "neutral": ("147, 158, 174", "#c2cad6"),
    "accent":  ("var(--accent-rgb)", "var(--accent)"),
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


# ======================================================================
#  Marca + componentes del sistema visual (mockups)
# ======================================================================
def brand_logo(scale: float = 1.0, stacked: bool = False,
               color: str = "var(--accent)") -> str:
    """Wordmark de marca: marca SVG (barras inclinadas tipo ecualizador) + 'SPORT STATISTICS'.

    Devuelve HTML (para inyectar). `stacked` apila SPORT sobre STATISTICS (login/sidebar).
    """
    mh = 30 * scale
    mark = (
        f"<svg width='{mh * 1.25:.0f}' height='{mh:.0f}' viewBox='0 0 40 32' fill='none' "
        f"style='flex:none'><g transform='skewX(-12)'>"
        f"<rect x='3'  y='14' width='5' height='14' rx='1.5' fill='{color}' opacity='.45'/>"
        f"<rect x='11' y='8'  width='5' height='20' rx='1.5' fill='{color}' opacity='.72'/>"
        f"<rect x='19' y='2'  width='5' height='26' rx='1.5' fill='{color}'/>"
        f"<rect x='27' y='11' width='5' height='17' rx='1.5' fill='{color}' opacity='.58'/>"
        f"</g></svg>"
    )
    fs = 1.1 * scale
    if stacked:
        word = (
            "<div style='display:flex;flex-direction:column;line-height:1;'>"
            f"<span style=\"font-family:'IBM Plex Sans',sans-serif;font-weight:600;color:#fff;"
            f"font-size:{fs:.2f}rem;letter-spacing:.16em;\">SPORT</span>"
            f"<span style=\"font-family:'IBM Plex Sans',sans-serif;font-weight:400;color:var(--muted);"
            f"font-size:{fs * 0.9:.2f}rem;letter-spacing:.22em;margin-top:3px;\">STATISTICS</span></div>"
        )
    else:
        word = (
            f"<span style=\"font-family:'IBM Plex Sans',sans-serif;font-weight:600;color:#fff;"
            f"font-size:{fs:.2f}rem;letter-spacing:.14em;\">SPORT "
            "<span style='font-weight:400;color:var(--muted);'>STATISTICS</span></span>"
        )
    return f"<div style='display:flex;align-items:center;gap:12px;'>{mark}{word}</div>"


def onboarding_banner(key: str = "ss_onboarded") -> None:
    """Banner de bienvenida (3 puntos), descartable y solo en la primera visita."""
    if st.session_state.get(key):
        return
    points = [
        ("chart", "Qué es", "Análisis estadístico de eventos deportivos con un modelo "
                            "matemático propio (fútbol, baloncesto, béisbol y tenis)."),
        ("alert", "Qué NO es", "No es una casa de apuestas ni consejo de apuestas. Las "
                               "probabilidades son estimaciones con incertidumbre."),
        ("list", "Cómo leerlo", "Las «situaciones más probables» son los mercados que el "
                                "modelo considera más probables, ordenados de mayor a menor."),
    ]
    rows = ""
    for ic, title, text in points:
        rows += (
            "<div style='display:flex;gap:12px;align-items:flex-start;padding:9px 0;'>"
            "<div style='display:flex;align-items:center;justify-content:center;width:30px;height:30px;"
            "flex:none;border-radius:8px;background:rgba(var(--accent-rgb),0.12);'>"
            f"{icon(ic, 15, 'var(--accent)')}</div>"
            f"<div><span style='color:#fff;font-weight:600;font-size:.9rem;'>{title}.</span> "
            f"<span style='color:var(--muted);font-size:.88rem;'>{html.escape(text)}</span></div></div>"
        )
    st.markdown(
        "<div style='background:var(--card);border:1px solid rgba(var(--accent-rgb),0.25);"
        f"border-radius:14px;padding:16px 20px;margin-bottom:12px;'>{rows}</div>",
        unsafe_allow_html=True,
    )
    if st.button("Entendido, empezar", type="primary", key=key + "_btn"):
        st.session_state[key] = True
        st.rerun()


def skeleton_rows(n: int = 10) -> str:
    """HTML de un esqueleto de N filas (barra de situación) con shimmer. Carga percibida."""
    row = ("<div style='display:flex;align-items:center;gap:12px;padding:9px 4px;'>"
           "<span class='ss-skel' style='width:22px;height:22px;border-radius:6px'></span>"
           "<span class='ss-skel' style='flex:1.2;height:12px'></span>"
           "<span class='ss-skel' style='flex:1;height:6px'></span>"
           "<span class='ss-skel' style='width:44px;height:12px'></span></div>")
    return (f"<div style='background:var(--card);border:1px solid var(--border);"
            f"border-radius:14px;padding:8px 16px'>{row * n}</div>")


def browser_tz():
    """Zona horaria del navegador (IANA) o None. Usa st.context (Streamlit ≥1.35)."""
    try:
        return st.context.timezone
    except Exception:
        return None


def local_hm(utc_iso, tz=None):
    """(hora 'HH:MM', etiqueta_zona) desde un ISO en UTC. Cae a UTC si no hay zona/dato."""
    from datetime import datetime
    s = str(utc_iso or "")
    if len(s) < 16:
        return "", ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return s[11:16], "UTC"
    if tz:
        try:
            from zoneinfo import ZoneInfo
            loc = dt.astimezone(ZoneInfo(tz))
            return loc.strftime("%H:%M"), (loc.tzname() or "local")
        except Exception:
            pass
    return dt.strftime("%H:%M"), "UTC"


def render_freshness(max_hours: int = 48) -> None:
    """Avisa si los datos están desactualizados (last_refresh > max_hours). Best-effort."""
    from datetime import datetime, timezone
    try:
        from core.database.meta import get_meta
        raw = get_meta("last_refresh")
        if not raw:
            return
        ts = datetime.strptime(str(raw).replace(" UTC", ""), "%Y-%m-%d %H:%M")
        ts = ts.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    except Exception:
        return
    if age_h > max_hours:
        st.warning(
            f"Datos desactualizados: última actualización hace {age_h / 24:.1f} días "
            f"({raw}). El refresco automático pudo fallar; revisa el cron.",
            icon=":material/warning:",
        )


def sidebar_nav() -> None:
    """Navegación de marca en el sidebar (reemplaza el nav automático de Streamlit,
    que mostraba «streamlit app»). Nombres e iconos limpios."""
    st.sidebar.page_link("streamlit_app.py", label="Dashboard", icon=":material/trophy:")
    st.sidebar.page_link("pages/1_Analizador_de_Partido.py", label="Analizador",
                         icon=":material/query_stats:")
    st.sidebar.page_link("pages/3_Partidos_del_dia.py", label="Partidos del día",
                         icon=":material/today:")
    st.sidebar.page_link("pages/2_Historial.py", label="Historial",
                         icon=":material/history:")


def page_header(title: str, subtitle: str = "", icon_name: str = "chart") -> None:
    """Cabecera de página: icono en cuadro de acento + título + subtítulo (mockups).

    Usa clases (ss-ph*) para poder encogerse en móvil vía media query (ver _THEME_CSS).
    """
    sub = (f"<div style='color:var(--muted);font-size:.9rem;margin-top:3px;'>"
           f"{html.escape(str(subtitle))}</div>") if subtitle else ""
    st.markdown(
        "<div class='ss-ph' style='display:flex;align-items:center;gap:14px;margin:2px 0 20px;'>"
        "<div class='ss-ph-ico' style='display:flex;align-items:center;justify-content:center;"
        "width:44px;height:44px;border-radius:11px;background:rgba(var(--accent-rgb),0.12);"
        f"border:1px solid rgba(var(--accent-rgb),0.25);'>{icon(icon_name, 22, 'var(--accent)')}</div>"
        f"<div><div class='ss-ph-title' style=\"font-family:'IBM Plex Sans',sans-serif;"
        f"font-size:1.5rem;font-weight:600;color:#fff;line-height:1.15;\">{html.escape(str(title))}</div>"
        f"{sub}</div></div>",
        unsafe_allow_html=True,
    )


def empty_state(title: str, detail: str = "", icon_name: str = "calendar") -> None:
    """Estado vacío homologado (tarjeta con icono) — coherente en toda la app.

    `detail` es texto de desarrollador (puede llevar HTML simple); `title` se escapa.
    """
    det = (f"<div style='color:var(--muted);font-size:.86rem;line-height:1.5;"
           f"max-width:440px;margin:0 auto;'>{detail}</div>") if detail else ""
    st.markdown(
        "<div style='background:var(--card);border:1px solid var(--border);border-radius:14px;"
        "padding:34px 20px;text-align:center;'>"
        f"<div style='display:inline-flex;margin-bottom:12px;'>{icon(icon_name, 28, 'var(--muted)')}</div>"
        f"<div style='color:#fff;font-weight:600;margin-bottom:6px;'>{html.escape(str(title))}</div>"
        f"{det}</div>",
        unsafe_allow_html=True,
    )


def sparkline(values, w: int = 94, h: int = 30, color: str = "var(--accent)") -> str:
    """Mini-gráfico SVG (línea + área) para las tarjetas KPI. '' si hay <2 puntos."""
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals)
    pts = [((i / (n - 1)) * (w - 2) + 1, h - 3 - (v - lo) / rng * (h - 6))
           for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"1,{h} " + line + f" {w - 1},{h}"
    return (
        f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}' fill='none' style='flex:none'>"
        f"<polygon points='{area}' fill='{color}' opacity='0.12'/>"
        f"<polyline points='{line}' fill='none' stroke='{color}' stroke-width='1.6' "
        f"stroke-linecap='round' stroke-linejoin='round'/></svg>"
    )


def kpi_card(label: str, value: str, icon_name: str = "activity",
             sub: str = "", spark=None) -> None:
    """Tarjeta KPI (mockup): icono en cuadro + etiqueta + valor mono grande + sparkline."""
    spark_html = sparkline(spark) if spark else ""
    sub_html = (f"<div style='color:var(--muted);font-size:.75rem;margin-top:7px;'>"
                f"{html.escape(str(sub))}</div>") if sub else ""
    st.markdown(
        "<div style='background:var(--card);border:1px solid var(--border);border-radius:14px;"
        "padding:16px 18px;box-shadow:0 1px 2px rgba(0,0,0,.25);'>"
        "<div style='display:flex;align-items:center;gap:9px;margin-bottom:12px;'>"
        "<div style='display:flex;align-items:center;justify-content:center;width:30px;height:30px;"
        f"border-radius:8px;background:rgba(var(--accent-rgb),0.12);'>{icon(icon_name, 16, 'var(--accent)')}</div>"
        "<span style='color:var(--muted);font-size:.72rem;font-weight:500;text-transform:uppercase;"
        f"letter-spacing:.06em;'>{html.escape(str(label))}</span></div>"
        "<div style='display:flex;align-items:flex-end;justify-content:space-between;gap:10px;'>"
        f"<div><div style=\"font-family:'IBM Plex Mono',monospace;font-size:1.85rem;font-weight:600;"
        f"color:#fff;line-height:1;\">{html.escape(str(value))}</div>{sub_html}</div>"
        f"{spark_html}</div></div>",
        unsafe_allow_html=True,
    )


def pill(text: str, kind: str = "neutral", icon_name: str = None, dot: bool = False) -> str:
    """Chip de estado (Acierto/Fallo, +9.4 pp, Ganador…). Devuelve HTML.

    kind: 'pos' (verde) | 'neg' (rojo) | 'neutral' | 'accent'. Opcional icono o punto.
    """
    rgb, fg = _PILL_COLORS.get(kind, _PILL_COLORS["neutral"])
    lead = ""
    if icon_name:
        lead = icon(icon_name, 13, fg, 2.2)
    elif dot:
        lead = (f"<span style='width:7px;height:7px;border-radius:50%;background:{fg};"
                f"flex:none'></span>")
    return (
        f"<span style='display:inline-flex;align-items:center;gap:5px;padding:3px 9px;"
        f"border-radius:20px;background:rgba({rgb},0.14);color:{fg};font-size:.75rem;"
        f"font-weight:500;white-space:nowrap;'>{lead}{html.escape(str(text))}</span>"
    )


def calibration_bar(value_pp: float, span: float = 15.0) -> str:
    """Barra divergente de calibración (mockup): chip con el valor + barra L/R desde el centro.

    value_pp > 0 (el modelo acierta más de lo prometido) -> verde a la derecha;
    < 0 (optimista) -> rojo a la izquierda. `span` = tope visual en puntos porcentuales.
    """
    kind = "pos" if value_pp >= 0 else "neg"
    _, fg = _PILL_COLORS[kind]
    frac = min(abs(value_pp) / span, 1.0) * 50.0   # % del semiancho
    if value_pp >= 0:
        fill = f"left:50%;width:{frac:.0f}%;"
    else:
        fill = f"right:50%;width:{frac:.0f}%;"
    return (
        "<div style='display:flex;align-items:center;gap:10px;'>"
        f"<span style='font-family:\"IBM Plex Mono\",monospace;font-size:.75rem;font-weight:600;"
        f"color:{fg};width:54px;text-align:right;'>{value_pp:+.1f}%</span>"
        "<div style='position:relative;flex:1;height:6px;background:rgba(255,255,255,0.05);"
        "border-radius:99px;min-width:70px;'>"
        "<div style='position:absolute;left:50%;top:-2px;width:2px;height:10px;"
        "background:rgba(255,255,255,0.5);transform:translateX(-1px);'></div>"
        f"<div style='position:absolute;top:0;{fill}height:100%;background:{fg};"
        "border-radius:99px;'></div></div></div>"
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


def _crest(logo: str) -> str:
    """<img> del escudo (o vacío). Alt vacío: es decorativo (el nombre ya está al lado)."""
    if not logo:
        return ""
    return (f"<img src='{html.escape(str(logo))}' alt='' loading='lazy' "
            f"style='width:44px;height:44px;object-fit:contain;margin-bottom:9px;'>")


def matchup_header(home, away, accent: str = "#5c9a85",
                   accent_rgb: str = "92, 154, 133", subtitle: str = "",
                   home_logo: str = "", away_logo: str = "") -> None:
    """Cabecera de enfrentamiento (H2H) mate, con escudos opcionales.

    Nombres de BD/feed → escapados (XSS-safe). Los logos son URLs del feed (MLB/fútbol).
    """
    sub = (
        f"<div style='position:relative;margin-top:14px;color:var(--muted);font-size:12px;"
        f"letter-spacing:.06em;text-transform:uppercase;'>{html.escape(str(subtitle))}</div>"
    ) if subtitle else ""

    def side(name, logo):
        return (
            "<div style='flex:1;display:flex;flex-direction:column;align-items:center;min-width:0;'>"
            f"{_crest(logo)}<span style=\"font-family:'IBM Plex Sans',sans-serif;font-size:19px;"
            f"font-weight:600;color:#fff;text-align:center;line-height:1.2;\">{html.escape(str(name))}</span></div>"
        )

    st.markdown(
        f"""
        <div role="group" aria-label="{html.escape(str(home))} contra {html.escape(str(away))}"
             style="position:relative;overflow:hidden;border-radius:14px;padding:22px 20px;margin-bottom:20px;
                    text-align:center;background:var(--card);border:1px solid rgba({accent_rgb},0.18);">
          <div style="position:absolute;left:0;right:0;top:0;height:2px;background:rgba({accent_rgb},0.55);"></div>
          <div style="display:flex;justify-content:center;align-items:center;gap:16px;max-width:640px;margin:0 auto;">
            {side(home, home_logo)}
            <div style="font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:12px;letter-spacing:.05em;
                 background:rgba({accent_rgb},0.12);border:1px solid rgba({accent_rgb},0.30);color:{accent};
                 padding:5px 12px;border-radius:6px;flex:none;">VS</div>
            {side(away, away_logo)}
          </div>
          {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )
