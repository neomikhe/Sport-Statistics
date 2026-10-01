import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.baseball.stats_markets import (hit_markets, hr_markets,
                                           strikeout_markets, stats_markets)
from sports.baseball.starter_adjustment import adjust_runs, LEAGUE_AVG_FIP
from sports.baseball.park_factors import park_factor
from core.history.resolvers import (resolve_baseball, resolve_baseball_stats,
                                    BASEBALL_STATS_GROUPS)


def _valid(markets):
    return all(0.0 <= m["prob"] <= 1.0 for m in markets)


def test_hit_markets_valid_and_complementary():
    mk = hit_markets(8.5, 8.0)
    assert _valid(mk)
    tot = [m for m in mk if m["grupo"] == "Hits totales"]
    for i in range(0, len(tot), 2):
        assert abs(tot[i]["prob"] + tot[i + 1]["prob"] - 1.0) < 1e-9


def test_more_hits_more_over():
    low = next(m["prob"] for m in hit_markets(6.0, 6.0)
               if m["mercado"] == "más de 12.5 hits")
    import scipy.stats as ss
    hi = float(ss.poisson.sf(12, 20.0))
    assert hi > low


def test_hr_markets_and_at_least_one():
    mk = hr_markets(1.2, 1.1)
    assert _valid(mk)
    at_least = next(m for m in mk if m["mercado"] == "Al menos 1 jonrón")
    none_hr = next(m for m in mk if m["mercado"] == "Ningún jonrón")
    assert abs(at_least["prob"] + none_hr["prob"] - 1.0) < 1e-9
    assert 0.5 < at_least["prob"] < 1.0


def test_strikeout_markets_valid():
    mk = strikeout_markets(17.0)
    assert _valid(mk)
    assert any(m["grupo"] == "Ponches totales" for m in mk)


def test_all_baseball_stats_markets_resolvable():
    mk = stats_markets(8.5, 8.0, 1.2, 1.1, 17.0)
    for m in mk:
        assert m["grupo"] in BASEBALL_STATS_GROUPS
        res = resolve_baseball_stats(m["grupo"], m["mercado"], 10, 7, 2, 1, 9, 8)
        assert res in (True, False), f"{m['grupo']} / {m['mercado']} -> {res}"


def test_resolve_baseball_runs():
    assert resolve_baseball("Ganador (ML)", "Gana local", 5, 3) is True
    assert resolve_baseball("Ganador (ML)", "Gana visitante", 5, 3) is False
    assert resolve_baseball("Run line (±1.5)", "Local -1.5 (gana por ≥2)", 5, 3) is True
    assert resolve_baseball("Run line (±1.5)", "Visitante +1.5", 5, 3) is False
    assert resolve_baseball("Total carreras", "Over 7.5", 5, 3) is True
    assert resolve_baseball("Total carreras", "Under 7.5", 5, 3) is False
    assert resolve_baseball("Carreras del local", "Local Over 2.5", 5, 3) is True


def test_adjust_runs_by_starter():
    base_h, base_a = 4.6, 4.3
    h, a = adjust_runs(base_h, base_a, home_fip=2.5, away_fip=None)
    assert a < base_a
    assert abs(h - base_h) < 1e-9
    h2, a2 = adjust_runs(base_h, base_a, home_fip=None, away_fip=2.5)
    assert h2 < base_h and a2 == base_a
    assert adjust_runs(base_h, base_a, None, None) == (base_h, base_a)
    _, a3 = adjust_runs(base_h, base_a, home_fip=LEAGUE_AVG_FIP * 1.5, away_fip=None)
    assert a3 > base_a
    _, a4 = adjust_runs(base_h, base_a, home_fip=0.01, away_fip=None)
    assert a4 >= base_a * 0.40


def test_park_factor():
    assert park_factor("Colorado Rockies") > 1.10
    assert park_factor("Seattle Mariners") < 0.95
    assert park_factor("Equipo Inexistente") == 1.0


def test_resolve_baseball_stats_correctness():
    assert resolve_baseball_stats("Hits totales", "más de 16.5 hits", 10, 7, 0, 0, 0, 0) is True
    assert resolve_baseball_stats("Hits totales", "menos de 16.5 hits", 10, 7, 0, 0, 0, 0) is False
    assert resolve_baseball_stats("Jonrones", "Al menos 1 jonrón", 8, 8, 0, 0, 5, 5) is False
    assert resolve_baseball_stats("Jonrones", "Al menos 1 jonrón", 8, 8, 1, 0, 5, 5) is True
    assert resolve_baseball_stats("Hits totales", "más de 16.5 hits", None, None, 0, 0, 0, 0) is None
