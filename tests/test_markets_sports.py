import numpy as np
import pytest

from sports.basketball import markets as nba
from sports.baseball import markets as mlb
from sports.tennis import markets as tennis
from sports.tennis.markets import set_score_distribution


def _by(markets, mercado):
    return next(x["prob"] for x in markets if x["mercado"] == mercado)


def _all_valid(markets):
    return all(0.0 <= x["prob"] <= 1.0 for x in markets)


def test_nba_ml_complete_and_valid():
    m = nba.all_markets(115, 108, rng=np.random.default_rng(0))
    assert _all_valid(m)
    assert _by(m, "Gana local") + _by(m, "Gana visitante") == pytest.approx(1.0)


def test_nba_favorite_has_higher_ml():
    m = nba.all_markets(118, 104, rng=np.random.default_rng(0))
    assert _by(m, "Gana local") > _by(m, "Gana visitante")


def test_mlb_ml_and_runline_complete():
    m = mlb.all_markets(4.7, 4.1, rng=np.random.default_rng(0))
    assert _all_valid(m)
    assert _by(m, "Gana local") + _by(m, "Gana visitante") == pytest.approx(1.0)
    assert _by(m, "Local -1.5 (gana por ≥2)") + _by(m, "Visitante +1.5") == pytest.approx(1.0)


def test_mlb_ml_is_calibrated_not_extreme():
    m = mlb.all_markets(5.2, 3.9, rng=np.random.default_rng(0))
    assert _by(m, "Gana local") < 0.70


def test_mlb_team_total_monotonic():
    m = mlb.all_markets(4.5, 4.5, rng=np.random.default_rng(0))
    assert _by(m, "Local Over 0.5") >= _by(m, "Local Over 2.5")


def test_tennis_set_distribution_sums_to_one():
    for bo in (3, 5):
        assert sum(set_score_distribution(0.6, bo).values()) == pytest.approx(1.0)


def test_tennis_winner_complete_and_symmetric():
    m = tennis.all_markets(0.5, best_of=3)
    assert _by(m, "Gana Jugador 1") == pytest.approx(0.5)
    assert _by(m, "Gana Jugador 1") + _by(m, "Gana Jugador 2") == pytest.approx(1.0)


def test_tennis_set_handicap_complete():
    m = tennis.all_markets(0.65, best_of=3)
    assert _by(m, "Jugador 1 -1.5 (barrido)") + _by(m, "Jugador 2 +1.5") == pytest.approx(1.0)


def test_tennis_favorite_more_likely_to_sweep():
    fav = tennis.all_markets(0.75, best_of=3)
    dog = tennis.all_markets(0.55, best_of=3)
    assert _by(fav, "Jugador 1 -1.5 (barrido)") > _by(dog, "Jugador 1 -1.5 (barrido)")
