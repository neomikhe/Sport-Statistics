"""
Feedback empírico del historial a los mercados de EVENTOS (córners, tarjetas, hits,
jonrones, ponches). Ajuste conservador y regularizado.

Idea: si un grupo de evento acumula suficientes predicciones resueltas y muestra un
sesgo sistemático (la tasa real difiere de la probabilidad media predicha), corrige
las probabilidades futuras de ese grupo con un desplazamiento en logit (estilo Platt
de un parámetro).

Diseño defensivo (para NO dañar la precisión con datos escasos/ruidosos):
  - Solo grupos de EVENTOS (nunca 1X2/goles/carreras, que están en su techo).
  - Solo con N >= MIN_N resueltas en el grupo.
  - Regularización Beta-Binomial fuerte: la tasa observada se ancla en la predicha con
    un prior de PRIOR muestras, así hace falta MUCHO historial para mover la aguja.
  - Desplazamiento acotado a ±CAP en logit.
  - Se aplica SOLO en display (el analizador). Las fixtures/cron registran el modelo
    CRUDO, para que el historial siempre mida el modelo real y el bucle no se realimente.

Sin historial (BD vacía o local) -> no hace nada (no-op).
"""
import math

from core.history.resolvers import STATS_GROUPS, BASEBALL_STATS_GROUPS

EVENT_GROUPS = set(STATS_GROUPS) | set(BASEBALL_STATS_GROUPS)

MIN_N = 150       # mínimo de resueltas en el grupo para corregir
PRIOR = 200.0     # fuerza del prior (regularización): más alto = más conservador
CAP = 0.5         # tope del desplazamiento en logit

_CACHE = {}


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def group_corrections(engine=None) -> dict:
    """{(sport, grupo): delta_logit} para grupos de evento con suficiente historial.

    Cacheado por proceso. {} si no hay historial (no-op).
    """
    if "corr" in _CACHE:
        return _CACHE["corr"]
    try:
        from core.history.store import history_summary
        df = history_summary()
    except Exception:
        return {}
    corr = {}
    if df is not None and not df.empty:
        for r in df.itertuples(index=False):
            if r.grupo not in EVENT_GROUPS:
                continue
            n = int(r.n)
            if n < MIN_N:
                continue
            p = float(r.prob_media)
            hits = float(r.aciertos)
            # Tasa observada regularizada hacia la predicha (Beta-Binomial).
            obs_shrunk = (hits + PRIOR * p) / (n + PRIOR)
            delta = _logit(obs_shrunk) - _logit(p)
            corr[(r.sport, r.grupo)] = max(-CAP, min(CAP, delta))
    _CACHE["corr"] = corr
    return corr


def apply_corrections(markets: list, sport: str, engine=None) -> list:
    """Aplica el ajuste de calibración a los mercados de EVENTO (in-place). No-op sin historial."""
    corr = group_corrections(engine)
    if not corr:
        return markets
    for m in markets:
        d = corr.get((sport, m.get("grupo")))
        if d:
            m["prob"] = _sigmoid(_logit(float(m["prob"])) + d)
    return markets
