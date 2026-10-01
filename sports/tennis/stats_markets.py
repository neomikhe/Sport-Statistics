from scipy.stats import poisson

from core.markets import straddling_lines as _straddling_lines


def _over_under(grupo: str, prefijo: str, mean: float, lines, unidad: str) -> list:
    out = []
    for line in lines:
        p_over = float(poisson.sf(int(line), max(0.1, mean)))
        out.append((grupo, f"{prefijo}más de {line:.1f} {unidad}", p_over))
        out.append((grupo, f"{prefijo}menos de {line:.1f} {unidad}", 1.0 - p_over))
    return out


def ace_markets(e_aces_a: float, e_aces_b: float, name_a: str, name_b: str) -> list:
    total = max(0.2, e_aces_a + e_aces_b)
    out = _over_under("Aces totales", "", total, _straddling_lines(total, (-3.5, -1.5, 0.5, 2.5)), "aces")
    for e, name in ((e_aces_a, name_a), (e_aces_b, name_b)):
        for line in _straddling_lines(max(0.2, e), (-1.5, 0.5, 2.5)):
            p = float(poisson.sf(int(line), max(0.1, e)))
            out.append((f"Aces {name}", f"{name} más de {line:.1f} aces", p))
    return [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in out]


def df_markets(e_df_a: float, e_df_b: float) -> list:
    total = max(0.2, e_df_a + e_df_b)
    out = _over_under("Dobles faltas totales", "", total,
                      _straddling_lines(total, (-2.5, -0.5, 1.5, 3.5)), "dobles faltas")
    return [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in out]


def stats_markets(e_aces_a: float, e_aces_b: float, e_df_a: float, e_df_b: float,
                  name_a: str, name_b: str) -> list:
    return (ace_markets(e_aces_a, e_aces_b, name_a, name_b)
            + df_markets(e_df_a, e_df_b))
