"""Tests de córners/tarjetas: mercados Poisson + resolvedor."""
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
    # Over X.5 + Under X.5 == 1 para cada línea de córners totales
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
    assert 0.0 < red["prob"] < 0.3           # roja es evento raro
    none_red = next(m for m in mk if m["mercado"] == "Ninguna tarjeta roja")
    assert abs(red["prob"] + none_red["prob"] - 1.0) < 1e-9


def test_all_stats_markets_are_resolvable():
    """Cobertura: dado un resultado concreto, TODA situación de córners/tarjetas
    del top se resuelve a True/False (nunca None por grupo no cubierto)."""
    mk = stats_markets(6.0, 5.0, 4.5, 0.2)
    # resultado real: 7 córners local, 4 visitante; 3+2 amarillas; 1 roja local
    for m in mk:
        assert m["grupo"] in STATS_GROUPS
        res = resolve_football_stats(m["grupo"], m["mercado"], 7, 4, 3, 2, 1, 0)
        assert res in (True, False), f"{m['grupo']} / {m['mercado']} -> {res}"


def test_resolver_correctness():
    # 12 córners totales -> Más de 10.5 = True, Menos de 10.5 = False
    assert resolve_football_stats("Córners totales", "Más de 10.5 córners", 7, 5, 0, 0, 0, 0) is True
    assert resolve_football_stats("Córners totales", "Menos de 10.5 córners", 7, 5, 0, 0, 0, 0) is False
    # sin roja -> "Al menos 1" False
    assert resolve_football_stats("Tarjeta roja", "Al menos 1 tarjeta roja", 5, 5, 2, 2, 0, 0) is False
    # con roja -> True
    assert resolve_football_stats("Tarjeta roja", "Al menos 1 tarjeta roja", 5, 5, 2, 2, 1, 0) is True
    # sin dato de córners -> None (queda pendiente)
    assert resolve_football_stats("Córners totales", "Más de 9.5 córners", None, None, 0, 0, 0, 0) is None


def test_nb_fatter_tails_than_poisson():
    """La Binomial Negativa (sobredispersión) da más masa en la cola alta que Poisson."""
    from scipy.stats import poisson
    mean = 4.2
    # cerca de la media, parecidas; en la cola profunda, NB > Poisson
    assert _nb_sf(8, mean, CARD_PHI) > float(poisson.sf(8, mean))
    assert _nb_sf(9, mean, CARD_PHI) > float(poisson.sf(9, mean))
    # phi=1 -> se degrada exactamente a Poisson
    assert abs(_nb_sf(5, mean, 1.0) - float(poisson.sf(5, mean))) < 1e-9


def test_dispatcher_routes_stats_groups():
    out = {"home_goals": 1, "away_goals": 1, "home_corners": 7, "away_corners": 5,
           "home_yellows": 2, "away_yellows": 3, "home_reds": 1, "away_reds": 0}
    # grupo de córners -> usa el resolvedor de stats, no el de goles
    assert resolve("football", "Córners totales", "Más de 10.5 córners", out) is True
    # grupo de goles sigue funcionando
    assert resolve("football", "1X2", "Empate", out) is True
