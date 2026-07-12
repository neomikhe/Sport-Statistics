"""
Registra en el historial las 10 situaciones más probables de los partidos de HOY.

Atajo para ejecutar solo ese paso a mano; el cron ya lo hace dentro de
refresh_cloud.py. Descarga los fixtures del día (MLB + fútbol), computa el top-10
de cada uno y lo guarda en match_predictions. Idempotente.

Uso:
    DATABASE_URL=... python scripts/log_todays_fixtures.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.refresh_cloud import log_todays_fixtures  # noqa: E402


def main() -> int:
    n = log_todays_fixtures()
    print(f"[OK] {n} partidos registrados en el historial de hoy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
