import math

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from app.ui import AWAY_COLOR, BRAND, DRAW_COLOR, SPORTS

FONT = "Schibsted Grotesk, system-ui, sans-serif"
DISPLAY = "Big Shoulders Display, Arial Narrow, sans-serif"
SURFACE = "#0f141c"
GRID = "#1b2430"
AXIS = "#2a3442"
MUTED = "#8a95a8"
TEXT_2 = "#b9c3d3"
TEXT = "#eef2f7"
GOOD = "#35c46a"
BAD = "#e5484d"
CONFIG = {"displayModeBar": False, "responsive": True, "scrollZoom": False}

pio.templates["floodlight"] = go.layout.Template(layout=dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family=FONT, color=MUTED, size=12),
    margin=dict(l=8, r=8, t=30, b=8),
    xaxis=dict(showgrid=False, zeroline=False, linecolor=AXIS, tickcolor=AXIS,
               ticks="outside", ticklen=4, color=MUTED, automargin=True),
    yaxis=dict(showgrid=True, gridcolor=GRID, gridwidth=1, zeroline=False, color=MUTED,
               automargin=True),
    hoverlabel=dict(bgcolor="#151c27", bordercolor=AXIS, font=dict(family=FONT, color=TEXT, size=12)),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(color=TEXT_2, size=12),
                bgcolor="rgba(0,0,0,0)"),
    hovermode="closest",
))


def accent(sport: str | None) -> str:
    return SPORTS.get(sport or "", BRAND)["accent"]


def _plain(text) -> str:
    return (str(text).replace("<", "‹").replace(">", "›")
            .replace("%{", "% {").replace("&", "&amp;"))


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _show(fig, height: int, key: str | None = None) -> None:
    fig.update_layout(template="floodlight", height=height)
    st.plotly_chart(fig, theme=None, config=CONFIG, key=key)


def score_heatmap(matrix, home: str, away: str, sport: str = "football", key=None) -> None:
    m = np.asarray(matrix, dtype=float) * 100.0
    n = m.shape[0]
    c = accent(sport)
    home, away = _plain(home), _plain(away)
    text = [[f"{v:.1f}" if v >= 1.5 else "" for v in row] for row in m]
    hover = [[f"{home} {i} – {j} {away}<br><b>{m[i, j]:.2f}%</b>" for j in range(n)] for i in range(n)]
    fig = go.Figure(go.Heatmap(
        z=m, x=list(range(n)), y=list(range(n)), text=text, texttemplate="%{text}",
        textfont=dict(family=FONT, size=11, color=TEXT),
        hovertext=hover, hovertemplate="%{hovertext}<extra></extra>",
        colorscale=[[0.0, SURFACE], [0.35, _rgba(c, 0.45)], [1.0, c]],
        xgap=2, ygap=2, showscale=False,
    ))
    fig.update_layout(
        xaxis=dict(title=dict(text=f"Goles de {away}", font=dict(color=TEXT_2, size=12)),
                   side="top", tickmode="linear", showline=False, ticks=""),
        yaxis=dict(title=dict(text=f"Goles de {home}", font=dict(color=TEXT_2, size=12)),
                   autorange="reversed", tickmode="linear", showgrid=False),
        margin=dict(l=8, r=8, t=40, b=8),
    )
    _show(fig, 380, key)


def margin_normal(mu: float, sigma: float, home: str, away: str, sport: str, key=None) -> None:
    x = np.linspace(mu - 3.2 * sigma, mu + 3.2 * sigma, 241)
    y = np.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi)) * 100
    c = accent(sport)
    home, away = _plain(home), _plain(away)
    fig = go.Figure()
    for mask, color, name in ((x >= 0, c, f"Gana {home}"), (x <= 0, AWAY_COLOR, f"Gana {away}")):
        fig.add_trace(go.Scatter(
            x=x[mask], y=y[mask], mode="lines", name=name, line=dict(color=color, width=2),
            fill="tozeroy", fillcolor=_rgba(color if color.startswith("#") else "#c3cedd", 0.12),
            hovertemplate="Margen %{x:.0f}<br>densidad %{y:.2f}%<extra></extra>"))
    fig.add_vline(x=mu, line=dict(color=TEXT_2, width=1),
                  annotation=dict(text=f"esperado {mu:+.1f}", font=dict(color=TEXT_2, size=11),
                                  yanchor="bottom"))
    fig.update_layout(xaxis=dict(title=dict(text=f"Margen de {home} (puntos)", font=dict(color=TEXT_2))),
                      yaxis=dict(title=None, ticksuffix="%"), hovermode="x")
    _show(fig, 280, key)


