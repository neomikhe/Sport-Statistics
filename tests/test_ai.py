"""Tests de la capa de IA: ajuste de fuerza + parseo defensivo de Gemini."""
import pytest

from core.ai.adjust import (
    elo_penalty,
    lambda_multiplier,
    points_multiplier,
    runs_multiplier,
)
from core.ai.gemini import _build_prompt, _extract_json, parse_response


def test_football_multiplier():
    assert lambda_multiplier("none") == 1.0
    assert lambda_multiplier("high") == pytest.approx(0.82)
    assert lambda_multiplier("HIGH") == pytest.approx(0.82)   # case-insensitive
    assert lambda_multiplier("loquesea") == 1.0               # desconocido -> sin cambio


def test_per_sport_scales_are_sensible():
    # 'none'/'unknown' nunca cambian nada
    for fn in (lambda_multiplier, points_multiplier, runs_multiplier):
        assert fn("none") == 1.0 and fn("unknown") == 1.0
    assert elo_penalty("none") == 0.0 and elo_penalty("unknown") == 0.0
    # NBA mueve mucho menos que fútbol; tenis penaliza Elo en 'high'
    assert points_multiplier("high") > lambda_multiplier("high")   # 0.95 > 0.82
    assert runs_multiplier("high") == pytest.approx(0.88)
    assert elo_penalty("high") == pytest.approx(80.0)
    assert elo_penalty("medium") < elo_penalty("high")


def test_prompt_is_sport_specific():
    assert "futbol" in _build_prompt("A", "B", "football", "").lower()
    assert "baloncesto" in _build_prompt("A", "B", "basketball", "").lower()
    assert "beisbol" in _build_prompt("A", "B", "baseball", "").lower()
    assert "tenis" in _build_prompt("A", "B", "tennis", "").lower()


def _resp(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_parse_clean_json():
    out = parse_response(_resp(
        '{"home":{"absences":["Mbappe - lesion"],"impact":"high","note":"x"},'
        '"away":{"absences":[],"impact":"none","note":""}}'
    ))
    assert out["home"]["impact"] == "high"
    assert out["home"]["absences"] == ["Mbappe - lesion"]
    assert out["away"]["impact"] == "none"


def test_parse_with_markdown_fences():
    out = parse_response(_resp('```json\n{"home":{"impact":"medium"},"away":{"impact":"low"}}\n```'))
    assert out["home"]["impact"] == "medium"
    assert out["away"]["impact"] == "low"


def test_parse_invalid_impact_becomes_unknown():
    out = parse_response(_resp('{"home":{"impact":"catastrofico"},"away":{}}'))
    assert out["home"]["impact"] == "unknown"
    assert out["away"]["impact"] == "unknown"


def test_parse_truncates_absences():
    out = parse_response(_resp(
        '{"home":{"impact":"low","absences":["a","b","c","d","e","f","g","h"]},"away":{}}'
    ))
    assert len(out["home"]["absences"]) <= 6   # se limita a 6


def test_parse_malformed_returns_none():
    assert parse_response(_resp("sin json aqui")) is None
    assert parse_response({}) is None


def test_extract_json_from_noise():
    assert _extract_json('bla {"a":1} fin') == {"a": 1}
    assert _extract_json("nada") is None
