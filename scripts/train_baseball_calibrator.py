"""
Entrena el calibrador isotónico binario del moneyline MLB.

Reproduce el Elo EXACTAMENTE como el pipeline (replay cronológico de baseball_games)
y usa la prob pre-partido -> por construcción es walk-forward (cada predicción solo
usa partidos anteriores). Se calibra tras un warm-up del 20 % inicial.

Requiere BD (lee baseball_games con el engine, igual que la app).
Guarda: data/models/baseball_calibrator_v1.joblib  (numpy puro, sin sklearn al cargar)

Uso:
    venv\\Scripts\\activate
    python scripts/train_baseball_calibrator.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.baseball.elo import BaseballEloSystem, expected_home_score  # noqa: E402
from core.calibration.isotonic import BinaryIsotonicCalibrator  # noqa: E402

WARMUP_FRACTION = 0.20


def _logloss(p, y) -> float:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _brier(p, y) -> float:
    return float(np.mean((p - y) ** 2))


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    out_path = root / "data" / "models" / "baseball_calibrator_v1.joblib"

    engine = get_sqlalchemy_engine()
    df = pd.read_sql(
        """
        SELECT g.date, g.home_team_id, g.away_team_id, g.home_runs, g.away_runs
        FROM baseball_games g
        WHERE g.home_runs IS NOT NULL AND g.away_runs IS NOT NULL
        ORDER BY g.date
        """,
        engine, parse_dates=["date"],
    )
    if len(df) < 500:
        print(f"[ERR] Pocos partidos en baseball_games: {len(df)}.")
        return 1
    print(f"Partidos leídos: {len(df):,}")

    elo = BaseballEloSystem()
    probs, outcomes = [], []
    for r in df.itertuples(index=False):
        season = str(r.date.year)                      # temporada MLB ≈ año natural
        eh, ea = elo.get(int(r.home_team_id)), elo.get(int(r.away_team_id))
        probs.append(expected_home_score(eh, ea))      # prob PRE-partido
        outcomes.append(1.0 if r.home_runs > r.away_runs else 0.0)
        elo.process_game(r.date, season, int(r.home_team_id), int(r.away_team_id),
                         int(r.home_runs), int(r.away_runs))

    probs, outcomes = np.array(probs), np.array(outcomes)
    start = int(len(probs) * WARMUP_FRACTION)          # descarta cold-start del Elo
    p_cal, y_cal = probs[start:], outcomes[start:]
    print(f"Partidos de calibración (tras warm-up {int(WARMUP_FRACTION*100)}%): {len(p_cal):,}")

    # --- Evaluación OUT-OF-SAMPLE: ajusta en 70% y mide en el 30% más reciente ---
    icut = int(len(p_cal) * 0.70)
    oos = BinaryIsotonicCalibrator().fit(p_cal[:icut], y_cal[:icut])
    ev_raw, ev_y = p_cal[icut:], y_cal[icut:]
    ev_cal = oos.transform(ev_raw)
    print("=" * 60)
    print("  CALIBRACIÓN MONEYLINE MLB — evaluación OUT-OF-SAMPLE (últ. 30%)")
    print("=" * 60)
    print(f"  Log-loss : {_logloss(ev_raw, ev_y):.4f}  ->  {_logloss(ev_cal, ev_y):.4f}")
    print(f"  Brier    : {_brier(ev_raw, ev_y):.4f}  ->  {_brier(ev_cal, ev_y):.4f}")

    # --- Gate: solo se despliega si MEJORA out-of-sample ---
    if _logloss(ev_cal, ev_y) < _logloss(ev_raw, ev_y):
        BinaryIsotonicCalibrator().fit(p_cal, y_cal).save(out_path)
        print(f"[OK] Mejora OOS confirmada -> calibrador guardado: {out_path}")
        print("     El analizador lo aplicará al moneyline MLB automáticamente.")
    else:
        if out_path.exists():
            out_path.unlink()
        print("[SKIP] La calibración NO mejora OOS -> no se despliega (se usa prob cruda).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
