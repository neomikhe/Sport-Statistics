"""
Diagnostico de calibracion (reliability) del modelo de futbol.

Lee data/processed/football_backtest_predictions.csv generado por backtest_football.py
y agrupa las predicciones en bins de probabilidad. Para cada bin compara la
probabilidad media predicha con la frecuencia observada.

Si el modelo esta bien calibrado, pred_mean deberia ser aproximadamente igual
a freq_obs en cada bin (reliability diagonal).

Uso:
    venv\\Scripts\\activate
    python scripts/football_reliability_plot.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluation.metrics import calibration_table  # noqa: E402


LABEL_NAMES = {"H": "Home (local)", "D": "Draw (empate)", "A": "Away (visitante)"}


def _ascii_bar(value: float, width: int = 30) -> str:
    """Barra ASCII con longitud proporcional a value en [0, 1]."""
    filled = int(round(value * width))
    return "#" * filled + "." * (width - filled)


def main():
    root = Path(__file__).resolve().parent.parent
    preds_path = root / "data" / "processed" / "football_backtest_predictions.csv"

    if not preds_path.exists():
        print("[ERR] No existe football_backtest_predictions.csv")
        print("      Ejecuta antes: python scripts/backtest_football.py")
        return 1

    df = pd.read_csv(preds_path)
    probs = df[["prob_home", "prob_draw", "prob_away"]].values
    outcomes = df["outcome"].values

    print(f"Evaluando calibracion sobre {len(df):,} predicciones del backtest")
    table = calibration_table(probs, outcomes, n_bins=10)

    global_errors = {}

    for label in ["H", "D", "A"]:
        sub = table[table["outcome"] == label].copy()
        if sub.empty:
            continue
        sub["delta"] = sub["freq_obs"] - sub["mean_pred"]

        print()
        print("=" * 88)
        print(f"  CLASE: {label} ({LABEL_NAMES[label]})")
        print("=" * 88)
        print(f"  {'bin':<16}{'n':>7}  {'pred_mean':>10}  {'freq_obs':>10}  {'delta':>9}")
        print(f"  {'-' * 16}{'-' * 7}  {'-' * 10}  {'-' * 10}  {'-' * 9}")
        for _, r in sub.iterrows():
            bin_str = f"[{r['bin_low']:.2f}, {r['bin_high']:.2f})"
            delta_str = f"{r['delta']:+.3f}"
            print(
                f"  {bin_str:<16}{int(r['n']):>7}  {r['mean_pred']:>10.3f}  "
                f"{r['freq_obs']:>10.3f}  {delta_str:>9}"
            )

        weighted_error = float((sub["delta"].abs() * sub["n"]).sum() / sub["n"].sum())
        global_errors[label] = weighted_error

        print(f"\n  Error absoluto ponderado de calibracion: {weighted_error:.4f}")
        if weighted_error < 0.020:
            verdict = "EXCELENTE"
        elif weighted_error < 0.040:
            verdict = "BUENA"
        elif weighted_error < 0.080:
            verdict = "REGULAR (hay margen)"
        else:
            verdict = "MALA (revisar modelo)"
        print(f"  Veredicto: {verdict}")

    # Resumen global
    print()
    print("=" * 88)
    print("  RESUMEN GLOBAL DE CALIBRACION")
    print("=" * 88)
    for label, err in global_errors.items():
        print(f"  {LABEL_NAMES[label]:<20}  error absoluto ponderado: {err:.4f}")

    avg = sum(global_errors.values()) / len(global_errors) if global_errors else 0
    print(f"  Media 3 clases:        {avg:.4f}")
    print()
    print("  Referencia:")
    print("    < 0.020 -> calibracion excelente (no necesita isotonic)")
    print("    0.020-0.040 -> buena (isotonic puede mejorar en muestras grandes)")
    print("    0.040-0.080 -> regular (isotonic ayuda)")
    print("    > 0.080 -> mala (revisar features o modelo)")

    print()
    print("[OK] Diagnostico de calibracion completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
