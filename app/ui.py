import html
import re
from datetime import datetime, timezone

import streamlit as st

BRAND = {"accent": "#c5f24a", "rgb": "197,242,74"}

SPORTS = {
    "football":   {"label": "Fútbol", "short": "Fútbol", "icon": ":material/sports_soccer:",
                   "accent": "#1fae78", "rgb": "31,174,120", "unit": "goles",
                   "entity": "Equipo", "draw": True},
    "basketball": {"label": "Baloncesto", "short": "NBA", "icon": ":material/sports_basketball:",
                   "accent": "#e8662a", "rgb": "232,102,42", "unit": "puntos",
                   "entity": "Equipo", "draw": False},
    "baseball":   {"label": "Béisbol", "short": "MLB", "icon": ":material/sports_baseball:",
                   "accent": "#3f8cf0", "rgb": "63,140,240", "unit": "carreras",
                   "entity": "Equipo", "draw": False},
    "tennis":     {"label": "Tenis", "short": "Tenis", "icon": ":material/sports_tennis:",
                   "accent": "#e0569a", "rgb": "224,86,154", "unit": "sets",
                   "entity": "Jugador", "draw": False},
}
DRAW_COLOR = "#5d6778"
AWAY_COLOR = "#c3cedd"


# Todo dato dinámico pasa por esc() antes de entrar en HTML.
def esc(value) -> str:
    return html.escape(str(value), quote=True)


def csv_bytes(df) -> bytes:
    from pandas.api.types import is_object_dtype, is_string_dtype

    out = df.copy()
    for col in out.columns:
        if is_object_dtype(out[col]) or is_string_dtype(out[col]):
            out[col] = out[col].map(
                lambda v: f"'{v}" if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v)
    return out.to_csv(index=False).encode("utf-8")


def safe_url(url) -> str:
    u = str(url or "").strip()
    return u if u.lower().startswith("https://") else ""


def cap(text) -> str:
    s = str(text)
    return s[:1].upper() + s[1:]


def fmt_pct(p, digits: int = 1) -> str:
    return "—" if p is None else f"{float(p) * 100:.{digits}f}%"


def fmt_odds(p) -> str:
    if p is None or float(p) < 0.001:
        return "—"
    o = 1.0 / float(p)
    return f"{o:.2f}" if o < 100 else f"{o:.0f}"


def fmt_num(x, digits: int = 1) -> str:
    return "—" if x is None else f"{float(x):,.{digits}f}"


