import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from core.database.meta import stamp_meta  # noqa: E402
from core.history import store, summary  # noqa: E402

def _step(label: str, fn, default=None):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] {label}: {type(e).__name__}")
        return default


def _scores(day: date) -> tuple:
    from core.fixtures.football import finished_scores
    from core.fixtures.mlb import finished_boxscores

    fb = _step("marcadores fútbol", lambda: finished_scores(day), [])
    mlb = _step("boxscores MLB", lambda: finished_boxscores(day), [])
    scores = {f"football:{s['date']}:{s['home']}:{s['away']}": f"{s['home_goals']}-{s['away_goals']}"
              for s in fb}
    scores.update({f"baseball:{b['date']}:{b['home']}:{b['away']}": f"{b['home_runs']}-{b['away_runs']}"
                   for b in mlb})
    return fb, mlb, scores


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Resumen diario de aciertos + keep-alive de la BD.")
    ap.add_argument("--date", help="YYYY-MM-DD (por defecto, hoy en SUMMARY_TZ)")
    args = ap.parse_args()
    tz = ZoneInfo(summary.TZ_NAME)
    day = date.fromisoformat(args.date) if args.date else summary.today_local()

    try:
        engine = get_sqlalchemy_engine()
        with engine.connect() as con:
            con.exec_driver_sql("SELECT 1")
    except Exception as e:  # noqa: BLE001
        # Logs públicos: nunca imprimir el mensaje (incluye host y usuario).
        print(f"[ERR] Sin conexión a la BD ({type(e).__name__}). Revisa el secret DB_URL.")
        return 1
    print(f"BD OK · resumen del {day} ({tz.key})")

    fb, mlb, scores = _scores(day)
    r1 = _step("resolver fútbol (feed)", lambda: store.resolve_football_from_scores(fb), {})
    r2 = _step("resolver MLB (feed)", lambda: store.resolve_baseball_from_boxscores(mlb), {})
    r3 = _step("resolver fútbol (tabla)", store.resolve_football_pending, {})
    r4 = _step("resolver MLB (tabla)", store.resolve_baseball_pending, {})
    print("resueltas:", sum(int((r or {}).get("resueltas", 0)) for r in (r1, r2, r3, r4)))

    s = _step("construir resumen", lambda: summary.build(engine, day, scores))
    if s is None:
        return 1
    ok = summary.save(s)
    pruned = _step("limpieza", summary.prune, 0)
    stamp_meta("last_keepalive", datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z"))

    t = s["totals"]
    print(f"guardado={ok} · partidos={t['matches']} (resueltos {t['resolved_matches']}) · "
          f"aciertos={t['hits']}/{t['resolved']} · pick principal={t['main_hits']}/{t['main_resolved']} · "
          f"borrados={pruned}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
