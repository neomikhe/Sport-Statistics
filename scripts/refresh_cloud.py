"""
Refresco programado de datos para la nube (lo ejecuta el cron de GitHub Actions).

Escribe sobre la BD a la que apunte la conexion (BD en la nube en Actions vía
DATABASE_URL; PostgreSQL local si no). Pasos:

  1. Pipeline de fútbol (descarga → ingesta → Elo → features → picks).
  2. Carga los picks generados en la tabla `football_picks` (la app los lee de ahí).
  3. Sella `app_meta.last_refresh` con la hora UTC (la app muestra "última actualización").

Uso:
    # Cron / despliegue (refresco completo contra la BD en la nube):
    DATABASE_URL=... python scripts/refresh_cloud.py

    # Local / siembra rápida (sin re-correr el pipeline pesado, solo carga los
    # CSV de picks que ya existan en data/processed/ y sella la hora):
    python scripts/refresh_cloud.py --skip-pipeline
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database.connection import get_pg_connection, get_sqlalchemy_engine  # noqa: E402

PICKS_GLOB = "picks_football_*.csv"


def _today():
    return datetime.now(timezone.utc).date()


def _current_season() -> str:
    """Temporada de fútbol en curso, formato 'YYYY-YYYY' (arranca en agosto)."""
    t = _today()
    start = t.year if t.month >= 7 else t.year - 1
    return f"{start}-{start + 1}"


def _mlb_years() -> list:
    """Años MLB recientes. Retrosheet publica con retraso → previa + actual."""
    y = _today().year
    return [str(y - 1), str(y)]


def _tennis_years() -> list:
    """Años de tenis a (re)cargar. La ingesta de tenis es RECARGA TOTAL, así que
    hay que descargar toda la historia que queremos representar en cada refresco."""
    y = _today().year
    return [str(yr) for yr in range(2021, y + 1)]


CURRENT_SEASON = _current_season()

# Pipelines por deporte. Cada deporte se ejecuta AISLADO: si uno falla (p. ej.
# nba_api bloqueado en CI), los demás continúan y el refresco no se rompe.
SPORTS = [
    ("Fútbol", [
        ("Descarga CSVs", ["scripts/download_football_data.py"]),
        ("Ingesta histórico", ["scripts/ingest_football_history.py"]),
        ("Recalcula Elo", ["scripts/compute_football_elo.py"]),
        ("Construye features", ["scripts/build_football_features.py"]),
        ("Genera picks", ["scripts/generate_football_picks.py", CURRENT_SEASON]),
    ]),
    # NOTA: el baloncesto NO va aquí. nba_api bloquea las IPs de la nube, así que se
    # refresca EN LOCAL con `python scripts/refresh_nba_local.py` (IP residencial).
    ("Béisbol", [
        ("Descarga MLB", ["scripts/download_retrosheet_data.py", *_mlb_years()]),
        ("Stats de pitchers (FIP)", ["scripts/fetch_pitcher_stats.py", *_mlb_years()]),
        ("Abridores probables del día", ["scripts/fetch_mlb_lineups.py"]),
    ]),
    ("Tenis", [
        ("Descarga Sackmann", ["scripts/download_tennis_data.py", *_tennis_years()]),
        ("Ingesta tenis", ["scripts/ingest_tennis_data.py"]),
        ("Elo tenis", ["scripts/compute_tennis_elo.py"]),
    ]),
]

SCHEMA_V4 = ROOT / "core" / "database" / "schema_v4_app.sql"
SCHEMA_HISTORY = ROOT / "core" / "database" / "schema_history.sql"
SCHEMA_STATS = ROOT / "core" / "database" / "schema_stats.sql"


def ensure_schema() -> None:
    """Crea/actualiza football_picks, app_meta, match_predictions y las columnas de
    córners/tarjetas si no existen (idempotente).

    En la nube el rol tiene privilegio CREATE. En local, el usuario puede no
    tenerlo: en ese caso asumimos que las tablas ya existen y seguimos.
    """
    con = get_pg_connection()
    try:
        with con.cursor() as cur:
            cur.execute(SCHEMA_V4.read_text(encoding="utf-8"))
            if SCHEMA_HISTORY.exists():
                cur.execute(SCHEMA_HISTORY.read_text(encoding="utf-8"))
            if SCHEMA_STATS.exists():
                cur.execute(SCHEMA_STATS.read_text(encoding="utf-8"))
        con.commit()
        print("  schema (app + historial + córners/tarjetas) verificado/creado")
    except psycopg2.errors.InsufficientPrivilege:
        con.rollback()
        print("  [aviso] sin privilegio CREATE; asumo que las tablas ya existen.")
    finally:
        con.close()


TOTAL_STEPS = sum(len(steps) for _, steps in SPORTS) + 1  # todos los pasos + carga de picks
STEP_TIMEOUT_S = 1800  # 30 min por paso (evita cuelgues, p. ej. nba_api)


def run_all() -> dict:
    """Ejecuta cada deporte de forma aislada. Devuelve {deporte: True/False}.

    Un fallo en un deporte NO aborta el refresco: se registra y se sigue con el
    siguiente. Los datos previos de ese deporte quedan intactos (ingestas idempotentes).
    """
    results = {}
    step = 0
    for sport, steps in SPORTS:
        ok = True
        for label, args in steps:
            step += 1
            set_status("running", step, f"{sport}: {label}")
            print(f"\n>>> [{step}/{TOTAL_STEPS}] {sport}: {label}")
            try:
                code = subprocess.run(
                    [sys.executable, *args], cwd=str(ROOT), timeout=STEP_TIMEOUT_S
                ).returncode
            except subprocess.TimeoutExpired:
                print(f"    [TIMEOUT] {sport}: {label}")
                code = -1
            if code != 0:
                print(f"    [FALLO] {sport}: {label} (código {code}); continúo con el resto")
                ok = False
                break  # no seguir los pasos dependientes de este deporte
        results[sport] = ok
    return results


def _table_exists(name: str) -> bool:
    con = get_pg_connection()
    with con, con.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (f"public.{name}",))
        return cur.fetchone()[0] is not None


def load_picks() -> int:
    """Vuelca todos los picks_football_*.csv a football_picks (reemplazo total)."""
    if not _table_exists("football_picks"):
        raise SystemExit(
            "ERROR: la tabla 'football_picks' no existe y no se pudo crear "
            "(falta privilegio CREATE).\n"
            "  - En la nube: ejecuta con DATABASE_URL apuntando a la BD remota.\n"
            "  - En local: crea las tablas como admin -> "
            "psql -U postgres -d betstats -f core/database/schema_v4_app.sql"
        )
    processed = ROOT / "data" / "processed"
    files = sorted(processed.glob(PICKS_GLOB))
    if not files:
        print("[WARN] No hay CSV de picks que cargar.")
        return 0

    frames = []
    for f in files:
        season = f.stem.replace("picks_football_", "")
        df = pd.read_csv(f, parse_dates=["date"])
        df.insert(0, "season", season)
        frames.append(df)
    picks = pd.concat(frames, ignore_index=True)

    cols = ["season", "date", "league", "home", "away", "selection",
            "prob_model", "odds", "ev", "kelly_frac", "stake", "real_result"]
    picks = picks[cols]

    engine = get_sqlalchemy_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql("TRUNCATE football_picks RESTART IDENTITY")
        picks.to_sql("football_picks", conn, if_exists="append", index=False)
    return len(picks)


def log_todays_fixtures() -> int:
    """Registra el top-10 de situaciones de los partidos de HOY (MLB + fútbol).

    Idempotente (ON CONFLICT DO NOTHING). Devuelve cuántos partidos se registraron.
    """
    from core.fixtures import todays_fixtures
    from core.fixtures.match import attach_entity_ids
    from core.matchup import predict
    from core.predictions import top_situations
    from core.history.store import log_predictions

    engine = get_sqlalchemy_engine()
    today = _today()
    total = 0
    for sport in ("baseball", "football"):
        fixtures = attach_entity_ids(engine, sport, todays_fixtures(sport, today))
        for f in fixtures:
            if not (f.get("home_id") and f.get("away_id")):
                continue
            markets = predict(sport, engine, f["home_id"], f["away_id"], game_date=today)
            sits = top_situations(markets, 10) if markets else []
            if sits:
                log_predictions(sport, today, f["home"], f["away"],
                                sits, f["home_id"], f["away_id"])
                total += 1
    return total


def stamp_meta(key: str, value: str) -> None:
    con = get_pg_connection()
    with con, con.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_meta (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (key, value),
        )
    con.close()


def set_status(state: str, step: int, label: str) -> None:
    """Escribe el progreso del refresco en app_meta (best-effort; nunca rompe).

    La app lee app_meta['refresh_status'] (JSON) para pintar la barra de progreso.
    """
    payload = json.dumps({
        "state": state,          # running | done | error
        "step": step,
        "total": TOTAL_STEPS,
        "label": label,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    try:
        stamp_meta("refresh_status", payload)
    except Exception:
        pass


def main() -> int:
    skip_pipeline = "--skip-pipeline" in sys.argv

    ensure_schema()
    try:
        set_status("running", 0, "Iniciando")
        results = {}
        if not skip_pipeline:
            results = run_all()
        else:
            print("(--skip-pipeline: solo cargo picks existentes y sello la hora)")

        set_status("running", TOTAL_STEPS, "Cargando picks")
        n = load_picks()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        stamp_meta("last_refresh", now)

        # Historial (best-effort: nunca rompe el refresco):
        #   1. registra el top-10 de los partidos de hoy,
        #   2. resuelve las predicciones cuyos partidos ya terminaron,
        #   3. caduca las antiguas (>3 meses).
        try:
            logged = log_todays_fixtures()
            print(f"  historial: {logged} partidos de hoy registrados")
        except Exception as e:
            print(f"  [aviso] fixtures de hoy no registrados: {e}")
        try:
            # Resolución MISMO DÍA (hoy + ayer, por si algún partido terminó tarde
            # tras el refresco anterior). No espera a Retrosheet ni al CSV:
            #   béisbol -> boxscores de statsapi; fútbol -> marcadores de football-data.org.
            from datetime import timedelta
            from core.fixtures.mlb import finished_boxscores
            from core.fixtures.football import finished_scores
            from core.history.store import (resolve_baseball_from_boxscores,
                                            resolve_football_from_scores)
            t = _today()
            boxes = finished_boxscores(t) + finished_boxscores(t - timedelta(days=1))
            scores = finished_scores(t) + finished_scores(t - timedelta(days=1))
            sd_b = resolve_baseball_from_boxscores(boxes)
            sd_f = resolve_football_from_scores(scores)
            print(f"  historial (mismo día): {sd_f['resueltas']} fútbol + "
                  f"{sd_b['resueltas']} béisbol resueltas")
        except Exception as e:
            print(f"  [aviso] resolución mismo día: {e}")
        try:
            from core.history.store import (resolve_football_pending,
                                            resolve_baseball_pending, expire_old)
            rf = resolve_football_pending()
            rb = resolve_baseball_pending()
            expired = expire_old(months=3)
            print(f"  historial: {rf['resueltas']} fútbol + {rb['resueltas']} béisbol "
                  f"resueltas (Retrosheet/CSV), {expired} caducadas")
        except Exception as e:
            print(f"  [aviso] historial no procesado: {e}")

        failed = [s for s, ok in results.items() if not ok]
        if results:
            stamp_meta("refresh_sports", json.dumps(results))
        done_label = "Completado" if not failed else f"Completado · fallaron: {', '.join(failed)}"
        set_status("done", TOTAL_STEPS, done_label)

        print(f"\n[OK] {n} picks cargados. last_refresh = {now}")
        if failed:
            print(f"[AVISO] Deportes con fallo (datos previos intactos): {failed}")
        return 0
    except SystemExit:
        raise
    except Exception as e:
        set_status("error", 0, str(e)[:120])
        raise


if __name__ == "__main__":
    sys.exit(main())