_CSS = """
<style>
:root{
  --bg:#07090d; --surface:#0f141c; --surface-2:#141b25; --surface-3:#1a2330;
  --line:rgba(255,255,255,.075); --line-2:rgba(255,255,255,.14);
  --text:#eef2f7; --text-2:#b9c3d3; --muted:#8a95a8;
  --volt:#c5f24a; --volt-rgb:197,242,74; --on-volt:#0c1204;
  --accent:#c5f24a; --accent-rgb:197,242,74;
  --good:#35c46a; --warn:#f5b83d; --serious:#f0884a; --bad:#e5484d;
  --draw:#5d6778; --away:#c3cedd;
  --f-display:'Big Shoulders Display','Arial Narrow','Roboto Condensed',sans-serif;
  --f-ui:'Schibsted Grotesk',system-ui,-apple-system,'Segoe UI',sans-serif;
  --f-mono:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  --r-sm:8px; --r-md:12px; --r-lg:18px;
  --ease:cubic-bezier(.2,.75,.25,1);
}

/* ---------- Atmósfera: dos focos de estadio sobre tinta ---------- */
.stApp{
  background:
    radial-gradient(900px 420px at 8% -170px, rgba(var(--accent-rgb),.14), transparent 70%),
    radial-gradient(760px 380px at 96% -210px, rgba(var(--volt-rgb),.07), transparent 70%),
    linear-gradient(180deg, rgba(255,255,255,.015), transparent 520px),
    var(--bg) !important;
}
[data-testid="stHeader"]{
  background:rgba(7,9,13,.8) !important;
  backdrop-filter:saturate(140%) blur(12px); -webkit-backdrop-filter:saturate(140%) blur(12px);
  border-bottom:1px solid var(--line);
}
[data-testid="stDecoration"]{display:none;}
[data-testid="stMainBlockContainer"]{max-width:1240px; padding-left:2rem; padding-right:2rem; padding-bottom:5rem;}
@media (max-width:760px){
  [data-testid="stMainBlockContainer"]{padding-left:.9rem; padding-right:.9rem; padding-bottom:4rem;}
}

/* ---------- Navegación superior ---------- */
[data-testid="stTopNavLink"]{font-weight:600; letter-spacing:.01em; border-radius:9px;}
[data-testid="stTopNavLink"][aria-current="page"]{
  background:rgba(var(--volt-rgb),.09) !important; box-shadow:inset 0 -2px 0 var(--volt);
}

/* ---------- Controles nativos (retoques; la base viene del tema) ---------- */
[data-testid="stBaseButton-primary"]{color:var(--on-volt) !important; font-weight:700 !important;}
[data-testid="stBaseButton-primary"] p{color:var(--on-volt) !important;}
[data-testid="stBaseButton-primary"]:hover{filter:brightness(1.07);}
[data-testid="stBaseButton-secondary"]{font-weight:600 !important;}
[data-testid="stBaseButton-secondary"]:hover{border-color:rgba(var(--volt-rgb),.6) !important;}
[data-testid="stBaseButton-segmented_control"],
[data-testid="stBaseButton-segmented_controlActive"],
[data-testid="stBaseButton-pills"],[data-testid="stBaseButton-pillsActive"]{font-weight:600 !important;}
[data-testid="stTabs"] button[role="tab"] p{font-weight:600; font-size:.92rem;}
[data-testid="stExpander"] details{background:var(--surface); border-color:var(--line) !important;}
[data-testid="stWidgetLabel"] p{font-size:.78rem !important; letter-spacing:.06em; text-transform:uppercase; color:var(--muted) !important; font-weight:600 !important;}
[data-testid="stCaptionContainer"]{color:var(--muted) !important;}
[data-testid="stDialog"] [role="dialog"]{background:var(--surface) !important; border:1px solid var(--line-2);}
/* Enlaces de página del contenido como botones-tarjeta */
[data-testid="stMainBlockContainer"] [data-testid="stPageLink-NavLink"]{
  background:var(--surface); border:1px solid var(--line); border-radius:var(--r-md);
  padding:10px 14px; min-height:46px; transition:border-color .2s var(--ease), background-color .2s var(--ease);}
[data-testid="stMainBlockContainer"] [data-testid="stPageLink-NavLink"]:hover{
  border-color:rgba(var(--volt-rgb),.55); background:var(--surface-2);}
[data-testid="stMainBlockContainer"] [data-testid="stPageLink-NavLink"] p{font-weight:600;}
/* Tarjeta de selección del analizador */
.st-key-an_form{background:var(--surface);}
:focus-visible{outline:2px solid var(--volt) !important; outline-offset:2px;}
::-webkit-scrollbar{width:8px; height:8px;}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1); border-radius:99px;}
::-webkit-scrollbar-thumb:hover{background:rgba(var(--volt-rgb),.5);}

/* ---------- Tipografía propia ---------- */
.ss{font-family:var(--f-ui); color:var(--text);}
.ss *{box-sizing:border-box;}
.ss h1, .ss h2, .ss h3{padding:0; line-height:inherit;}
.ss table, .ss th, .ss td{border:0;}
.ss-num{font-variant-numeric:tabular-nums;}
.ss-muted{color:var(--muted);}

/* ---------- Cabecera de página ---------- */
.ss-ph{margin:.1rem 0 .4rem;}
.ss-eyebrow{display:flex; align-items:center; gap:9px; font:700 .72rem/1 var(--f-ui);
  letter-spacing:.16em; text-transform:uppercase; color:var(--accent);}
.ss-eyebrow::before{content:""; width:22px; height:2px; border-radius:2px; background:var(--accent);}
.ss-title{font:800 clamp(2.1rem,5.2vw,3.35rem)/.92 var(--f-display); text-transform:uppercase;
  letter-spacing:.005em; color:var(--text); margin:.45rem 0 .5rem; padding:0 !important;}
.ss-sub{color:var(--text-2); font-size:1rem; line-height:1.55; max-width:64ch; margin:0;}

/* ---------- Secciones ---------- */
.ss-sec{display:flex; align-items:flex-end; justify-content:space-between; gap:12px;
  border-bottom:1px solid var(--line); padding-bottom:.5rem; margin:1.5rem 0 .2rem;}
.ss-sec h2{font:800 1.45rem/1 var(--f-display); text-transform:uppercase; letter-spacing:.02em;
  margin:0; padding:0; color:var(--text);}
.ss-sec .note{color:var(--muted); font-size:.8rem; text-align:right;}

/* ---------- KPIs ---------- */
.ss-kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(148px,1fr)); gap:10px;}
@media (max-width:420px){ .ss-kpi-v{font-size:2rem;} .ss-kpi{min-height:100px; padding:12px 13px;} }
.ss-kpi{position:relative; overflow:hidden; background:var(--surface); border:1px solid var(--line);
  border-radius:var(--r-md); padding:14px 16px 13px; min-height:112px;}
.ss-kpi::after{content:""; position:absolute; left:0; top:0; bottom:0; width:2px; background:var(--accent); opacity:.7;}
.ss-kpi-l{font:700 .68rem/1.25 var(--f-ui); letter-spacing:.1em; text-transform:uppercase; color:var(--muted);}
.ss-kpi-v{font:800 2.3rem/1 var(--f-display); color:var(--text); margin-top:10px; letter-spacing:.01em;}
.ss-kpi-s{font-size:.78rem; color:var(--text-2); margin-top:7px; line-height:1.35;}
.ss-kpi svg.spark{position:absolute; right:12px; bottom:14px; opacity:.95;}
.ss-kpi{container-type:inline-size;}
.ss-kpi.has-spark .ss-kpi-v, .ss-kpi.has-spark .ss-kpi-s{max-width:calc(100% - 94px);}
@container (max-width:240px){
  .ss-kpi svg.spark{display:none;}
  .ss-kpi.has-spark .ss-kpi-v, .ss-kpi.has-spark .ss-kpi-s{max-width:none;}
}
.ss-delta{display:inline-flex; align-items:center; gap:4px; font-weight:600;}
.ss-delta.up{color:var(--good);} .ss-delta.down{color:var(--bad);} .ss-delta.flat{color:var(--text-2);}
.ss-delta.warn{color:var(--warn);}

/* ---------- Chips / pills ---------- */
.ss-pill{display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:99px;
  font:600 .74rem/1.2 var(--f-ui); white-space:nowrap; border:1px solid transparent;}
.ss-pill.neutral{background:rgba(255,255,255,.06); color:var(--text-2); border-color:var(--line);}
.ss-pill.accent{background:rgba(var(--accent-rgb),.14); color:var(--text); border-color:rgba(var(--accent-rgb),.35);}
.ss-pill.good{background:rgba(53,196,106,.14); color:#8be0ab;}
.ss-pill.warn{background:rgba(245,184,61,.14); color:#f6cf7e;}
.ss-pill.bad{background:rgba(229,72,77,.15); color:#f3a2a4;}
.ss-pill.live{background:rgba(229,72,77,.16); color:#ffb4b6;}
.ss-pill.live::before{content:""; width:7px; height:7px; border-radius:50%; background:var(--bad);
  animation:ss-pulse 1.4s ease-in-out infinite;}
.ss-dot{display:inline-block; width:9px; height:9px; border-radius:3px; flex:none;}
.ss-chips{display:flex; flex-wrap:wrap; gap:6px; margin:.35rem 0 .2rem;}

/* ---------- Avisos ---------- */
.ss-note{display:flex; gap:10px; align-items:flex-start; padding:11px 14px; border-radius:var(--r-md);
  border:1px solid var(--line); background:var(--surface); color:var(--text-2); font-size:.87rem; line-height:1.5;}
.ss-note svg{flex:none; margin-top:2px;}
.ss-note.warn{border-color:rgba(245,184,61,.3); background:rgba(245,184,61,.06);}
.ss-note.bad{border-color:rgba(229,72,77,.3); background:rgba(229,72,77,.06);}
.ss-note.info{border-color:rgba(77,156,248,.28); background:rgba(77,156,248,.06);}
.ss-note b{color:var(--text);}
.ss-notes{display:grid; gap:8px;}

/* ---------- Marcador del enfrentamiento (scorebug) ---------- */
.ss-bug{position:relative; overflow:hidden; border-radius:var(--r-lg); border:1px solid var(--line);
  background:
    radial-gradient(120% 140% at 0% 0%, rgba(var(--accent-rgb),.16), transparent 55%),
    radial-gradient(120% 140% at 100% 0%, rgba(195,206,221,.07), transparent 55%),
    var(--surface);
  padding:16px 20px 16px;}
.ss-bug::before{content:""; position:absolute; left:0; right:0; top:0; height:3px;
  background:linear-gradient(90deg, var(--accent) 0%, rgba(var(--accent-rgb),.25) 50%, var(--away) 100%);}
.ss-bug-meta{display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;
  font:700 .7rem/1.3 var(--f-ui); letter-spacing:.12em; text-transform:uppercase; color:var(--muted);}
.ss-bug-grid{display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); align-items:end;
  gap:14px; margin-top:14px;}
.ss-side{display:flex; flex-direction:column; gap:6px; min-width:0;}
.ss-side.away{align-items:flex-end; text-align:right;}
.ss-crest{width:44px; height:44px; object-fit:contain; margin-bottom:2px;}
.ss-name{font:800 clamp(1.15rem,2.7vw,1.95rem)/1.02 var(--f-display); text-transform:uppercase;
  color:var(--text); overflow-wrap:anywhere;}
.ss-role{display:flex; align-items:center; gap:7px; font:600 .7rem/1 var(--f-ui); letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted);}
.ss-side.away .ss-role{flex-direction:row-reverse;}
.ss-big{font:800 clamp(2.6rem,7vw,4.3rem)/.86 var(--f-display); color:var(--text); letter-spacing:-.01em;}
.ss-big small{font-size:.42em; color:var(--muted); margin-left:2px; letter-spacing:0;}
.ss-mid{display:flex; flex-direction:column; align-items:center; gap:6px; padding-bottom:6px;}
.ss-vs{font:800 .82rem/1 var(--f-display); letter-spacing:.24em; color:var(--muted);
  border:1px solid var(--line-2); border-radius:99px; padding:6px 12px 6px 14px;}
.ss-draw{font:800 1.9rem/1 var(--f-display); color:var(--text-2);}
.ss-draw-l{font:600 .66rem/1 var(--f-ui); letter-spacing:.12em; text-transform:uppercase; color:var(--muted);}
.ss-bar{display:flex; gap:2px; height:10px; margin:16px 0 10px;}
.ss-bar > span{display:block; height:100%; min-width:3px; border-radius:2px;
  transform-origin:left center; animation:ss-grow .8s var(--ease) both;}
.ss-bar > span:first-child{border-radius:4px 2px 2px 4px;}
.ss-bar > span:last-child{border-radius:2px 4px 4px 2px;}
.ss-bug-foot{display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); gap:14px;
  font-size:.8rem; color:var(--text-2);}
.ss-bug-foot .r{text-align:right;}
.ss-bug-foot b{color:var(--text); font-weight:700;}
.ss-odds{font-family:var(--f-mono); font-size:.76rem; color:var(--muted);}
.ss-exp{display:flex; flex-wrap:wrap; gap:8px 18px; margin-top:12px; padding-top:12px;
  border-top:1px solid var(--line); font-size:.82rem; color:var(--text-2);}
.ss-exp b{font:800 1.15rem/1 var(--f-display); color:var(--text); margin-left:4px; letter-spacing:.02em;}
@media (max-width:560px){
  .ss-bug{padding:14px 14px 14px;}
  .ss-bug-grid{gap:8px;}
  .ss-crest{width:34px; height:34px;}
  .ss-vs{padding:5px 8px 5px 10px; font-size:.72rem;}
  .ss-draw{font-size:1.45rem;}
}

/* ---------- Lista de situaciones (ranking) ---------- */
.ss-list{background:var(--surface); border:1px solid var(--line); border-radius:var(--r-md); overflow:hidden;}
.ss-li{display:grid; grid-template-columns:30px minmax(0,1fr) minmax(90px,.7fr) 68px;
  grid-template-areas:"rank name meter pct"; align-items:center; gap:4px 14px;
  padding:11px 16px; border-top:1px solid var(--line);
  animation:ss-rise .45s var(--ease) both;}
.ss-li:first-child{border-top:0;}
.ss-li:nth-child(2){animation-delay:.03s} .ss-li:nth-child(3){animation-delay:.06s}
.ss-li:nth-child(4){animation-delay:.09s} .ss-li:nth-child(5){animation-delay:.12s}
.ss-li:nth-child(n+6){animation-delay:.15s}
.ss-rank{grid-area:rank; font:800 1.1rem/1 var(--f-display); color:var(--muted); text-align:center;}
.ss-li-name{grid-area:name; min-width:0;}
.ss-li-name .n{color:var(--text); font-weight:600; font-size:.93rem; line-height:1.3;}
.ss-li-name .g{color:var(--muted); font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; margin-top:3px;}
.ss-meter{grid-area:meter; position:relative; height:6px; border-radius:99px; background:rgba(255,255,255,.07);}
.ss-meter > i{position:absolute; left:0; top:0; bottom:0; border-radius:99px; background:var(--accent);
  transform-origin:left center; animation:ss-grow .7s var(--ease) both;}
.ss-meter > b{position:absolute; left:50%; top:-3px; width:1px; height:12px; background:rgba(255,255,255,.2);}
.ss-li-p{grid-area:pct; text-align:right;}
.ss-li-p .p{font:800 1.2rem/1 var(--f-display); color:var(--text); letter-spacing:.02em;}
.ss-li-p .o{font-family:var(--f-mono); font-size:.7rem; color:var(--muted); margin-top:3px;}
@media (max-width:600px){
  .ss-li{grid-template-columns:24px minmax(0,1fr) 62px;
    grid-template-areas:"rank name pct" ". meter meter"; padding:10px 12px;}
  .ss-li .ss-meter{margin-top:6px;}
}

/* ---------- Mercados agrupados ---------- */
.ss-groups{display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px;}
.ss-group{background:var(--surface); border:1px solid var(--line); border-radius:var(--r-md); padding:12px 14px 6px;}
.ss-group h3{display:flex; justify-content:space-between; align-items:center; gap:8px;
  font:800 1.02rem/1 var(--f-display); text-transform:uppercase; letter-spacing:.04em;
  color:var(--text-2); margin:0 0 6px; padding:0;}
.ss-group h3 span{font:600 .64rem/1 var(--f-ui); letter-spacing:.08em; color:var(--muted);}
.ss-mrow{display:grid; grid-template-columns:minmax(0,1fr) 54px 44px; gap:4px 10px; align-items:center;
  padding:7px 0 8px; border-top:1px solid var(--line);}
.ss-mrow:first-of-type{border-top:0;}
.ss-mrow .n{font-size:.86rem; color:var(--text); line-height:1.3;}
.ss-mrow .n em{font-style:normal; color:var(--muted); font-size:.72rem;}
.ss-mrow .p{font:700 .92rem/1 var(--f-ui); font-variant-numeric:tabular-nums; text-align:right; color:var(--text);}
.ss-mrow .o{font-family:var(--f-mono); font-size:.72rem; color:var(--muted); text-align:right;}
.ss-mrow .m{grid-column:1/-1; height:3px; border-radius:99px; background:rgba(255,255,255,.06); position:relative;}
.ss-mrow .m i{position:absolute; left:0; top:0; bottom:0; border-radius:99px; background:var(--accent); opacity:.85;}

/* ---------- Comparativa equipo vs equipo ---------- */
.ss-cmp{background:var(--surface); border:1px solid var(--line); border-radius:var(--r-md); padding:6px 16px;}
.ss-cmp-row{display:grid; grid-template-columns:minmax(64px,auto) minmax(0,1fr) minmax(64px,auto);
  gap:6px 14px; align-items:center; padding:10px 0; border-top:1px solid var(--line);}
.ss-cmp-row:first-child{border-top:0;}
.ss-cmp-row .v{font:800 1.2rem/1 var(--f-display); color:var(--text); letter-spacing:.02em;}
.ss-cmp-row .v.r{text-align:right;}
.ss-cmp-row .c{text-align:center;}
.ss-cmp-row .c .l{font:600 .68rem/1.2 var(--f-ui); letter-spacing:.1em; text-transform:uppercase; color:var(--muted);}
.ss-cmp-row .split{display:flex; gap:2px; height:5px; margin-top:7px;}
.ss-cmp-row .split span{display:block; height:100%; border-radius:2px;}

/* ---------- Forma (últimos resultados) ---------- */
.ss-form{display:inline-flex; gap:4px;}
.ss-form span{width:22px; height:22px; border-radius:6px; display:grid; place-items:center;
  font:700 .7rem/1 var(--f-ui);}
.ss-form .G{background:rgba(53,196,106,.18); color:#8be0ab;}
.ss-form .E{background:rgba(138,149,168,.2); color:#cdd5e0;}
.ss-form .P{background:rgba(229,72,77,.18); color:#f3a2a4;}

/* ---------- Tarjeta de equipo ---------- */
.ss-team{background:var(--surface); border:1px solid var(--line); border-radius:var(--r-md); padding:14px 16px;}
.ss-team-h{display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap;}
.ss-team-h .t{display:flex; align-items:center; gap:9px; font:800 1.35rem/1 var(--f-display);
  text-transform:uppercase; color:var(--text);}
.ss-stats{display:grid; grid-template-columns:repeat(auto-fit,minmax(92px,1fr)); gap:8px; margin-top:12px;}
.ss-stat{background:var(--surface-2); border-radius:var(--r-sm); padding:9px 11px;}
.ss-stat .l{font:600 .64rem/1.2 var(--f-ui); letter-spacing:.09em; text-transform:uppercase; color:var(--muted);}
.ss-stat .v{font:800 1.3rem/1 var(--f-display); color:var(--text); margin-top:6px; letter-spacing:.02em;}

/* ---------- Tabla responsiva (tarjetas en móvil) ---------- */
.ss-tablewrap{background:var(--surface); border:1px solid var(--line); border-radius:var(--r-md); overflow:hidden;}
.ss-table{width:100%; border-collapse:collapse; font-size:.86rem;}
.ss-table th{font:700 .66rem/1.2 var(--f-ui); letter-spacing:.09em; text-transform:uppercase; color:var(--muted);
  text-align:left; padding:11px 14px; background:rgba(255,255,255,.02); border-bottom:1px solid var(--line);}
.ss-table td{padding:10px 14px; border-top:1px solid var(--line); color:var(--text); vertical-align:middle;}
.ss-table tr:first-child td{border-top:0;}
.ss-table .num{text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap;}
.ss-table th.num{text-align:right;}
.ss-table .dim{color:var(--muted);}
@media (max-width:640px){
  .ss-table thead{display:none;}
  .ss-table, .ss-table tbody, .ss-table tr, .ss-table td{display:block; width:100%;}
  .ss-table tr{padding:10px 14px; border-top:1px solid var(--line);}
  .ss-table tr:first-child{border-top:0;}
  .ss-table td{border:0; padding:3px 0; display:flex; justify-content:space-between; align-items:center;
    gap:14px; text-align:right;}
  .ss-table td::before{content:attr(data-label); color:var(--muted); font:600 .66rem/1.2 var(--f-ui);
    letter-spacing:.08em; text-transform:uppercase; text-align:left; flex:none;}
  .ss-table td.lead{font-weight:700; font-size:.95rem; padding-bottom:6px; text-align:left;}
  .ss-table td.lead::before{display:none;}
}

/* ---------- Tarjeta de partido (agenda) ---------- */
.ss-fx{background:var(--surface); border:1px solid var(--line); border-radius:var(--r-md);
  padding:13px 14px 12px; position:relative; overflow:hidden;}
.ss-fx::before{content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--accent); opacity:.55;}
.ss-fx.live::before{background:var(--bad); opacity:1;}
.ss-fx-top{display:flex; justify-content:space-between; align-items:center; gap:8px;
  font:700 .7rem/1 var(--f-ui); letter-spacing:.1em; text-transform:uppercase; color:var(--muted);}
.ss-fx-top .time{font:800 1.05rem/1 var(--f-display); letter-spacing:.04em; color:var(--text);}
.ss-fx-row{display:grid; grid-template-columns:24px minmax(0,1fr) auto; gap:10px; align-items:center; margin-top:10px;}
.ss-fx-row img{width:24px; height:24px; object-fit:contain;}
.ss-fx-row .ph{width:24px; height:24px; border-radius:6px; background:var(--surface-3);}
.ss-fx-row .tn{font-weight:600; font-size:.95rem; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.ss-fx-row .tp{font:800 1.25rem/1 var(--f-display); color:var(--text);}
.ss-fx-row .sc{font:800 1.3rem/1 var(--f-display); color:var(--text); min-width:18px; text-align:right;}
.ss-fx .ss-bar{height:6px; margin:12px 0 6px;}
.ss-fx-foot{display:flex; justify-content:space-between; gap:8px; font-size:.72rem; color:var(--muted);}

/* ---------- Tarjetas de deporte (inicio) ---------- */
.ss-sport{position:relative; overflow:hidden; border-radius:var(--r-lg); border:1px solid var(--line);
  padding:16px 16px 14px; min-height:150px;
  background:radial-gradient(130% 120% at 100% 0%, rgba(var(--c),.22), transparent 60%), var(--surface);}
.ss-sport .k{font:700 .68rem/1 var(--f-ui); letter-spacing:.14em; text-transform:uppercase; color:rgb(var(--c));}
.ss-sport .t{font:800 2rem/1 var(--f-display); text-transform:uppercase; color:var(--text); margin-top:8px;}
.ss-sport .d{font-size:.82rem; color:var(--text-2); margin-top:8px; line-height:1.45;}
.ss-sport .f{display:flex; gap:14px; flex-wrap:wrap; margin-top:12px; font-size:.75rem; color:var(--muted);}
.ss-sport .f b{color:var(--text); font-weight:700;}

/* ---------- Resumen del día ---------- */
.ss-sums{display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:12px;}
.ss-sum{background:var(--surface); border:1px solid var(--line); border-radius:var(--r-md); padding:13px 14px 12px;}
.ss-sum.ok{box-shadow:inset 3px 0 0 var(--good);} .ss-sum.ko{box-shadow:inset 3px 0 0 var(--bad);}
.ss-sum-h{display:flex; justify-content:space-between; align-items:flex-start; gap:10px;}
.ss-sum-h .s{font:700 .66rem/1 var(--f-ui); letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin-bottom:7px;}
.ss-sum-h .m{font-weight:700; font-size:.96rem; color:var(--text); line-height:1.3; overflow-wrap:anywhere;}
.ss-sum-h .m b{font:800 1.15rem/1 var(--f-display); margin:0 6px; letter-spacing:.03em;}
.ss-sum-rate{font:800 1.6rem/1 var(--f-display); color:var(--text); white-space:nowrap;}
.ss-sum-rate small{font-size:.5em; color:var(--muted); margin-left:1px;}
.ss-sum ul{list-style:none; margin:11px 0 0; padding:0; display:grid; gap:6px;}
.ss-sum li{display:grid; grid-template-columns:18px minmax(0,1fr) auto; gap:9px; align-items:center;
  font-size:.84rem; color:var(--text-2); line-height:1.3;}
.ss-sum li .i{width:18px; height:18px; border-radius:5px; display:grid; place-items:center; font:800 .68rem/1 var(--f-ui);}
.ss-sum li.h .i{background:rgba(53,196,106,.18); color:#8be0ab;}
.ss-sum li.x .i{background:rgba(229,72,77,.18); color:#f3a2a4;}
.ss-sum li.p .i{background:rgba(138,149,168,.18); color:#cdd5e0;}
.ss-sum li .pr{font-variant-numeric:tabular-nums; color:var(--muted); font-size:.76rem;}
.ss-sum li.main .n{color:var(--text); font-weight:600;}
.ss-sr{position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap;}

/* ---------- Calibración (real − prometido) ---------- */
.ss-gap{display:flex; align-items:center; gap:10px; justify-content:flex-end; min-width:150px;}
.ss-gap .v{font-variant-numeric:tabular-nums; font-weight:600; min-width:64px; text-align:right;}
.ss-gap .t{position:relative; flex:1; max-width:120px; height:6px; border-radius:99px; background:rgba(255,255,255,.06);}
.ss-gap .t i{position:absolute; top:0; bottom:0; border-radius:99px;}
.ss-gap .t b{position:absolute; left:50%; top:-3px; width:1px; height:12px; background:rgba(255,255,255,.35);}

/* ---------- Estado vacío ---------- */
.ss-empty{text-align:center; padding:38px 22px; border:1px dashed var(--line-2); border-radius:var(--r-lg);
  background:rgba(255,255,255,.012);}
.ss-empty .t{font:800 1.35rem/1.1 var(--f-display); text-transform:uppercase; color:var(--text); margin-top:10px;}
.ss-empty .d{color:var(--text-2); font-size:.9rem; line-height:1.55; max-width:52ch; margin:8px auto 0;}

/* ---------- Pie ---------- */
.ss-foot{margin-top:2.5rem; padding-top:1rem; border-top:1px solid var(--line); color:var(--muted);
  font-size:.76rem; line-height:1.6; display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap;}

/* ---------- Movimiento ---------- */
@keyframes ss-grow{from{transform:scaleX(0)} to{transform:scaleX(1)}}
@keyframes ss-rise{from{opacity:0; transform:translateY(6px)} to{opacity:1; transform:none}}
@keyframes ss-pulse{0%,100%{opacity:1} 50%{opacity:.35}}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none !important; transition:none !important;}
}
</style>
"""


