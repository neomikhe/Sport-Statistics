def top_markets(markets: list, n: int = 3, include_approx: bool = False) -> list:
    pool = markets if include_approx else [x for x in markets if not x.get("aprox")]
    return sorted(pool, key=lambda x: x["prob"], reverse=True)[:n]


def premium_picks(markets: list, low: float = 0.70, high: float = 0.99) -> list:
    pool = [x for x in markets if low <= x["prob"] <= high]
    return sorted(pool, key=lambda x: x["prob"], reverse=True)


def straddling_lines(mean: float, offsets) -> list:
    base = round(mean)
    return sorted({base + off for off in offsets if base + off >= 0.5})
