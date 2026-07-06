"""
Gráficos Plotly con estética premium oscura (estilo Sofascore / ESPN Stats).

Sin toolbar, fondo transparente (se integra con el tema), tipografía Inter,
colores de marca por deporte. Todos los datos vienen del modelo (no de usuario);
las etiquetas que sí pueden traer texto de BD (nombres de equipo) se escapan.
"""
import html

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Acento por deporte (coincide con app/ui.py)
ACCENT = {
    "football": "#5c9a85",
    "basketball": "#bd8560",
    "baseball": "#5f8fa8",
    "tennis": "#b3985c",
}

_FONT = "IBM Plex Sans, system-ui, sans-serif"
_GRID = "rgba(255,255,255,0.05)"
_MUTED = "#94a3b8"
_INK = "#0a0e1a"           # texto oscuro para fondos claros
_UP = "#5c9a85"            # ganancia (bankroll)
_DOWN = "#ef4444"          # pérdida (bankroll)
_DRAW = "#475569"          # empate / neutro
_AWAY = "#94a3b8"          # visitante en la barra de probabilidad
_NO_BAR = {"displayModeBar": False}

# ---- Mejora #4: plantilla Plotly registrada UNA vez (DRY) ----
pio.templates["sportstats_dark"] = go.layout.Template(layout=dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family=_FONT, color=_MUTED, size=12),
    colorway=list(ACCENT.values()),
    margin=dict(l=10, r=10, t=26, b=10),
    xaxis=dict(showgrid=False, zeroline=False, color=_MUTED),
    yaxis=dict(showgrid=True, gridcolor=_GRID, zeroline=False, color=_MUTED),
    hoverlabel=dict(font=dict(family=_FONT), bgcolor="#0d1426"),
))


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _text_on(hex_color: str) -> str:
    """Negro o blanco según la luminancia del fondo (contraste legible)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return _INK if lum > 0.6 else "#ffffff"


def _empty(height: int, msg: str = "Sin datos recientes") -> None:
    """Mejora #5: placeholder con estilo cuando no hay datos que graficar."""
    st.markdown(
        f"<div style='height:{height}px;display:flex;align-items:center;"
        f"justify-content:center;color:{_MUTED};font-family:{_FONT};font-size:.85rem;"
        f"border:1px dashed {_GRID};border-radius:14px;'>{html.escape(msg)}</div>",
        unsafe_allow_html=True,
    )


def _layout(height: int, **extra):
    base = dict(template="sportstats_dark", height=height,
                showlegend=False, hovermode="x unified")
    base.update(extra)
    return base


def _show(fig) -> None:
    st.plotly_chart(fig, use_container_width=True, config=_NO_BAR)


def trend(df, x_col, for_col, against_col, for_label, against_label, accent):
    """Tendencia: área 'a favor' (acento) + línea punteada 'en contra' (gris)."""
    if df is None or len(df) == 0:
        return _empty(220)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df[x_col], y=df[for_col], name=for_label, mode="lines+markers",
        line=dict(color=accent, width=2.5, shape="spline"),
        fill="tozeroy", fillcolor=_rgba(accent, 0.13),
        marker=dict(size=6, color=accent),
    ))
    fig.add_trace(go.Scatter(
        x=df[x_col], y=df[against_col], name=against_label, mode="lines+markers",
        line=dict(color="#64748b", width=1.8, dash="dot", shape="spline"),
        marker=dict(size=5, color="#64748b"),
    ))
    fig.update_layout(**_layout(
        220, showlegend=True,
        legend=dict(orientation="h", y=1.22, x=0, font=dict(size=11)),
    ))
    _show(fig)


def bars(labels, values, accent, height=300, horizontal=False, pct=False):
    """Barras de marca (marcadores probables, Elo por superficie...)."""
    if values is None or len(values) == 0:
        return _empty(height)
    text = [(f"{v * 100:.1f}%" if pct else f"{v:.0f}") for v in values]
    fig = go.Figure(go.Bar(
        x=(values if horizontal else labels),
        y=(labels if horizontal else values),
        orientation=("h" if horizontal else "v"),
        marker=dict(color=accent, line=dict(width=0)),
        text=text, textposition="auto",
        textfont=dict(family=_FONT, color="#ffffff", size=11),
        hoverinfo="skip",
    ))
    extra = dict(hovermode=False)
    if horizontal:
        extra["yaxis"] = dict(autorange="reversed", showgrid=False, color=_MUTED)
        extra["xaxis"] = dict(showgrid=True, gridcolor=_GRID, color=_MUTED)
    fig.update_layout(**_layout(height, **extra))
    _show(fig)