def _minify(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    return re.sub(r"\s*([{};])\s*", r"\1", css).strip()


_CSS_MIN = _minify(_CSS)


def inject_base_css() -> None:
    st.html(_CSS_MIN)


def set_accent(sport: str | None) -> None:
    meta = SPORTS.get(sport or "", BRAND)
    st.html(f"<style>:root{{--accent:{meta['accent']};--accent-rgb:{meta['rgb']};}}</style>")


def render(markup: str) -> None:
    st.html(f"<div class='ss'>{markup}</div>")


_ICONS = {
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "calendar": '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "trending": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "bot": '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
}


def icon(name: str, size: int = 16, color: str = "currentColor", stroke: float = 2.0) -> str:
    inner = _ICONS.get(name, _ICONS["info"])
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{inner}</svg>')


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    eb = f"<div class='ss-eyebrow'>{esc(eyebrow)}</div>" if eyebrow else ""
    sub = f"<p class='ss-sub'>{esc(subtitle)}</p>" if subtitle else ""
    render(f"<header class='ss-ph'>{eb}<h1 class='ss-title'>{esc(title)}</h1>{sub}</header>")


def section(title: str, note: str = "") -> None:
    nt = f"<div class='note'>{esc(note)}</div>" if note else ""
    render(f"<div class='ss-sec'><h2>{esc(title)}</h2>{nt}</div>")


def notice(text: str, tone: str = "info", title: str = "") -> str:
    ic = {"info": ("info", "#4d9cf8"), "warn": ("alert", "#f5b83d"),
          "bad": ("alert", "#e5484d")}.get(tone, ("info", "#4d9cf8"))
    head = f"<b>{esc(title)}</b> " if title else ""
    return (f"<div class='ss-note {esc(tone)}' role='note'>{icon(ic[0], 17, ic[1])}"
            f"<div>{head}{esc(text)}</div></div>")


def notes(items, tone: str = "info") -> None:
    items = [i for i in (items or []) if i]
    if items:
        render("<div class='ss-notes'>" + "".join(notice(t, tone) for t in items) + "</div>")


def pill(text: str, tone: str = "neutral", dot_color: str = "") -> str:
    dot = f"<span class='ss-dot' style='background:{esc(dot_color)}'></span>" if dot_color else ""
    return f"<span class='ss-pill {esc(tone)}'>{dot}{esc(text)}</span>"


def chips(items) -> None:
    render("<div class='ss-chips'>" + "".join(items) + "</div>")


def empty_state(title: str, detail: str = "", icon_name: str = "calendar") -> None:
    d = f"<div class='d'>{esc(detail)}</div>" if detail else ""
    render(f"<div class='ss-empty'>{icon(icon_name, 30, 'var(--muted)', 1.6)}"
           f"<div class='t'>{esc(title)}</div>{d}</div>")


def sparkline(values, w: int = 86, h: int = 30) -> str:
    vals = [float(v) for v in (values or []) if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals)
    pts = [((i / (n - 1)) * (w - 4) + 2, h - 3 - (v - lo) / rng * (h - 6)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"2,{h} {line} {w - 2},{h}"
    ex, ey = pts[-1]
    return (f"<svg class='spark' width='{w}' height='{h}' viewBox='0 0 {w} {h}' aria-hidden='true'>"
            f"<polygon points='{area}' fill='var(--accent)' opacity='.10'/>"
            f"<polyline points='{line}' fill='none' stroke='var(--accent)' stroke-width='2' "
            f"stroke-linecap='round' stroke-linejoin='round'/>"
            f"<circle cx='{ex:.1f}' cy='{ey:.1f}' r='3.2' fill='var(--accent)' stroke='var(--surface)' "
            f"stroke-width='2'/></svg>")


def kpis(items) -> None:
    cells = []
    for it in items:
        delta = ""
        if it.get("delta"):
            d = it.get("delta_dir", "flat")
            arrow = {"up": "▲", "down": "▼", "warn": "●"}.get(d, "•")
            delta = f"<span class='ss-delta {esc(d)}'>{arrow} {esc(it['delta'])}</span> "
        sub = it.get("sub", "")
        sub_html = f"<div class='ss-kpi-s'>{delta}{esc(sub)}</div>" if (sub or delta) else ""
        spark = sparkline(it.get("spark"))
        cells.append(
            f"<div class='ss-kpi{' has-spark' if spark else ''}'>{spark}"
            f"<div class='ss-kpi-l'>{esc(it['label'])}</div>"
            f"<div class='ss-kpi-v'>{esc(it['value'])}</div>{sub_html}</div>")
    render("<div class='ss-kpis'>" + "".join(cells) + "</div>")


def _segments(win: dict, home_color: str = "var(--accent)") -> list:
    segs = [(win.get("home") or 0.0, home_color, "Local")]
    if win.get("draw") is not None:
        segs.append((win["draw"], DRAW_COLOR, "Empate"))
    segs.append((win.get("away") or 0.0, AWAY_COLOR, "Visitante"))
    return segs


def prob_bar(win: dict, label: str = "Probabilidad de cada resultado") -> str:
    segs = _segments(win)
    total = sum(p for p, _, _ in segs) or 1.0
    spans = "".join(
        f"<span style='flex:{max(p / total, 0.0):.4f} 1 0;background:{c}' "
        f"title='{esc(n)}: {fmt_pct(p / total)}'></span>" for p, c, n in segs)
    aria = ", ".join(f"{n} {fmt_pct(p / total)}" for p, _, n in segs)
    return f"<div class='ss-bar' role='img' aria-label='{esc(label)}: {esc(aria)}'>{spans}</div>"


def _crest(url: str) -> str:
    url = safe_url(url)
    return f"<img class='ss-crest' src='{esc(url)}' alt='' loading='lazy' referrerpolicy='no-referrer'>" if url else ""


def scorebug(fc, meta_left: str = "", meta_right: str = "", crests=("", ""),
             roles=("Local", "Visitante")) -> None:
    win = fc.win
    unit = fc.expected.get("unit", "")
    ph, pd_, pa = win.get("home", 0.0), win.get("draw"), win.get("away", 0.0)

    def side(name, p, role, crest, css, color):
        return (f"<div class='ss-side {css}'>{_crest(crest)}"
                f"<div class='ss-name'>{esc(name)}</div>"
                f"<div class='ss-role'><span class='ss-dot' style='background:{color}'></span>"
                f"{esc(role)}</div>"
                f"<div class='ss-big'>{p * 100:.0f}<small>%</small></div></div>")

    if pd_ is not None:
        mid = (f"<div class='ss-mid'><span class='ss-vs'>VS</span>"
               f"<div class='ss-draw'>{pd_ * 100:.0f}<small style='font-size:.5em'>%</small></div>"
               f"<div class='ss-draw-l'><span class='ss-dot' style='background:{DRAW_COLOR};"
               f"margin-right:5px'></span>Empate</div></div>")
    else:
        mid = "<div class='ss-mid'><span class='ss-vs'>VS</span></div>"

    exp = fc.expected
    exp_items = []
    if unit in ("goles", "puntos", "carreras"):
        label = {"goles": "Goles esperados", "puntos": "Puntos esperados",
                 "carreras": "Carreras esperadas"}[unit]
        d = 2 if unit != "puntos" else 1
        exp_items.append(f"<span>{esc(label)}<b>{fmt_num(exp['home'], d)} – {fmt_num(exp['away'], d)}</b></span>")
        exp_items.append(f"<span>Total<b>{fmt_num(exp['home'] + exp['away'], d)}</b></span>")
        if unit == "puntos":
            exp_items.append(f"<span>Margen local<b>{exp['home'] - exp['away']:+.1f}</b></span>")
    elif unit == "P(set)":
        exp_items.append(f"<span>Prob. de ganar un set<b>{fmt_pct(exp['home'])}</b></span>")

    odds_mid = (f"<span class='ss-odds'>{fmt_odds(pd_)}</span>" if pd_ is not None else "<span></span>")
    markup = (
        "<section class='ss-bug' aria-label='Pronóstico del enfrentamiento'>"
        f"<div class='ss-bug-meta'><span>{esc(meta_left)}</span><span>{esc(meta_right)}</span></div>"
        "<div class='ss-bug-grid'>"
        + side(fc.home, ph, roles[0], crests[0], "home", "var(--accent)")
        + mid
        + side(fc.away, pa, roles[1], crests[1], "away", AWAY_COLOR)
        + "</div>"
        + prob_bar(win)
        + "<div class='ss-bug-foot'>"
        f"<div>Cuota justa <span class='ss-odds'>{fmt_odds(ph)}</span></div>"
        f"<div style='text-align:center'>{odds_mid}</div>"
        f"<div class='r'>Cuota justa <span class='ss-odds'>{fmt_odds(pa)}</span></div>"
        "</div>"
        + (f"<div class='ss-exp'>{''.join(exp_items)}</div>" if exp_items else "")
        + "</section>"
    )
    render(markup)


def situation_list(markets, n_label: bool = True) -> None:
    if not markets:
        empty_state("Sin situaciones", "No hay mercados que mostrar para este partido.", "info")
        return
    rows = []
    for i, m in enumerate(markets, 1):
        p = float(m["prob"])
        grp = f"<div class='g'>{esc(m.get('grupo', ''))}</div>" if n_label else ""
        name = esc(cap(m["mercado"]))
        rows.append(
            f"<div class='ss-li'><div class='ss-rank'>{i}</div>"
            f"<div class='ss-li-name'><div class='n'>{name}</div>{grp}</div>"
            f"<div class='ss-meter' role='progressbar' aria-valuemin='0' aria-valuemax='100' "
            f"aria-valuenow='{p * 100:.0f}' aria-label='{name}'>"
            f"<i style='width:{p * 100:.1f}%'></i><b></b></div>"
            f"<div class='ss-li-p'><div class='p'>{fmt_pct(p)}</div>"
            f"<div class='o'>@ {fmt_odds(p)}</div></div></div>")
    render("<div class='ss-list'>" + "".join(rows) + "</div>")


def market_groups(markets, query: str = "") -> int:
    q = (query or "").strip().lower()
    groups: dict = {}
    for m in markets:
        if q and q not in m["mercado"].lower() and q not in m.get("grupo", "").lower():
            continue
        groups.setdefault(m.get("grupo", "Otros"), []).append(m)
    if not groups:
        empty_state("Sin coincidencias", "Ningún mercado coincide con la búsqueda.", "search")
        return 0
    cards = []
    shown = 0
    for g, items in groups.items():
        rows = []
        for m in items:
            p = float(m["prob"])
            aprox = " <em>(aprox.)</em>" if m.get("aprox") else ""
            rows.append(
                f"<div class='ss-mrow'><div class='n'>{esc(cap(m['mercado']))}{aprox}</div>"
                f"<div class='p'>{fmt_pct(p)}</div><div class='o'>{fmt_odds(p)}</div>"
                f"<div class='m'><i style='width:{p * 100:.1f}%'></i></div></div>")
            shown += 1
        cards.append(f"<div class='ss-group'><h3>{esc(g)}<span>prob · cuota</span></h3>{''.join(rows)}</div>")
    render("<div class='ss-groups'>" + "".join(cards) + "</div>")
    return shown


def compare_rows(rows, home_color: str = "var(--accent)") -> None:
    out = []
    for label, hv, av, fmt, _ in rows:
        try:
            h, a = float(hv), float(av)
            tot = abs(h) + abs(a)
            share = (abs(h) / tot) if tot else 0.5
        except (TypeError, ValueError):
            share = 0.5
        split = (f"<div class='split'><span style='flex:{share:.3f} 1 0;background:{home_color}'></span>"
                 f"<span style='flex:{1 - share:.3f} 1 0;background:{AWAY_COLOR}'></span></div>")
        out.append(
            f"<div class='ss-cmp-row'><div class='v'>{esc(fmt(hv))}</div>"
            f"<div class='c'><div class='l'>{esc(label)}</div>{split}</div>"
            f"<div class='v r'>{esc(fmt(av))}</div></div>")
    render("<div class='ss-cmp'>" + "".join(out) + "</div>")


def form_chips(results) -> str:
    names = {"G": "Ganado", "E": "Empatado", "P": "Perdido"}
    return ("<span class='ss-form'>" + "".join(
        f"<span class='{esc(r)}' title='{esc(names.get(r, r))}'>{esc(r)}</span>" for r in results)
        + "</span>")


def team_card(name: str, color: str, stats, form=None, extra: str = "") -> None:
    stat_html = "".join(f"<div class='ss-stat'><div class='l'>{esc(l)}</div>"
                        f"<div class='v'>{esc(v)}</div></div>" for l, v in stats)
    form_html = form_chips(form) if form else ""
    render(f"<div class='ss-team'><div class='ss-team-h'><div class='t'>"
           f"<span class='ss-dot' style='background:{esc(color)}'></span>{esc(name)}</div>{form_html}</div>"
           f"<div class='ss-stats'>{stat_html}</div>{extra}</div>")


def table(columns, rows, lead: int = 0, caption: str = "") -> None:
    head = "".join(f"<th class='{c}' scope='col'>{esc(t)}</th>" for t, c in columns)
    body = []
    for r in rows:
        tds = []
        for k, (cell, (title, cls)) in enumerate(zip(r, columns)):
            klass = " ".join(x for x in (cls, "lead" if k == lead else "") if x)
            tds.append(f"<td class='{klass}' data-label='{esc(title)}'>{cell}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    cap_html = f"<caption class='ss-sr'>{esc(caption)}</caption>" if caption else ""
    render(f"<div class='ss-tablewrap'><table class='ss-table'>{cap_html}<thead><tr>{head}</tr></thead>"
           f"<tbody>{''.join(body)}</tbody></table></div>")


def _fx_row(name: str, logo: str, right: str) -> str:
    logo = safe_url(logo)
    img = f"<img src='{esc(logo)}' alt='' loading='lazy' referrerpolicy='no-referrer'>" if logo else "<span class='ph'></span>"
    return f"<div class='ss-fx-row'>{img}<span class='tn'>{esc(name)}</span>{right}</div>"


def _fx_right(score, idx: int, p) -> str:
    if score:
        return f"<span class='sc'>{esc(score[idx])}</span>"
    if p is not None:
        return f"<span class='tp'>{p * 100:.0f}%</span>"
    return ""


def fixture_card(f: dict, win: dict | None, time_label: str, status: tuple) -> None:
    text, tone = status
    win = win or {}
    score = f.get("score")
    rows = (_fx_row(f["home"], f.get("home_logo", ""), _fx_right(score, 0, win.get("home")))
            + _fx_row(f["away"], f.get("away_logo", ""), _fx_right(score, 1, win.get("away"))))
    bar = prob_bar(win, "Probabilidades del modelo") if win else ""
    draw = f"Empate {fmt_pct(win['draw'], 0)}" if win.get("draw") is not None else ""
    source = "Modelo" if win else "Sin datos del modelo"
    live = " live" if tone == "live" else ""
    render(f"<article class='ss-fx{live}'>"
           f"<div class='ss-fx-top'><span class='time'>{esc(time_label)}</span>"
           f"{pill(text, tone) if text else ''}</div>{rows}{bar}"
           f"<div class='ss-fx-foot'><span>{esc(draw)}</span><span>{source}</span></div></article>")


def sport_tile(sport: str, title: str, desc: str, facts) -> None:
    meta = SPORTS[sport]
    facts_html = "".join(f"<span>{esc(k)} <b>{esc(v)}</b></span>" for k, v in facts)
    render(f"<div class='ss-sport' style='--c:{meta['rgb']}'><div class='k'>{esc(meta['short'])}</div>"
           f"<div class='t'>{esc(title)}</div><div class='d'>{esc(desc)}</div>"
           f"<div class='f'>{facts_html}</div></div>")


def sport_option(sport: str) -> str:
    m = SPORTS.get(sport)
    return f"{m['icon']} {m['label']}" if m else str(sport)


def gap_cell(gap_pp: float, span: float = 12.0) -> str:
    a = abs(gap_pp)
    color = "var(--bad)"
    if a <= 3:
        color = "var(--good)"
    elif a <= 7:
        color = "var(--warn)"
    frac = min(a / span, 1.0) * 50.0
    pos = f"left:50%;width:{frac:.1f}%" if gap_pp >= 0 else f"right:50%;width:{frac:.1f}%"
    return (f"<div class='ss-gap'><span class='v'>{gap_pp:+.1f} pp</span>"
            f"<span class='t'><i style='{pos};background:{color}'></i><b></b></span></div>")


_MARKS = {True: ("h", "✓", "Acierto"), False: ("x", "✗", "Fallo"), None: ("p", "•", "Pendiente")}


def _summary_card(m: dict) -> str:
    main_hit = m["main"]["hit"]
    state = {True: " ok", False: " ko"}.get(main_hit, "")
    sport = SPORTS.get(m["sport"], {}).get("short", m["sport"])
    score = f"<b>{esc(m['score'].replace('-', '–'))}</b>" if m.get("score") else " vs "
    rate = (f"{m['hits']}<small>/{m['resolved']}</small>" if m["resolved"]
            else "<small>pendiente</small>")
    items = []
    for k, it in enumerate(m["items"]):
        css, mark, label = _MARKS[it["hit"]]
        main = " main" if k == 0 else ""
        items.append(f"<li class='{css}{main}'><span class='i' aria-hidden='true'>{mark}</span>"
                     f"<span class='n'><span class='ss-sr'>{label}: </span>{esc(cap(it['mercado']))}</span>"
                     f"<span class='pr'>{fmt_pct(it['prob'], 0)}</span></li>")
    return (f"<article class='ss-sum{state}'><div class='ss-sum-h'><div>"
            f"<div class='s'>{esc(sport)} · pick principal "
            f"{ {True: 'acertado', False: 'fallado'}.get(main_hit, 'pendiente') }</div>"
            f"<div class='m'>{esc(m['home'])}{score}{esc(m['away'])}</div></div>"
            f"<div class='ss-sum-rate'>{rate}</div></div><ul>{''.join(items)}</ul></article>")


def summary_cards(matches) -> None:
    render("<div class='ss-sums'>" + "".join(_summary_card(m) for m in matches) + "</div>")


def result_pill(hit) -> str:
    return pill("Acierto", "good") if bool(hit) else pill("Fallo", "bad")


def footer() -> None:
    render("<footer class='ss-foot'><span>SportStatistics · probabilidades calibradas, no consejos "
           "de apuesta. Un favorito del 75 % pierde 1 de cada 4 veces.</span>"
           "<span>Modelos v2 · evaluados fuera de muestra</span></footer>")


def browser_tz():
    try:
        return st.context.timezone
    except Exception:
        return None


def local_hm(utc_iso, tz=None):
    s = str(utc_iso or "")
    if len(s) < 16:
        return "", ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return s[11:16], "UTC"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if tz:
        try:
            from zoneinfo import ZoneInfo
            loc = dt.astimezone(ZoneInfo(tz))
            return loc.strftime("%H:%M"), (loc.tzname() or "local")
        except Exception:
            pass
    return dt.strftime("%H:%M"), "UTC"


def status_of(status) -> tuple:
    s = str(status or "").upper()
    if any(k in s for k in ("IN_PLAY", "PROGRESS", "LIVE", "PAUSED", "MANAGER CHALLENGE")):
        return "En vivo", "live"
    if any(k in s for k in ("FINISH", "FINAL", "COMPLET", "GAME OVER", "AWARDED")):
        return "Final", "neutral"
    if any(k in s for k in ("POSTPON", "CANCEL", "SUSPEND")):
        return "Aplazado", "warn"
    if "DELAY" in s:
        return "Retrasado", "warn"
    return "", "neutral"


def freshness(last_refresh: str | None, max_hours: int = 48):
    if not last_refresh:
        return None
    try:
        ts = datetime.strptime(str(last_refresh).replace(" UTC", ""), "%Y-%m-%d %H:%M")
        age_h = (datetime.now(timezone.utc) - ts.replace(tzinfo=timezone.utc)).total_seconds() / 3600
    except ValueError:
        return None
    if age_h < 1:
        txt = "Datos actualizados hace menos de 1 h"
    elif age_h < 48:
        txt = f"Datos actualizados hace {age_h:.0f} h"
    else:
        txt = f"Datos de hace {age_h / 24:.0f} días"
    return txt, ("good" if age_h <= max_hours else "warn")
