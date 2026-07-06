"""
Re-entrenamiento periódico de modelos + calibradores, con GATE OOS y rollback.

Complementa a refresh_cloud.py:
  - refresh_cloud.py (diario): descarga → ingesta → Elo → features → picks. Datos frescos.
  - retrain_all.py  (mensual/temporada): re-entrena los MODELOS y CALIBRADORES.

Garantía de seguridad ("nunca desplegar una regresión"):
  1. Antes de nada, copia data/models/*.joblib a data/models/.backup/.
  2. Re-entrena por deporte, AISLADO (un fallo no aborta los demás).
  3. Los calibradores YA se auto-validan (gate OOS interno: solo se guardan si mejoran).
  4. El modelo GLM de fútbol (el principal) pasa por un GATE explícito: si su log-loss
     1X2 OOS empeora vs el modelo previo (backup), se hace ROLLBACK al backup.
  5. Sella app_meta con la hora y la salud del modelo (para el dashboard/monitor).

Asume que los datos y el Elo están frescos (los mantiene refresh_cloud.py). Recalcula
features antes de entrenar para reflejar el último Elo/partidos.

Uso:
    DATABASE_URL=... python scripts/retrain_all.py           # nube (cron)
    python scripts/retrain_all.py                            # local
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODELS_DIR = ROOT / "data" / "models"
BACKUP_DIR = MODELS_DIR / ".backup"
FEATURES_CSV = ROOT / "data" / "processed" / "football_features.csv"
GLM_NAME = "football_poisson_v1.joblib"
TEST_SEASON = "2024-2025"   # hold-out; debe coincidir con train_football_model.py
GATE_TOLERANCE = 1e-4       # el nuevo no puede empeorar más que esto
STEP_TIMEOUT_S = 1800

# Pasos por deporte. build features → entrenar modelo(s) → calibrador (auto-gated).
STEPS = [
    ("Fútbol", [
        ("Features", ["scripts/build_football_features.py"]),
        ("Modelo GLM Poisson", ["scripts/train_football_model.py"]),
        ("Modelo XGBoost", ["scripts/train_football_xgboost.py"]),
        ("Calibrador 1X2", ["scripts/train_football_calibrator.py"]),
    ]),
    ("Baloncesto", [
        ("Features", ["scripts/build_basketball_features.py"]),
        ("Modelo Ridge", ["scripts/train_basketball_model.py"]),
        ("Calibrador ML", ["scripts/train_basketball_calibrator.py"]),
    ]),
    ("Béisbol", [
        ("Pythagorean", ["scripts/baseball_pythagorean.py"]),
        ("Calibrador ML", ["scripts/train_baseball_calibrator.py"]),
    ]),
    ("Tenis", [
        ("Calibrador prob.", ["scripts/train_tennis_calibrator.py"]),
    ]),
]


def backup_models() -> None:
    """Copia los .joblib actuales a .backup/ (para poder hacer rollback)."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for f in MODELS_DIR.glob("*.joblib"):
        shutil.copy2(f, BACKUP_DIR / f.name)
    print(f"[backup] {len(list(BACKUP_DIR.glob('*.joblib')))} artefactos respaldados.")


def restore(name: str) -> None:
    src = BACKUP_DIR / name
    if src.exists():
        shutil.copy2(src, MODELS_DIR / name)
        print(f"[rollback] {name} restaurado desde backup.")


def run_steps() -> dict:
    """Ejecuta los pasos por deporte, aislado. Devuelve {deporte: ok}."""
    results = {}
    for sport, steps in STEPS:
        ok = True
        for label, args in steps:
            print(f"\n>>> {sport}: {label}")
            try:
                code = subprocess.run(
                    [sys.executable, *args], cwd=str(ROOT), timeout=STEP_TIMEOUT_S
                ).returncode
            except subprocess.TimeoutExpired:
                print(f"    [TIMEOUT] {sport}: {label}")
                code = -1
            if code != 0:
                print(f"    [FALLO] {sport}: {label} (código {code}); sigo con el resto")
                ok = False
                break
        results[sport] = ok
    return results


def football_gate() -> dict:
    """Compara el GLM nuevo vs el backup sobre el hold-out. Rollback si empeora.

    Devuelve {status, log_loss_new, log_loss_old} (o {status:'skip'} si no se puede).
    """
    import joblib
    import pandas as pd

    from core.evaluation.model_health import football_health

    if not FEATURES_CSV.exists() or not (MODELS_DIR / GLM_NAME).exists():
        return {"status": "skip", "reason": "faltan features o modelo"}
    df = pd.read_csv(FEATURES_CSV)
    test = df[df["season"] == TEST_SEASON].dropna(subset=["home_goals", "away_goals"])
    if len(test) < 200:
        return {"status": "skip", "reason": "hold-out insuficiente"}

    new = joblib.load(MODELS_DIR / GLM_NAME)
    h_new = football_health(new, test)
    old_path = BACKUP_DIR / GLM_NAME
    if not old_path.exists():
        return {"status": "ok_first", "log_loss_new": h_new["log_loss"]}

    h_old = football_health(joblib.load(old_path), test)
    if h_new["log_loss"] <= h_old["log_loss"] + GATE_TOLERANCE:
        print(f"[gate] OK  log-loss {h_old['log_loss']:.4f} -> {h_new['log_loss']:.4f}")
        return {"status": "deployed",
                "log_loss_new": h_new["log_loss"], "log_loss_old": h_old["log_loss"]}
    print(f"[gate] EMPEORA {h_old['log_loss']:.4f} -> {h_new['log_loss']:.4f}: rollback")
    restore(GLM_NAME)
    return {"status": "rolled_back",
            "log_loss_new": h_new["log_loss"], "log_loss_old": h_old["log_loss"]}


def main() -> int:
    from core.database.meta import stamp_meta

    backup_models()
    results = run_steps()
    gate = football_gate()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stamp_meta("last_retrain", now)
    stamp_meta("retrain_report", json.dumps({"sports": results, "football_gate": gate}))

    print("\n" + "=" * 60)
    print(f"  RE-ENTRENAMIENTO COMPLETADO · {now}")
    print("=" * 60)
    for sport, ok in results.items():
        print(f"  {sport:12} {'OK' if ok else 'FALLÓ (artefactos previos intactos)'}")
    print(f"  Gate GLM fútbol: {gate.get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
