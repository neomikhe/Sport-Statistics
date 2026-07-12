"""
Motor de "situaciones más probables" de un enfrentamiento.

Toma la lista de mercados que ya produce cada deporte
([{grupo, mercado, prob, aprox}, ...], todos derivados de UNA misma distribución)
y devuelve las N situaciones más probables y DIVERSAS, ordenadas de mayor a menor.

Criterios (para que la lista sea informativa, no 10 variantes de lo mismo):
  - Descarta los mercados aproximados (aprox=True).
  - Prioriza las situaciones informativas (prob <= max_prob); las casi-certezas
    (p. ej. "más de 0 goles" al 98 %) solo rellenan si el partido es muy desigual.
  - Limita a `per_group` mercados por dimensión (1X2, totales, hándicap, ...),
    para no repetir la misma idea.
"""

TRIVIAL = 0.95   # por encima de esto una "situación" es casi certeza -> poco informativa


def top_situations(markets, n: int = 10, per_group: int = 2, max_prob: float = TRIVIAL) -> list:
    """Las `n` situaciones más probables y variadas de un enfrentamiento.

    Devuelve una sublista de `markets` (mismos dicts: {grupo, mercado, prob, ...}).
    """
    real = [m for m in markets if not m.get("aprox")]
    informativas = sorted((m for m in real if m["prob"] <= max_prob),
                          key=lambda x: x["prob"], reverse=True)
    triviales = sorted((m for m in real if m["prob"] > max_prob),
                       key=lambda x: x["prob"], reverse=True)

    out, counts = [], {}
    for m in list(informativas) + list(triviales):   # informativas primero, casi-certezas al final
        g = m.get("grupo", "")
        if counts.get(g, 0) >= per_group:
            continue
        out.append(m)
        counts[g] = counts.get(g, 0) + 1
        if len(out) >= n:
            break
    return out


def situation_rows(markets, n: int = 10) -> list:
    """Formatea las situaciones para mostrar: [{'Situación', 'Grupo', 'prob', 'Probabilidad'}]."""
    rows = []
    for m in top_situations(markets, n=n):
        rows.append({
            "Situación": m["mercado"],
            "Grupo": m.get("grupo", ""),
            "prob": float(m["prob"]),
            "Probabilidad": f"{m['prob'] * 100:.1f} %",
        })
    return rows
