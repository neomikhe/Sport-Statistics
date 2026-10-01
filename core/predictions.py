TRIVIAL = 0.95


def top_situations(markets, n: int = 10, per_group: int = 2, max_prob: float = TRIVIAL) -> list:
    real = [m for m in markets if not m.get("aprox")]
    informativas = sorted((m for m in real if m["prob"] <= max_prob),
                          key=lambda x: x["prob"], reverse=True)
    triviales = sorted((m for m in real if m["prob"] > max_prob),
                       key=lambda x: x["prob"], reverse=True)

    out, counts = [], {}
    for m in list(informativas) + list(triviales):
        g = m.get("grupo", "")
        if counts.get(g, 0) >= per_group:
            continue
        out.append(m)
        counts[g] = counts.get(g, 0) + 1
        if len(out) >= n:
            break
    return out


def situation_rows(markets, n: int = 10) -> list:
    rows = []
    for m in top_situations(markets, n=n):
        rows.append({
            "Situación": m["mercado"],
            "Grupo": m.get("grupo", ""),
            "prob": float(m["prob"]),
            "Probabilidad": f"{m['prob'] * 100:.1f} %",
        })
    return rows
