import pandas as pd

from core.history.summary import summarize

COLS = ["sport", "match_key", "home", "away", "grupo", "mercado", "probability", "rank", "hit"]
DAY = "2026-09-30"


def _row(sport, home, away, rank, prob, hit, mercado="Gana local"):
    return (sport, f"{sport}:{DAY}:{home}:{away}", home, away, "1X2", mercado, prob, rank, hit)


def _rows():
    return pd.DataFrame([
        _row("football", "A", "B", 1, 0.62, True),
        _row("football", "A", "B", 2, 0.55, False, "Over 2.5"),
        _row("football", "A", "B", 3, 0.51, None, "Córners"),
        _row("baseball", "C", "D", 1, 0.58, False),
        _row("baseball", "C", "D", 2, 0.71, True, "Under 10.5"),
        _row("football", "E", "F", 1, 0.66, None),
    ], columns=COLS)


def test_totals_and_main_pick():
    s = summarize(_rows(), DAY, {f"football:{DAY}:A:B": "2-1"})
    t = s["totals"]
    assert (t["matches"], t["resolved_matches"]) == (3, 2)
    assert (t["hits"], t["resolved"]) == (2, 4)
    assert (t["main_hits"], t["main_resolved"]) == (1, 2)
    by_home = {m["home"]: m for m in s["matches"]}
    assert by_home["A"]["score"] == "2-1"
    assert by_home["A"]["main"]["hit"] is True
    assert by_home["C"]["main"]["hit"] is False
    assert by_home["E"]["main"]["hit"] is None and by_home["E"]["resolved"] == 0


def test_items_keep_rank_order():
    s = summarize(_rows(), DAY)
    a = next(m for m in s["matches"] if m["home"] == "A")
    assert [i["mercado"] for i in a["items"]] == ["Gana local", "Over 2.5", "Córners"]


def test_empty_day():
    s = summarize(pd.DataFrame(columns=COLS), DAY)
    assert s["matches"] == [] and s["totals"]["matches"] == 0
    assert s["totals"]["promised"] is None
