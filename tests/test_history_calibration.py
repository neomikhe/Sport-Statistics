"""Tests del feedback empírico del historial a los eventos (conservador y regularizado)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.history.calibration as cal


def _fake_summary(rows):
    """Monkeypatch de history_summary con un DataFrame sintético."""
    cal._CACHE.clear()
    import core.history.store as store
    store.history_summary = lambda *a, **k: pd.DataFrame(rows)


def test_no_history_is_noop():
    _fake_summary([])
    markets = [{"grupo": "Tarjetas totales", "mercado": "Más de 3.5 tarjetas", "prob": 0.6}]
    out = cal.apply_corrections(markets, "football")
    assert out[0]["prob"] == 0.6   # sin historial -> no cambia nada


def test_optimistic_event_group_gets_lowered():
    # grupo de evento con MUCHA muestra y sesgo optimista: predijo 60%, acertó 50%
    _fake_summary([{"sport": "football", "grupo": "Tarjetas totales", "n": 2000,
                    "aciertos": 1000, "prob_media": 0.60, "tasa_acierto": 0.50}])
    corr = cal.group_corrections()
    assert corr[("football", "Tarjetas totales")] < 0     # baja las probabilidades
    markets = [{"grupo": "Tarjetas totales", "mercado": "Más de 3.5 tarjetas", "prob": 0.60}]
    out = cal.apply_corrections(markets, "football")
    assert out[0]["prob"] < 0.60


def test_small_sample_not_corrected():
    _fake_summary([{"sport": "football", "grupo": "Tarjetas totales", "n": 50,
                    "aciertos": 25, "prob_media": 0.60, "tasa_acierto": 0.50}])
    assert cal.group_corrections() == {}   # N < MIN_N -> no corrige


def test_non_event_group_never_corrected():
    # 1X2 (goles) NUNCA se corrige, aunque tenga sesgo y muestra
    _fake_summary([{"sport": "football", "grupo": "1X2", "n": 5000,
                    "aciertos": 2000, "prob_media": 0.55, "tasa_acierto": 0.40}])
    corr = cal.group_corrections()
    assert ("football", "1X2") not in corr
    markets = [{"grupo": "1X2", "mercado": "Gana local", "prob": 0.55}]
    out = cal.apply_corrections(markets, "football")
    assert out[0]["prob"] == 0.55


def test_strong_regularization_is_conservative():
    # muestra moderada (justo sobre el mínimo): el prior debe regularizar hacia 0.
    _fake_summary([{"sport": "football", "grupo": "Córners totales", "n": 160,
                    "aciertos": 64, "prob_media": 0.60, "tasa_acierto": 0.40}])
    d = cal.group_corrections()[("football", "Córners totales")]
    raw = cal._logit(0.40) - cal._logit(0.60)   # corrección SIN regularizar (~-0.81)
    # el ajuste regularizado es MENOS extremo que el crudo, y sigue negativo
    assert raw < d < 0.0
