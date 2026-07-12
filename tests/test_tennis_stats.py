"""Tests de aces/dobles faltas de tenis (mercados Poisson)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports.tennis.stats_markets import (ace_markets, df_markets, stats_markets,
                                         _straddling_lines)


def _valid(markets):
    return all(0.0 <= m["prob"] <= 1.0 for m in markets)


def test_straddling_lines_center_on_mean():
    lines = _straddling_lines(9.0, (-3.5, -1.5, 0.5, 2.5))
    assert lines == [5.5, 7.5, 9.5, 11.5]
    # no genera líneas negativas
    assert all(x >= 0.5 for x in _straddling_lines(1.0, (-3.5, -1.5, 0.5, 2.5)))


def test_ace_probs_valid_and_complementary():
    mk = ace_markets(6.0, 5.0, "Jugador A", "Jugador B")
    assert _valid(mk)
    tot = [m for m in mk if m["grupo"] == "Aces totales"]
    for i in range(0, len(tot), 2):
        assert abs(tot[i]["prob"] + tot[i + 1]["prob"] - 1.0) < 1e-9


def test_more_aces_more_over():
    # a igualdad de línea, más aces esperados -> más probable el 'más de'.
    # total 6 -> líneas [2.5,4.5,6.5,8.5]; total 10 -> [6.5,8.5,10.5,12.5]. Común: 6.5
    low = ace_markets(3.0, 3.0, "A", "B")      # total 6
    high = ace_markets(5.0, 5.0, "A", "B")     # total 10
    lo = next(m["prob"] for m in low if m["mercado"] == "más de 6.5 aces")
    hi = next(m["prob"] for m in high if m["mercado"] == "más de 6.5 aces")
    assert hi > lo


def test_player_ace_groups_present():
    mk = ace_markets(8.0, 4.0, "Isner", "Nadal")
    grupos = {m["grupo"] for m in mk}
    assert "Aces Isner" in grupos and "Aces Nadal" in grupos


def test_df_markets_valid():
    mk = df_markets(3.5, 2.5)
    assert _valid(mk)
    assert any(m["grupo"] == "Dobles faltas totales" for m in mk)


def test_combined_stats_markets():
    mk = stats_markets(6.0, 5.0, 3.0, 2.5, "A", "B")
    assert _valid(mk)
    grupos = {m["grupo"] for m in mk}
    assert "Aces totales" in grupos and "Dobles faltas totales" in grupos
    assert all(m["aprox"] is False for m in mk)