def diff_bars(pmf_by_diff: dict, home: str, away: str, sport: str, unit: str = "carreras",
              key=None) -> None:
    ks = sorted(pmf_by_diff)
    c = accent(sport)
    home, away = _plain(home), _plain(away)
    colors = [c if k > 0 else (AWAY_COLOR if k < 0 else DRAW_COLOR) for k in ks]
    vals = [pmf_by_diff[k] * 100 for k in ks]
    fig = go.Figure(go.Bar(
        x=ks, y=vals, marker=dict(color=colors, cornerradius=4), width=0.72,
        hovertemplate="Diferencia %{x:+d}<br><b>%{y:.1f}%</b><extra></extra>"))
    fig.update_layout(
        xaxis=dict(title=dict(text=f"{home} − {away} ({unit})", font=dict(color=TEXT_2)),
                   tickmode="linear", dtick=1),
        yaxis=dict(ticksuffix="%"), bargap=0.1)
    _show(fig, 280, key)


def set_scores(dist: dict, name_a: str, name_b: str, sport: str = "tennis", key=None) -> None:
    name_a, name_b = _plain(name_a), _plain(name_b)
    items = sorted(dist.items(), key=lambda kv: (kv[0][0] - kv[0][1]), reverse=True)
    labels = [f"{a}-{b}" for (a, b), _ in items]
    vals = [p * 100 for _, p in items]
    c = accent(sport)
    colors = [c if a > b else AWAY_COLOR for (a, b), _ in items]
    fig = go.Figure(go.Bar(
        x=labels, y=vals, marker=dict(color=colors, cornerradius=4), width=0.6,
        text=[f"{v:.0f}%" for v in vals], textposition="outside",
        textfont=dict(color=TEXT_2, size=12),
        hovertemplate="%{x}<br><b>%{y:.1f}%</b><extra></extra>"))
    fig.update_layout(
        xaxis=dict(title=dict(text=f"Sets ({name_a} – {name_b})", font=dict(color=TEXT_2))),
        yaxis=dict(ticksuffix="%", rangemode="tozero"), showlegend=False)
    _show(fig, 260, key)


def team_trend(dates, scored, conceded, label_for: str, label_against: str,
               color: str, key=None) -> None:
    c = color
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=scored, name=label_for, mode="lines+markers",
        line=dict(color=c, width=2), fill="tozeroy", fillcolor=_rgba(c, 0.10),
        marker=dict(size=8, color=c, line=dict(color=SURFACE, width=2)),
        hovertemplate="%{x}<br>" + label_for + ": <b>%{y}</b><extra></extra>"))
    fig.add_trace(go.Scatter(
        x=dates, y=conceded, name=label_against, mode="lines+markers",
        line=dict(color="#7d889b", width=2),
        marker=dict(size=8, color="#7d889b", line=dict(color=SURFACE, width=2)),
        hovertemplate="%{x}<br>" + label_against + ": <b>%{y}</b><extra></extra>"))
    fig.update_layout(showlegend=True, xaxis=dict(type="category", tickangle=0, nticks=6),
                      yaxis=dict(rangemode="tozero"), hovermode="x unified")
    _show(fig, 240, key)


