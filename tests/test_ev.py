"""Tests del cálculo de Expected Value (core/betting/ev.py)."""
import numpy as np
import pytest

from core.betting.ev import edge, ev_array, expected_value, implied_from_odds


def test_fair_bet_has_zero_ev():
    assert expected_value(0.5, 2.0) == pytest.approx(0.0)


def test_positive_value_bet():
    assert expected_value(0.6, 2.0) == pytest.approx(0.2)


def test_negative_value_bet():
    assert expected_value(0.4, 2.0) < 0


def test_implied_probability_is_inverse_of_odds():
    assert implied_from_odds(2.0) == pytest.approx(0.5)
    assert implied_from_odds(4.0) == pytest.approx(0.25)


def test_edge_is_model_minus_implied():
    # cuota 2.0 -> implícita 0.5; modelo 0.55 -> edge 0.05
    assert edge(0.55, 2.0) == pytest.approx(0.05)


def test_ev_array_matches_scalar():
    probs = [0.5, 0.6, 0.4]
    odds = [2.0, 2.0, 2.0]
    expected = [expected_value(p, o) for p, o in zip(probs, odds)]
    assert np.allclose(ev_array(probs, odds), expected)
