import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.evaluation.model_health import football_health  # noqa: E402
from core.database.meta import stamp_meta  # noqa: E402
from sports.football.models import load_model  # noqa: E402

FEATURES_CSV = ROOT / "data" / "processed" / "football_features.csv"
GLM_PATH = ROOT / "data" / "models" / "football_poisson_v1.json"
TEST_SEASON = "2024-2025"
RECENT_DAYS = 90
MIN_RECENT = 150
DRIFT_FACTOR = 1.15


def main() -> int:
    if not FEATURES_CSV.exists() or not GLM_PATH.exists():
        print("[skip] faltan features o modelo.")
        return 0

    df = pd.read_csv(FEATURES_CSV, parse_dates=["date"])
    model = load_model(GLM_PATH)

    test = df[df["season"] == TEST_SEASON].dropna(subset=["home_goals", "away_goals"])
    baseline = football_health(model, test)["log_loss"] if len(test) >= 200 else None

    cutoff = pd.Timestamp(datetime.now(timezone.utc).date() - timedelta(days=RECENT_DAYS))
    recent = df[(df["date"] >= cutoff)].dropna(subset=["home_goals", "away_goals"])
    hr = football_health(model, recent)

    if hr["n"] < MIN_RECENT or baseline is None:
        status = "insufficient"
    elif hr["log_loss"] > baseline * DRIFT_FACTOR:
        status = "degraded"
    else:
        status = "ok"

    payload = {
        "status": status,
        "recent_log_loss": round(hr["log_loss"], 4) if hr["n"] else None,
        "baseline_log_loss": round(baseline, 4) if baseline else None,
        "n_recent": hr["n"],
        "window_days": RECENT_DAYS,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    stamp_meta("model_health", json.dumps(payload))

    print("=" * 56)
    print(f"  SALUD DEL MODELO (fútbol) — {status.upper()}")
    print("=" * 56)
    print(f"  Recientes ({RECENT_DAYS}d): n={hr['n']}  log-loss={payload['recent_log_loss']}")
    print(f"  Línea base (hold-out)   : {payload['baseline_log_loss']}")
    if status == "degraded":
        print("  ⚠️  El modelo se ha degradado -> conviene re-entrenar (retrain_all.py).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
