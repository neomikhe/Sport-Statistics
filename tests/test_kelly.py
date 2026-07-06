"""Tests del staking Kelly fraccional (core/betting/kelly.py)."""
import pytest

from core.betting.kelly import kelly_fractional, kelly_full, kelly_stake


def test_no_edge_means_zero_stake():
    # p=0.5, cuota 2.0 -> f = (0.5*1 - 0.5)/1 = 0
    assert kelly_full(0.5, 2.0) == pytest.approx(0.0)


def test_positive_edge_returns_expected_fraction():
    # p=0.6, b=1 -> f = (0.6*1 - 0.4)/1 = 0.2
    assert kelly_full(0.6, 2.0) == pytest.approx(0.2)


def test_negative_edge_is_clamped_to_zero():
    assert kelly_full(0.4, 2.0) == 0.0


def test_odds_at_or_below_one_returns_zero():
    assert kelly_full(0.9, 1.0) == 0.0
    assert kelly_full(0.9, 0.5) == 0.0


def test_fractional_scales_full_kelly():
    assert kelly_fractional(0.6, 2.0, fraction=0.25) == pytest.approx(0.05)


def test_stake_applies_fraction_to_bankroll():
    # full=0.2, 1/4 = 0.05, bankroll 1000 -> 50
    assert kelly_stake(0.6, 2.0, bankroll=1000, fraction=0.25) == pytest.approx(50.0)


def test_stake_is_capped_at_max_pct():
    # edge enorme: full=0.8; con fraction=1.0 daría 0.8, pero el cap 0.05 manda -> 50
    assert kelly_stake(0.9, 2.0, bankroll=1000, fraction=1.0, max_stake_pct=0.05) == pytest.approx(50.0)
