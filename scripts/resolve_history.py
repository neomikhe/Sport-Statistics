"""
Resuelve el historial de predicciones y caduca lo antiguo.

Pensado para el cron (tras el refresco de datos): cuando llegan resultados nuevos,
marca acierto/fallo de las predicciones pendientes y borra las de más de N meses.

Uso:
    DATABASE_URL=... python scripts/resolve_history.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, timedelta  # noqa: E402

from core.fixtures.mlb import finished_boxscores  # noqa: E402
from core.fixtures.football import finished_scores  # noqa: E402
from core.history.store import (resolve_football_pending,  # noqa: E402
                                resolve_baseball_pending,
                                resolve_football_from_scores,
                                resolve_baseball_from_boxscores, expire_old)

EXPIRE_MONTHS = 3


def main() -> int:
    # Mismo día (rápido): boxscores statsapi + marcadores football-data.org (hoy + ayer).
    t = date.today()
    boxes = finished_boxscores(t) + finished_boxscores(t - timedelta(days=1))
    scores = finished_scores(t) + finished_scores(t - timedelta(days=1))
    sd_f = resolve_football_from_scores(scores)
    sd_b = resolve_baseball_from_boxscores(boxes)
    print(f"Mismo día: {sd_f['resueltas']} fútbol + {sd_b['resueltas']} béisbol")

    # Fallback por BD (córners/tarjetas por CSV, béisbol por Retrosheet).
    rf = resolve_football_pending()
    print(f"Fútbol (CSV): {rf['resueltas']} resueltas · push borradas: {rf['push_borradas']}")
    rb = resolve_baseball_pending()
    print(f"Béisbol (Retrosheet): {rb['resueltas']} resueltas")
    n = expire_old(months=EXPIRE_MONTHS)
    print(f"Caducadas (>{EXPIRE_MONTHS} meses, borradas): {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
