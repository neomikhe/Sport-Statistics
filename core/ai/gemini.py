"""
Cliente de Gemini (Google AI Studio) con BÚSQUEDA WEB (grounding).

Aporta CONTEXTO cualitativo actual (bajas, lesiones, sanciones) para un partido.
NO produce probabilidades: el modelo matemático sigue calculando el número; este
contexto solo ajusta la fuerza de los equipos (ver core/ai/adjust.py).

- Sin dependencias nuevas: usa urllib (stdlib).
- La clave se lee de st.secrets["gemini_api_key"] o de GEMINI_API_KEY.
- Si no hay clave -> is_enabled() = False y la función no hace nada (degradación limpia).
- Cualquier error de red/cuota/parseo -> devuelve None (nunca rompe la app).
- El grounding (google_search) hace que use datos ACTUALES, evitando alucinaciones.
"""
import json
import os
import urllib.error
import urllib.request

_DEFAULT_MODEL = "gemini-2.0-flash"
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_VALID_IMPACT = ("none", "low", "medium", "high", "unknown")

# Intro específico por deporte (qué contexto buscar).
_INTRO = {
    "football": 'Para el partido de futbol "{home}" (local) vs "{away}" (visitante) en "{league}", '
                'indica las BAJAS CONFIRMADAS (lesiones o sanciones) de jugadores IMPORTANTES de cada '
                'equipo (maximo goleador, portero titular, etc.) y el impacto en la fuerza de cada equipo.',
    "basketball": 'Para el partido de baloncesto (NBA) "{home}" (local) vs "{away}" (visitante), indica '
                  'las LESIONES y DESCANSOS confirmados (load management) de jugadores CLAVE (estrellas) '
                  'y el impacto en cada equipo.',
    "baseball": 'Para el partido de beisbol (MLB) "{home}" (local) vs "{away}" (visitante), indica '
                'lesiones, ausencias por torneos (Mundial/WBC) o cambios de roster de jugadores clave '
                '(bateadores estrella, abridor del dia) y el impacto en cada equipo.',
    "tennis": 'Para el partido de tenis "{home}" vs "{away}", indica LESIONES o molestias fisicas '
              'recientes, fatiga acumulada o retiros recientes de cada jugador y el impacto en su nivel.',
}

# Formato de salida + reglas (común a todos los deportes).
_FORMAT = """

Responde SOLO con JSON valido, sin texto adicional ni markdown, con este formato exacto:
{{"home":{{"absences":["Nombre - motivo"],"impact":"none|low|medium|high|unknown","note":"breve"}},
"away":{{"absences":["Nombre - motivo"],"impact":"none|low|medium|high|unknown","note":"breve"}}}}
Usa "home" para "{home}" y "away" para "{away}".

Reglas estrictas:
- Si NO tienes informacion fiable y reciente de un lado, usa impact "unknown" y absences [].
- NO inventes nombres ni datos. Es mejor "unknown" que adivinar.
- impact "high" solo si falta una figura DECISIVA; "medium" titulares relevantes; "low" bajas menores."""


def _build_prompt(home: str, away: str, sport: str, league: str) -> str:
    intro = _INTRO.get(sport, _INTRO["football"])
    return ("Eres un asistente de datos deportivos. Usando informacion ACTUAL de la web, "
            + intro.format(home=home, away=away, league=league or "su competicion")
            + _FORMAT.format(home=home, away=away))


def _secret(key: str):
    try:
        import streamlit as st

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key.upper())


def is_enabled() -> bool:
    """True si hay clave de Gemini configurada."""
    return bool(_secret("gemini_api_key"))


def _model() -> str:
    return _secret("gemini_model") or _DEFAULT_MODEL


def match_context(home: str, away: str, sport: str = "football",
                  league: str = "", timeout: int = 25):
    """Devuelve {'home': {...}, 'away': {...}} con el contexto, o None si no disponible.

    `sport` ∈ {football, basketball, baseball, tennis}. En tenis, home=jugador 1.
    """
    key = _secret("gemini_api_key")
    if not key:
        return None

    body = {
        "contents": [{"parts": [{"text": _build_prompt(home, away, sport, league)}]}],
        "tools": [{"google_search": {}}],          # grounding -> datos actuales
        "generationConfig": {"temperature": 0.2},
    }
    url = _ENDPOINT.format(model=_model()) + f"?key={key}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
    except Exception:
        return None
    return parse_response(data)


def _extract_json(text: str):
    """Saca el objeto JSON del texto (puede venir con ```json ... ``` o texto extra)."""
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1] if text.count("```") >= 2 else text
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def _norm_side(d) -> dict:
    d = d if isinstance(d, dict) else {}
    impact = str(d.get("impact", "unknown")).lower().strip()
    if impact not in _VALID_IMPACT:
        impact = "unknown"
    absences = d.get("absences", [])
    if not isinstance(absences, list):
        absences = []
    return {
        "impact": impact,
        "absences": [str(a)[:120] for a in absences][:6],
        "note": str(d.get("note", ""))[:200],
    }


def parse_response(data) -> dict | None:
    """Normaliza la respuesta de Gemini a {'home': {...}, 'away': {...}}."""
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return None
    parsed = _extract_json(text)
    if not isinstance(parsed, dict):
        return None
    return {"home": _norm_side(parsed.get("home")), "away": _norm_side(parsed.get("away"))}
