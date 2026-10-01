import datetime as dt

import pytest

from sports.football.elo import (
    DEFAULT_ELO,
    EloSystem,
    expected_home_score,
    update_elos,
)


def test_equal_teams_no_home_advantage_is_fifty_fifty():
    assert expected_home_score(1500, 1500, home_advantage=0) == pytest.approx(0.5)


def test_home_advantage_raises_home_probability():
    assert expected_home_score(1500, 1500) > 0.5


def test_expected_scores_are_complementary():
    a = expected_home_score(1600, 1500, home_advantage=0)
    b = expected_home_score(1500, 1600, home_advantage=0)
    assert a + b == pytest.approx(1.0)


def test_update_is_zero_sum():
    eh, ea = 1500.0, 1500.0
    new_h, new_a = update_elos(eh, ea, home_goals=2, away_goals=0)
    assert (new_h + new_a) == pytest.approx(eh + ea)


def test_winner_gains_loser_loses():
    new_h, new_a = update_elos(1500, 1500, home_goals=1, away_goals=0)
    assert new_h > 1500 > new_a


def test_bigger_margin_moves_elo_more():
    narrow_h, _ = update_elos(1500, 1500, 1, 0)
    blowout_h, _ = update_elos(1500, 1500, 3, 0)
    assert (blowout_h - 1500) > (narrow_h - 1500)


def test_system_tracks_and_updates_rating():
    elo = EloSystem()
    assert elo.get(1) == DEFAULT_ELO
    elo.process_match(dt.date(2024, 8, 1), "2024-2025", 1, 2, 2, 0)
    assert elo.get(1) > DEFAULT_ELO
    assert elo.get(2) < DEFAULT_ELO


def test_season_regression_pulls_toward_mean():
    elo = EloSystem(season_regression=0.5)
    elo.process_match(dt.date(2024, 8, 1), "A", 1, 2, 3, 0)
    high = elo.get(1)
    elo.process_match(dt.date(2025, 8, 1), "B", 1, 3, 0, 0)
    assert elo.get(1) < high
