"""Tests de coherencia del motor de mercados de fútbol (sports/football/markets.py)."""
import pytest

from sports.football.dixon_coles import exact_probabilities_dc
from sports.football.markets import (
    all_markets,
    premium_picks,
    score_matrix,
    top_markets,
)

LH, LA, RHO = 1.6, 1.1, -0.10


def _p(markets, mercado):
    return next(x["prob"] for x in markets if x["mercado"] == mercado)


def test_score_matrix_sums_to_one():
    assert score_matrix(LH, LA, RHO).sum() == pytest.approx(1.0)


def test_all_probabilities_are_valid():
    for x in all_markets(LH, LA, RHO):
        assert 0.0 <= x["prob"] <= 1.0, x


def test_1x2_sums_to_one():
    m = all_markets(LH, LA, RHO)
    total = _p(m, "Gana local") + _p(m, "Empate") + _p(m, "Gana visitante")
    assert total == pytest.approx(1.0)


def test_double_chance_equals_pair_sum():
    m = all_markets(LH, LA, RHO)
    assert _p(m, "1X (local o empate)") == pytest.approx(
        _p(m, "Gana local") + _p(m, "Empate")
    )


def test_over_under_pairs_sum_to_one():
    m = all_markets(LH, LA, RHO)
    for line in ["0.5", "1.5", "2.5", "3.5"]:
        assert _p(m, f"Over {line}") + _p(m, f"Under {line}") == pytest.approx(1.0)


def test_over_is_monotonic_decreasing():
    m = all_markets(LH, LA, RHO)
    overs = [_p(m, f"Over {l}") for l in ["0.5", "1.5", "2.5", "3.5"]]
    assert overs == sorted(overs, reverse=True)


def test_btts_and_dnb_complete():
    m = all_markets(LH, LA, RHO)
    assert _p(m, "Sí") + _p(m, "No") == pytest.approx(1.0)
    assert _p(m, "Local") + _p(m, "Visitante") == pytest.approx(1.0)  # DNB


def test_matches_dixon_coles_for_shared_markets():
    m = all_markets(LH, LA, RHO)
    dc = exact_probabilities_dc(LH, LA, RHO)
    assert _p(m, "Gana local") == pytest.approx(dc["prob_home"], abs=1e-6)
    assert _p(m, "Over 2.5") == pytest.approx(dc["prob_over_2_5"], abs=1e-6)
    assert _p(m, "Sí") == pytest.approx(dc["prob_btts"], abs=1e-6)


def test_top_markets_sorted_and_sized():
    top = top_markets(all_markets(LH, LA, RHO), n=3)
    assert len(top) == 3
    probs = [x["prob"] for x in top]
    assert probs == sorted(probs, reverse=True)


def test_premium_picks_in_range_and_sorted():
    picks = premium_picks(all_markets(LH, LA, RHO))
    assert all(0.70 <= x["prob"] <= 0.99 for x in picks)
    probs = [x["prob"] for x in picks]
    assert probs == sorted(probs, reverse=True)
