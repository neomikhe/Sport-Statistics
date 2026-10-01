from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from core.forecast.base import fair_odds, half_line, norm_cdf, sigmoid, logit
from core.forecast.baseball import MLBForecaster, MLBParams
from core.forecast.basketball import NBAForecaster
from core.forecast.tennis import TennisForecaster, format_adjust
from sports.baseball.markets import all_markets as mlb_markets, run_matrix, runs_pmf
from sports.basketball.markets import normal_markets
from sports.football.team_ratings import fit_ratings


def _p(markets, name):
    return next(m["prob"] for m in markets if m["mercado"] == name)


def test_half_line_never_integer():
    for x in (0.0, 1.0, 2.49, 224.0, 224.3, 8.75):
        line = half_line(x)
        assert line != round(line)
        assert abs(line - x) <= 1.0


def test_fair_odds_and_logit_roundtrip():
    assert fair_odds(0.5) == pytest.approx(2.0)
    assert fair_odds(0.0) == float("inf")
    assert sigmoid(logit(0.73)) == pytest.approx(0.73)
    assert norm_cdf(0.0) == pytest.approx(0.5)


def test_nba_normal_markets_are_coherent():
    mk = normal_markets(4.0, 226.0, 13.8, 18.8)
    assert _p(mk, "Gana local") + _p(mk, "Gana visitante") == pytest.approx(1.0)
    bands = [m["prob"] for m in mk if m["grupo"] == "Margen de victoria"]
    assert sum(bands) == pytest.approx(1.0, abs=1e-9)
    overs = [m for m in mk if m["grupo"] == "Total puntos" and m["mercado"].startswith("Over")]
    for o in overs:
        under = _p(mk, o["mercado"].replace("Over", "Under"))
        assert o["prob"] + under == pytest.approx(1.0)


def test_nba_wider_total_sigma_less_confident():
    tight = normal_markets(0.0, 220.0, 13.0, 12.0)
    wide = normal_markets(0.0, 220.0, 13.0, 25.0)
    line = "Over 213.5"
    assert _p(tight, line) > _p(wide, line) > 0.5


def _nba_season(strong: int, weak: int, n: int = 40):
    start = date(2024, 11, 1)
    for i in range(n):
        d = start + timedelta(days=i)
        yield d, strong, weak, 120.0, 100.0, 100.0
        yield d, 99, strong, 105.0, 118.0, 100.0


def test_nba_forecaster_learns_stronger_team():
    f = NBAForecaster()
    for d, h, a, hs, as_, poss in _nba_season(1, 2):
        f.update(d, h, a, hs, as_, poss)
    fc = f.forecast(1, 2, "Fuerte", "Débil")
    assert fc.win["home"] > 0.75
    assert fc.expected["margin"] > 5
    assert fc.ratings["home"]["ortg"] > fc.ratings["away"]["ortg"]


def test_nba_missing_boxscore_uses_league_pace():
    f = NBAForecaster()
    f.update(date(2024, 11, 1), 1, 2, 110.0, 100.0, float("nan"))
    assert np.isfinite(f.team_state(1)["pace"])


def test_mlb_run_matrix_sums_to_one_and_ml_complements():
    assert run_matrix(4.6, 4.2).sum() == pytest.approx(1.0)
    mk = mlb_markets(4.6, 4.2)
    assert _p(mk, "Gana local") + _p(mk, "Gana visitante") == pytest.approx(1.0)
    assert _p(mk, "Local -1.5 (gana por ≥2)") + _p(mk, "Visitante +1.5") == pytest.approx(1.0)


def test_mlb_dispersion_widens_distribution():
    k = np.arange(31)
    lo = runs_pmf(4.5, r=100.0)
    hi = runs_pmf(4.5, r=3.0)
    var = lambda p: float((p * (k - (p * k).sum()) ** 2).sum())  # noqa: E731
    assert var(hi) > var(lo)


def test_mlb_shrinkage_tempers_small_samples():
    f = MLBForecaster(MLBParams(prior_games=10.0))
    d0 = date(2024, 4, 1)
    for i in range(3):
        f.update(d0 + timedelta(days=i), 1, 2, 12.0, 1.0)
    rs = f.team_state(1)["rs"]
    assert 4.5 < rs < 12.0


def test_mlb_park_neutralization_avoids_double_counting():
    parks = {1: 1.15, 2: 1.0}
    f = MLBForecaster(park_of=parks)
    d0 = date(2024, 4, 1)
    for i in range(60):
        f.update(d0 + timedelta(days=2 * i), 1, 3, 5.75, 5.75)
        f.update(d0 + timedelta(days=2 * i + 1), 2, 4, 5.0, 5.0)
    assert f.team_state(1)["rs"] == pytest.approx(f.team_state(2)["rs"], rel=0.02)


def test_tennis_bo5_favours_the_favourite():
    assert format_adjust(0.70, 5) > 0.70
    assert format_adjust(0.30, 5) < 0.30
    assert format_adjust(0.62, 3) == pytest.approx(0.62)


def test_tennis_dynamic_k_shrinks_with_experience():
    f = TennisForecaster()
    assert f._k((1, "all")) > 0
    for i in range(50):
        f.update(date(2023, 1, 1) + timedelta(days=i), "hard", 1, 100 + i, 1)
    assert f._k((1, "all")) < f._k((2, "all"))
    fc = f.forecast(1, 2, "hard", 3, "A", "B")
    assert fc.win["home"] > 0.8
    assert fc.win["home"] + fc.win["away"] == pytest.approx(1.0)


def _synthetic_league(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    attack = {1: 0.45, 2: 0.15, 3: -0.10, 4: -0.40}
    rows = []
    d = date(2023, 8, 1)
    for rnd in range(40):
        for h in attack:
            for a in attack:
                if h == a or (h + a + rnd) % 3:
                    continue
                lh = np.exp(0.1 + 0.25 + attack[h] - 0.3 * attack[a])
                la = np.exp(0.1 + attack[a] - 0.3 * attack[h])
                rows.append((d + timedelta(days=rnd * 7), h, a, rng.poisson(lh), rng.poisson(la)))
    return pd.DataFrame(rows, columns=["date", "home_team_id", "away_team_id",
                                       "home_goals", "away_goals"])


def test_team_ratings_recover_attack_order():
    m = _synthetic_league()
    r = fit_ratings(m, m["date"].max() + pd.Timedelta(days=1), reg=1.0)
    att = [r.team(t)["attack"] for t in (1, 2, 3, 4)]
    assert att == sorted(att, reverse=True)
    lh, la = r.lambdas(1, 4)
    assert lh > la > 0
    assert r.home > 0


def test_team_ratings_need_enough_data():
    m = _synthetic_league().head(10)
    assert fit_ratings(m, m["date"].max() + pd.Timedelta(days=1)) is None
