import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.football.stats_markets import (corner_markets, card_markets, stats_markets,
                                           _nb_sf, CARD_PHI)
from core.history.resolvers import resolve_football_stats, STATS_GROUPS, resolve


def _probs_valid(markets):
    return all(0.0 <= m["prob"] <= 1.0 for m in markets)


def test_corner_probs_valid_and_complementary():
    mk = corner_markets(5.5, 4.5)
    assert _probs_valid(mk)
    tot = [m for m in mk if m["grupo"] == "Córners totales"]
    for i in range(0, len(tot), 2):
        assert abs(tot[i]["prob"] + tot[i + 1]["prob"] - 1.0) < 1e-9


def test_more_corners_more_over():
    low = next(m for m in corner_markets(3.0, 3.0)
               if m["mercado"] == "Más de 9.5 córners")
    high = next(m for m in corner_markets(7.0, 7.0)
                if m["mercado"] == "Más de 9.5 córners")
    assert high["prob"] > low["prob"]


def test_card_and_red_probs():
    mk = card_markets(4.0, 0.15)
    assert _probs_valid(mk)
    red = next(m for m in mk if m["mercado"] == "Al menos 1 tarjeta roja")
    assert 0.0 < red["prob"] < 0.3
    none_red = next(m for m in mk if m["mercado"] == "Ninguna tarjeta roja")
    assert abs(red["prob"] + none_red["prob"] - 1.0) < 1e-9


def test_all_stats_markets_are_resolvable():
    mk = stats_markets(6.0, 5.0, 4.5, 0.2)
    for m in mk:
        assert m["grupo"] in STATS_GROUPS
        res = resolve_football_stats(m["grupo"], m["mercado"], 7, 4, 3, 2, 1, 0)
        assert res in (True, False), f"{m['grupo']} / {m['mercado']} -> {res}"


def test_resolver_correctness():
    assert resolve_football_stats("Córners totales", "Más de 10.5 córners", 7, 5, 0, 0, 0, 0) is True
    assert resolve_football_stats("Córners totales", "Menos de 10.5 córners", 7, 5, 0, 0, 0, 0) is False
    assert resolve_football_stats("Tarjeta roja", "Al menos 1 tarjeta roja", 5, 5, 2, 2, 0, 0) is False
    assert resolve_football_stats("Tarjeta roja", "Al menos 1 tarjeta roja", 5, 5, 2, 2, 1, 0) is True
    assert resolve_football_stats("Córners totales", "Más de 9.5 córners", None, None, 0, 0, 0, 0) is None


def test_nb_fatter_tails_than_poisson():
    from scipy.stats import poisson
    mean = 4.2
    assert _nb_sf(8, mean, CARD_PHI) > float(poisson.sf(8, mean))
    assert _nb_sf(9, mean, CARD_PHI) > float(poisson.sf(9, mean))
    assert abs(_nb_sf(5, mean, 1.0) - float(poisson.sf(5, mean))) < 1e-9


def test_dispatcher_routes_stats_groups():
    out = {"home_goals": 1, "away_goals": 1, "home_corners": 7, "away_corners": 5,
           "home_yellows": 2, "away_yellows": 3, "home_reds": 1, "away_reds": 0}
    assert resolve("football", "Córners totales", "Más de 10.5 córners", out) is True
    assert resolve("football", "1X2", "Empate", out) is True
