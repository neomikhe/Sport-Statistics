"""
Tests del cliente de football-data.org: cabecera de auth y THROTTLING automático.

El proveedor pide expresamente que el cliente examine las cabeceras de respuesta para
auto-limitarse y no saturar el rate limiter (free tier: 10 req/min).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.fixtures.football as fb


class _Headers(dict):
    """Cabeceras HTTP simuladas (interfaz .get como las de urllib)."""
    def get(self, key, default=None):
        return dict.get(self, key, default)


def _reset_state():
    fb._rate["remaining"] = None
    fb._rate["reset_at"] = 0.0


def test_lee_la_cuota_de_las_cabeceras():
    _reset_state()
    fb._remember_quota(_Headers({"X-Requests-Available-Minute": "7",
                                 "X-RequestCounter-Reset": "40"}))
    assert fb._rate["remaining"] == 7
    assert 35 <= fb._rate["reset_at"] - time.time() <= 45


def test_cabeceras_ausentes_o_basura_no_rompen():
    _reset_state()
    fb._remember_quota(_Headers({}))                      # sin cabeceras
    fb._remember_quota(_Headers({"X-Requests-Available-Minute": "abc"}))  # basura
    assert fb._rate["remaining"] is None                  # degrada sin excepción


def test_throttle_espera_cuando_no_queda_cuota():
    _reset_state()
    fb._rate["remaining"] = 0
    fb._rate["reset_at"] = time.time()      # reset ya vencido -> espera mínima
    t0 = time.time()
    fb._throttle()
    assert time.time() - t0 < 3             # no se cuelga
    assert fb._rate["remaining"] is None    # tras el reset, vuelve a intentar


def test_throttle_no_espera_si_queda_cuota():
    _reset_state()
    fb._rate["remaining"] = 5
    t0 = time.time()
    fb._throttle()
    assert time.time() - t0 < 0.2           # con cuota, no duerme


def test_espera_de_429_respeta_al_servidor():
    assert fb._reset_wait(_Headers({"X-RequestCounter-Reset": "30"})) == 31.0
    assert fb._reset_wait(_Headers({"Retry-After": "15"})) == 16.0
    assert fb._reset_wait(None) == 60.0                   # sin cabeceras -> por defecto
    assert fb._reset_wait(_Headers({"X-RequestCounter-Reset": "9999"})) <= fb._MAX_WAIT_S


def test_sin_token_degrada_limpio(monkeypatch):
    monkeypatch.setattr(fb, "_token", lambda: None)
    assert fb.todays_games() == []          # no revienta ni llama a la red
    assert fb.finished_scores() == []
