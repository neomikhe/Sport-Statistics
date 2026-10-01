from math import comb

from core.markets import premium_picks, top_markets  # noqa: F401


def set_score_distribution(p_set: float, best_of: int = 3) -> dict:
    p = max(min(p_set, 0.999), 0.001)
    q = 1.0 - p
    need = (best_of + 1) // 2
    dist = {}
    for losing in range(need):
        ways = comb(need - 1 + losing, losing)
        dist[(need, losing)] = ways * (p ** need) * (q ** losing)
        dist[(losing, need)] = ways * (q ** need) * (p ** losing)
    return dist


def match_prob(p_set: float, best_of: int = 3) -> float:
    dist = set_score_distribution(p_set, best_of)
    return sum(pr for (sa, sb), pr in dist.items() if sa > sb)


def p_set_from_match(match_probability: float, best_of: int = 3) -> float:
    target = min(max(match_probability, 1e-6), 1.0 - 1e-6)
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if match_prob(mid, best_of) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def all_markets(p_set: float, best_of: int = 3,
                name_a: str = "Jugador 1", name_b: str = "Jugador 2") -> list:
    dist = set_score_distribution(p_set, best_of)
    need = (best_of + 1) // 2
    p_a = sum(pr for (sa, sb), pr in dist.items() if sa > sb)

    out = [("Ganador", f"Gana {name_a}", p_a),
           ("Ganador", f"Gana {name_b}", 1.0 - p_a)]

    for (sa, sb), pr in dist.items():
        winner = name_a if sa > sb else name_b
        out.append(("Marcador por sets", f"{winner} {max(sa, sb)}-{min(sa, sb)}", pr))

    line = need - 0.5
    p_a_sweep = dist.get((need, 0), 0.0)
    p_b_sweep = dist.get((0, need), 0.0)
    out += [("Hándicap de sets", f"{name_a} -{line} (barrido)", p_a_sweep),
            ("Hándicap de sets", f"{name_b} +{line}", 1.0 - p_a_sweep),
            ("Hándicap de sets", f"{name_b} -{line} (barrido)", p_b_sweep),
            ("Hándicap de sets", f"{name_a} +{line}", 1.0 - p_b_sweep)]

    p_min_sets = p_a_sweep + p_b_sweep
    if best_of == 3:
        out += [("Total de sets", "2 sets (Under 2.5)", p_min_sets),
                ("Total de sets", "3 sets (Over 2.5)", 1.0 - p_min_sets)]
    else:
        out += [("Total de sets", "3 sets (barrido)", p_min_sets),
                ("Total de sets", "4+ sets", 1.0 - p_min_sets)]

    return [{"grupo": g, "mercado": s, "prob": p, "aprox": False} for g, s, p in out]
