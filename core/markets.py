"""
Utilidades de mercados deporte-agnósticas.

Cada deporte construye su lista de mercados como [{grupo, mercado, prob, aprox}, ...]
(todos derivados de UNA misma distribución → coherencia interna). Estas funciones
operan sobre esa lista, sin importar el deporte.
"""


def top_markets(markets: list, n: int = 3, include_approx: bool = False) -> list:
    """Los n mercados más probables. Por defecto excluye los marcados aprox=True."""
    pool = markets if include_approx else [x for x in markets if not x.get("aprox")]
    return sorted(pool, key=lambda x: x["prob"], reverse=True)[:n]


def premium_picks(markets: list, low: float = 0.70, high: float = 0.99) -> list:
    """Picks con probabilidad en [low, high], de mayor a menor. No fuerza nada:
    si ningún mercado cae en el rango, devuelve lista vacía."""
    pool = [x for x in markets if low <= x["prob"] <= high]
    return sorted(pool, key=lambda x: x["prob"], reverse=True)


def straddling_lines(mean: float, offsets) -> list:
    """Líneas de medio punto alrededor de una media (p. ej. media 9 -> 5.5, 7.5, 9.5, 11.5).

    Se usa en mercados de conteo (aces, hits, ponches…) para generar líneas dinámicas
    centradas en el valor esperado, de modo que las situaciones sean informativas y no
    triviales. Descarta líneas negativas."""
    base = round(mean)
    return sorted({base + off for off in offsets if base + off >= 0.5})
