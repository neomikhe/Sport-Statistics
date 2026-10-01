import pytest

from core.betting.kelly import kelly_fractional, kelly_full, kelly_stake


def test_no_edge_means_zero_stake():
    assert kelly_full(0.5, 2.0) == pytest.approx(0.0)


def test_positive_edge_returns_expected_fraction():
    assert kelly_full(0.6, 2.0) == pytest.approx(0.2)


def test_negative_edge_is_clamped_to_zero():
    assert kelly_full(0.4, 2.0) == 0.0


def test_odds_at_or_below_one_returns_zero():
    assert kelly_full(0.9, 1.0) == 0.0
    assert kelly_full(0.9, 0.5) == 0.0


def test_fractional_scales_full_kelly():
    assert kelly_fractional(0.6, 2.0, fraction=0.25) == pytest.approx(0.05)


def test_stake_applies_fraction_to_bankroll():
    assert kelly_stake(0.6, 2.0, bankroll=1000, fraction=0.25) == pytest.approx(50.0)


def test_stake_is_capped_at_max_pct():
    assert kelly_stake(0.9, 2.0, bankroll=1000, fraction=1.0, max_stake_pct=0.05) == pytest.approx(50.0)