def bankroll(dates, values, baseline: float, sport: str = "football", key=None) -> None:
    values = list(values)
    if not values:
        return
    c = accent(sport)
    fig = go.Figure(go.Scatter(
        x=list(dates), y=values, mode="lines", line=dict(color=c, width=2),
        fill="tozeroy", fillcolor=_rgba(c, 0.08), name="Banco",
        hovertemplate="%{x|%d %b %Y}<br>Banco <b>%{y:,.0f}</b><extra></extra>"))
    fig.add_hline(y=baseline, line=dict(color=TEXT_2, width=1, dash="dot"),
                  annotation=dict(text=f"Equilibrio {baseline:,.0f}", font=dict(color=TEXT_2, size=11),
                                  xanchor="left", x=0, yanchor="bottom"))
    lo, hi = min(values + [baseline]), max(values + [baseline])
    pad = (hi - lo) * 0.08 or 10
    fig.update_layout(yaxis=dict(range=[lo - pad, hi + pad], tickformat=",.0f"),
                      hovermode="x")
    _show(fig, 300, key)


def reliability(pred, obs, counts, key=None) -> None:
    pred = [p * 100 for p in pred]
    obs = [o * 100 for o in obs]
    size = [max(8.0, min(26.0, 6 + math.sqrt(n) * 1.2)) for n in counts]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", name="Calibración perfecta",
                             line=dict(color=AXIS, width=1.5, dash="dot"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=pred, y=obs, mode="lines+markers", name="Modelo",
        line=dict(color=BRAND["accent"], width=2),
        marker=dict(size=size, color=BRAND["accent"], line=dict(color=SURFACE, width=2)),
        customdata=counts,
        hovertemplate="Prometido %{x:.0f}%<br>Real <b>%{y:.1f}%</b><br>%{customdata} casos<extra></extra>"))
    fig.update_layout(
        showlegend=True,
        xaxis=dict(title=dict(text="Probabilidad del modelo", font=dict(color=TEXT_2)),
                   range=[0, 100], ticksuffix="%", showgrid=True, gridcolor=GRID),
        yaxis=dict(title=dict(text="Frecuencia real", font=dict(color=TEXT_2)),
                   range=[0, 100], ticksuffix="%"))
    _show(fig, 340, key)


def weekly_trend(weeks, hit_rate, mean_prob, key=None) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weeks, y=[v * 100 for v in mean_prob], name="Prometido (prob. media)", mode="lines",
        line=dict(color="#7d889b", width=2),
        hovertemplate="%{x|%d %b}<br>Prometido <b>%{y:.1f}%</b><extra></extra>"))
    fig.add_trace(go.Scatter(
        x=weeks, y=[v * 100 for v in hit_rate], name="Real (tasa de acierto)", mode="lines+markers",
        line=dict(color=BRAND["accent"], width=2),
        marker=dict(size=8, color=BRAND["accent"], line=dict(color=SURFACE, width=2)),
        hovertemplate="%{x|%d %b}<br>Real <b>%{y:.1f}%</b><extra></extra>"))
    fig.update_layout(showlegend=True, yaxis=dict(ticksuffix="%"), hovermode="x unified")
    _show(fig, 280, key)


def yield_by_group(labels, yields, counts, key=None) -> None:
    order = np.argsort(yields)
    labels = [_plain(labels[i]) for i in order]
    ys = [yields[i] * 100 for i in order]
    ns = [counts[i] for i in order]
    colors = [GOOD if v >= 0 else BAD for v in ys]
    fig = go.Figure(go.Bar(
        x=ys, y=labels, orientation="h", marker=dict(color=colors, cornerradius=4), width=0.62,
        text=[f"{v:+.1f}%" for v in ys], textposition="outside",
        textfont=dict(color=TEXT_2, size=11), customdata=ns,
        hovertemplate="%{y}<br>Yield <b>%{x:+.1f}%</b><br>%{customdata} picks<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=AXIS, width=1))
    fig.update_layout(xaxis=dict(ticksuffix="%", showgrid=True, gridcolor=GRID),
                      yaxis=dict(showgrid=False), showlegend=False,
                      margin=dict(l=8, r=40, t=10, b=8))
    _show(fig, max(220, 34 * len(labels) + 40), key)
