"""
Entrena el calibrador isotónico binario de la prob. de ganar en tenis.

Reproduce el Elo por superficie EXACTAMENTE como el pipeline (replay cronológico de
tennis_matches) y usa la prob pre-partido -> walk-forward por construcción. Se calibra
tras un warm-up del 20 % inicial.

Requiere BD (lee tennis_matches con el engine, igual que la app).
Guarda: data/models/tennis_calibrator_v1.joblib  (numpy puro, sin sklearn al cargar)

Uso:
    venv\\Scripts\\activate
    python scripts/train_tennis_calibrator.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.tennis.elo import TennisEloSystem, SURFACES, expected_score  # noqa: E402
from core.calibration.isotonic import BinaryIsotonicCalibrator  # noqa: E402

WARMUP_FRACTION = 0.20


def _logloss(p, y) -> float:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _brier(p, y) -> float:
    return float(np.mean((p - y) ** 2))


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    out_path = root / "data" / "models" / "tennis_calibrator_v1.joblib"

    engine = get_sqlalchemy_engine()
    df = pd.read_sql(
        """
        SELECT m.date, m.surface, m.player1_id, m.player2_id, m.winner_id
        FROM tennis_matches m
        WHERE m.surface IS NOT NULL AND m.winner_id IS NOT NULL
        ORDER BY m.date
        """,
        engine, parse_dates=["date"],
    )
    if df.empty:
        print("[ERR] No hay partidos en tennis_matches.")
        return 1
    df["surface"] = df["surface"].str.lower().str.strip()
    df = df[df["surface"].isin(SURFACES)].reset_index(drop=True)
    print(f"Partidos válidos: {len(df):,}")
    if len(df) < 500:
        print("[ERR] Pocos partidos para calibrar (>=500).")
        return 1

    elo = TennisEloSystem()
    probs, outcomes = [], []
    for r in df.itertuples(index=False):
        p1, p2 = int(r.player1_id), int(r.player2_id)
        e1, e2 = elo.get(p1, r.surface), elo.get(p2, r.surface)
        probs.append(expected_score(e1, e2))           # prob PRE-partido de player1
        outcomes.append(1.0 if int(r.winner_id) == p1 else 0.0)
        elo.process_match(r.date, r.surface, p1, p2, int(r.winner_id))

    probs, outcomes = np.array(probs), np.array(outcomes)
    start = int(len(probs) * WARMUP_FRACTION)
    p_cal, y_cal = probs[start:], outcomes[start:]
    print(f"Partidos de calibración (tras warm-up {int(WARMUP_FRACTION*100)}%): {len(p_cal):,}")

    # --- Evaluación OUT-OF-SAMPLE: ajusta en 70% y mide en el 30% más reciente ---
    icut = int(len(p_cal) * 0.70)
    oos = BinaryIsotonicCalibrator().fit(p_cal[:icut], y_cal[:icut])
    ev_raw, ev_y = p_cal[icut:], y_cal[icut:]
    ev_cal = oos.transform(ev_raw)
    print("=" * 60)
    print("  CALIBRACIÓN PROB. DE GANAR — TENIS (OUT-OF-SAMPLE, últ. 30%)")
    print("=" * 60)
    print(f"  Log-loss : {_logloss(ev_raw, ev_y):.4f}  ->  {_logloss(ev_cal, ev_y):.4f}")
    print(f"  Brier    : {_brier(ev_raw, ev_y):.4f}  ->  {_brier(ev_cal, ev_y):.4f}")

    # --- Gate: solo se despliega si MEJORA out-of-sample ---
    if _logloss(ev_cal, ev_y) < _logloss(ev_raw, ev_y):
        BinaryIsotonicCalibrator().fit(p_cal, y_cal).save(out_path)
        print(f"[OK] Mejora OOS confirmada -> calibrador guardado: {out_path}")
        print("     El analizador lo aplicará a la prob. de ganar de tenis automáticamente.")
    else:
        if out_path.exists():
            out_path.unlink()
        print("[SKIP] La calibración NO mejora OOS -> no se despliega (se usa prob cruda).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
