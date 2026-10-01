from core.predictions import top_situations, situation_rows


def _markets():
    return [
        {"grupo": "1X2", "mercado": "Gana local", "prob": 0.55, "aprox": False},
        {"grupo": "1X2", "mercado": "Empate", "prob": 0.25, "aprox": False},
        {"grupo": "1X2", "mercado": "Gana visitante", "prob": 0.20, "aprox": False},
        {"grupo": "Doble oportunidad", "mercado": "1X", "prob": 0.80, "aprox": False},
        {"grupo": "Doble oportunidad", "mercado": "12", "prob": 0.75, "aprox": False},
        {"grupo": "Doble oportunidad", "mercado": "X2", "prob": 0.45, "aprox": False},
        {"grupo": "Over/Under", "mercado": "Over 0.5", "prob": 0.98, "aprox": False},
        {"grupo": "Over/Under", "mercado": "Under 2.5", "prob": 0.60, "aprox": False},
        {"grupo": "BTTS", "mercado": "BTTS Sí", "prob": 0.52, "aprox": False},
        {"grupo": "1ª mitad", "mercado": "Over 0.5 1ªM", "prob": 0.70, "aprox": True},
    ]


def test_excluye_aproximados():
    out = top_situations(_markets(), n=10)
    assert all(not m.get("aprox") for m in out)
    assert "Over 0.5 1ªM" not in [m["mercado"] for m in out]


def test_limite_n():
    assert len(top_situations(_markets(), n=5)) == 5


def test_tope_por_grupo():
    out = top_situations(_markets(), n=10, per_group=2)
    counts = {}
    for m in out:
        counts[m["grupo"]] = counts.get(m["grupo"], 0) + 1
    assert all(c <= 2 for c in counts.values())
    assert counts.get("1X2", 0) == 2


def test_informativas_antes_que_triviales():
    out = top_situations(_markets(), n=10, per_group=2, max_prob=0.95)
    probs = [m["prob"] for m in out]
    assert out[0]["mercado"] != "Over 0.5"
    if any(p > 0.95 for p in probs):
        assert probs[-1] > 0.95


def test_diversidad():
    out = top_situations(_markets(), n=10)
    assert len({m["grupo"] for m in out}) >= 3


def test_situation_rows_formato():
    rows = situation_rows(_markets(), n=4)
    assert len(rows) == 4
    assert set(rows[0].keys()) == {"Situación", "Grupo", "prob", "Probabilidad"}
    assert rows[0]["Probabilidad"].endswith("%")