def win_probability(labels, values, colors, height=76):
    """Mejora #1: barra 100% apilada de probabilidad de victoria (estilo Sofascore).

    `labels` puede incluir nombres de equipo (BD) -> se escapan en la leyenda HTML.
    """
    total = sum(values) or 1.0
    fig = go.Figure()
    for lab, v, color in zip(labels, values, colors):
        frac = v / total
        fig.add_trace(go.Bar(
            x=[frac], y=["ml"], orientation="h", width=0.62,
            marker=dict(color=color, line=dict(color=_INK, width=1)),
            text=[f"{frac * 100:.0f}%"], textposition="inside",
            insidetextanchor="middle",
            textfont=dict(family=_FONT, color=_text_on(color), size=15),
            hovertext=[f"{lab}: {frac * 100:.1f}%"], hoverinfo="text",
        ))
    fig.update_layout(
        template="sportstats_dark", barmode="stack", height=height,
        margin=dict(l=0, r=0, t=4, b=4), showlegend=False, bargap=0,
        xaxis=dict(visible=False, range=[0, 1]), yaxis=dict(visible=False),
    )
    _show(fig)
    chips = "&nbsp;&nbsp;&nbsp;".join(
        f"<span style='color:{c}'>●</span> "
        f"<span style='color:#e2e8f0;font-weight:600'>{html.escape(str(lab))}</span> "
        f"<span style='color:{_MUTED}'>{v / total * 100:.0f}%</span>"
        for lab, v, c in zip(labels, values, colors)
    )
    st.markdown(
        f"<div style='font-family:{_FONT};font-size:.82rem;display:flex;gap:1rem;"
        f"flex-wrap:wrap;justify-content:center;margin-top:-6px'>{chips}</div>",
        unsafe_allow_html=True,
    )


def gauge(prob, accent, label="", height=190):
    """Mejora #3: donut radial para la probabilidad del mercado destacado."""
    pct = max(0.0, min(1.0, float(prob)))
    fig = go.Figure(go.Pie(
        values=[pct, 1 - pct], hole=0.72, sort=False, direction="clockwise",
        rotation=0, marker=dict(colors=[accent, "rgba(255,255,255,0.06)"]),
        textinfo="none", hoverinfo="skip",
    ))
    fig.update_layout(
        template="sportstats_dark", height=height,
        margin=dict(l=0, r=0, t=6, b=6), showlegend=False,
        annotations=[dict(text=f"<b>{pct * 100:.0f}%</b>", x=0.5, y=0.5,
                          font=dict(family=_FONT, size=26, color="#ffffff"),
                          showarrow=False)],
    )
    _show(fig)
    if label:
        st.markdown(
            f"<div style='text-align:center;color:{_MUTED};margin-top:-10px;"
            f"font-family:{_FONT};font-size:.85rem'>{html.escape(str(label))}</div>",
            unsafe_allow_html=True,
        )


def bankroll(dates, values, baseline=None, height=280):
    """Mejora #2: evolución del bankroll con break-even y relleno verde/rojo."""
    values, dates = list(values), list(dates)
    if not values:
        return _empty(height)
    if baseline is None:
        baseline = values[0]
    line_color = _UP if values[-1] >= baseline else _DOWN
    base_line = [baseline] * len(dates)
    y_pos = [max(v, baseline) for v in values]
    y_neg = [min(v, baseline) for v in values]

    fig = go.Figure()
    # Relleno verde por encima del break-even
    fig.add_trace(go.Scatter(x=dates, y=base_line, mode="lines",
                             line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=dates, y=y_pos, mode="lines", line=dict(width=0),
                             fill="tonexty", fillcolor=_rgba(_UP, 0.15),
                             hoverinfo="skip", showlegend=False))
    # Relleno rojo por debajo del break-even
    fig.add_trace(go.Scatter(x=dates, y=base_line, mode="lines",
                             line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=dates, y=y_neg, mode="lines", line=dict(width=0),
                             fill="tonexty", fillcolor=_rgba(_DOWN, 0.15),
                             hoverinfo="skip", showlegend=False))
    # Línea de valor (color según ganancia/pérdida final)
    fig.add_trace(go.Scatter(x=dates, y=values, mode="lines",
                             line=dict(color=line_color, width=2.5, shape="spline"),
                             hovertemplate="%{y:,.0f}<extra></extra>"))
    fig.update_layout(**_layout(height))
    fig.add_hline(y=baseline, line=dict(color=_MUTED, width=1, dash="dot"),
                  annotation_text=f"break-even {baseline:,.0f}",
                  annotation_position="top left",
                  annotation_font=dict(family=_FONT, color=_MUTED, size=11))
    _show(fig)
