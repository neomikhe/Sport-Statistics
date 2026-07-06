"""
Genera picks de futbol con EV positivo usando:
    1. Modelo GLM Poisson entrenado (data/models/football_poisson_v1.joblib).
    2. Features precalculadas.
    3. Probabilidades 1X2 exactas (Poisson independiente).
    4. EV = prob * cuota - 1, filtra picks con EV >= MIN_EV_THRESHOLD (.env).
    5. Stake sugerido via Kelly fraccional (1/4 Kelly, cap 5 % del bankroll).

Si los partidos tienen resultado en BD, simula el bankroll y muestra ROI.

Uso:
    venv\\Scripts\\activate
    python scripts/generate_football_picks.py                 # default: 2025-2026
    python scripts/generate_football_picks.py 2024-2025       # temporada explicita
"""
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from sports.football.models import HOME_MODEL_FEATURES, AWAY_MODEL_FEATURES  # noqa: E402
from sports.football.simulation import exact_probabilities  # noqa: E402
from sports.football.dixon_coles import exact_probabilities_dc  # noqa: E402
from core.betting.kelly import kelly_fractional  # noqa: E402

load_dotenv()

MIN_EV = float(os.getenv("MIN_EV_THRESHOLD", "0.03"))
MAX_EV = float(os.getenv("MAX_EV_THRESHOLD", "0.25"))      # cap anti-overconfidence
KELLY_FRAC = float(os.getenv("KELLY_FRACTION", "0.25"))
BANKROLL = float(os.getenv("BANKROLL_INITIAL", "1000"))
MAX_STAKE_PCT = 0.05

# Filtros de cuota: elimina longshots (el 90% del bias de seleccion esta aqui)
# y heavy favorites (margen insuficiente)
ODDS_MIN = float(os.getenv("ODDS_MIN", "1.40"))
ODDS_MAX = float(os.getenv("ODDS_MAX", "3.50"))

# Stop-loss: si el bankroll cae por debajo de este % del inicial, paramos.
STOP_LOSS_PCT = 0.20

# Dixon-Coles: corrige subestimacion de empates pero EMPEORA el ROI cuando se
# combina con filtros bajos de EV (introduce mas picks DRAW marginales).
# Default desactivado. Activable con USE_DC=1 en .env para comparar.
USE_DC = os.getenv("USE_DC", "0") == "1"
DC_RHO = float(os.getenv("DC_RHO", "-0.13"))  # tipico para futbol europeo


def main():
    target_season = sys.argv[1] if len(sys.argv) > 1 else "2025-2026"

    root = Path(__file__).resolve().parent.parent
    features_path = root / "data" / "processed" / "football_features.csv"
    model_path = root / "data" / "models" / "football_poisson_v1.joblib"

    if not features_path.exists() or not model_path.exists():
        print("[ERR] Faltan artefactos. Ejecuta antes:")
        print("      python scripts/build_football_features.py")
        print("      python scripts/train_football_model.py")
        return 1

    print(f"Generando picks para temporada: {target_season}")
    print(f"  EV minimo:         {MIN_EV:.3f}")
    print(f"  EV maximo:         {MAX_EV:.3f}   (anti-overconfidence)")
    print(f"  Cuota minima:      {ODDS_MIN:.2f}   (anti-heavy-fav)")
    print(f"  Cuota maxima:      {ODDS_MAX:.2f}   (anti-longshot)")
    print(f"  Kelly fraccional:  {KELLY_FRAC}")
    print(f"  Bankroll base:     {BANKROLL:.2f}")
    print(f"  Cap stake/pick:    {MAX_STAKE_PCT * 100:.1f} % del bankroll")
    print(f"  Stop-loss:         bank < {STOP_LOSS_PCT * 100:.0f} % del inicial")
    print(f"  Dixon-Coles:       {'ACTIVADO (rho=' + str(DC_RHO) + ')' if USE_DC else 'DESACTIVADO'}")

    df = pd.read_csv(features_path, parse_dates=["date"])
    model = joblib.load(model_path)

    engine = get_sqlalchemy_engine()
    ent = pd.read_sql("SELECT id, name FROM entities WHERE sport_id = 1", engine)
    name_by_id = dict(zip(ent["id"].tolist(), ent["name"].tolist()))

    all_feats = list(set(HOME_MODEL_FEATURES) | set(AWAY_MODEL_FEATURES))
    subset = df[
        (df["season"] == target_season)
        & df["odds_home_close"].notna()
        & df["odds_draw_close"].notna()
        & df["odds_away_close"].notna()
        & df[all_feats].notna().all(axis=1)
    ].copy()

    print(f"  Partidos candidatos: {len(subset):,}")

    if subset.empty:
        print("[WARN] No hay partidos candidatos.")
        return 0

    pred = model.predict_lambda(subset)
    subset["lambda_home"] = pred["lambda_home"].values
    subset["lambda_away"] = pred["lambda_away"].values

    probs = np.zeros((len(subset), 3))
    prob_fn = (
        (lambda lh, la: exact_probabilities_dc(lh, la, rho=DC_RHO))
        if USE_DC
        else exact_probabilities
    )
    for i in range(len(subset)):
        p = prob_fn(
            subset["lambda_home"].iloc[i],
            subset["lambda_away"].iloc[i],
        )
        probs[i] = [p["prob_home"], p["prob_draw"], p["prob_away"]]
    subset["prob_home"] = probs[:, 0]
    subset["prob_draw"] = probs[:, 1]
    subset["prob_away"] = probs[:, 2]

    subset["ev_home"] = subset["prob_home"] * subset["odds_home_close"] - 1.0
    subset["ev_draw"] = subset["prob_draw"] * subset["odds_draw_close"] - 1.0
    subset["ev_away"] = subset["prob_away"] * subset["odds_away_close"] - 1.0

    picks = []
    for _, r in subset.iterrows():
        for sel, p_col, o_col, ev_col in [
            ("HOME", "prob_home", "odds_home_close", "ev_home"),
            ("DRAW", "prob_draw", "odds_draw_close", "ev_draw"),
            ("AWAY", "prob_away", "odds_away_close", "ev_away"),
        ]:
            ev = r[ev_col]
            odds = r[o_col]
            if not (MIN_EV <= ev <= MAX_EV):
                continue
            if not (ODDS_MIN <= odds <= ODDS_MAX):
                continue
            f_k = min(
                kelly_fractional(r[p_col], odds, fraction=KELLY_FRAC),
                MAX_STAKE_PCT,
            )
            stake = BANKROLL * f_k
            picks.append({
                    "date": r["date"].date(),
                    "league": r["league"],
                    "home": name_by_id.get(r["home_team_id"], f"id={r['home_team_id']}"),
                    "away": name_by_id.get(r["away_team_id"], f"id={r['away_team_id']}"),
                    "selection": sel,
                    "prob_model": float(r[p_col]),
                    "odds": float(r[o_col]),
                    "ev": float(ev),
                    "kelly_frac": float(f_k),
                    "stake": float(stake),
                    "real_result": (
                        f"{int(r['home_goals'])}-{int(r['away_goals'])}"
                        if pd.notna(r.get("home_goals")) and pd.notna(r.get("away_goals"))
                        else "pending"
                    ),
                })

    if not picks:
        print(f"\n  (sin picks con EV >= {MIN_EV:.3f})")
        return 0

    picks_df = pd.DataFrame(picks).sort_values("ev", ascending=False).reset_index(drop=True)

    print(f"\n  PICKS ENCONTRADOS (EV >= {MIN_EV:.3f}): {len(picks_df)}")

    print()
    print("=" * 125)
    print(f"  TOP 20 PICKS POR EV")
    print("=" * 125)
    header = (f"  {'fecha':<11} {'liga':<16} {'local':<16} {'visit':<16} {'sel':<5} "
              f"{'prob':>5} {'cuota':>6} {'EV %':>6} {'stake':>8} {'real'}")
    print(header)
    print("  " + "-" * (len(header) - 2))

    for _, p in picks_df.head(20).iterrows():
        print(f"  {str(p['date']):<11} {p['league']:<16} {p['home'][:15]:<16} "
              f"{p['away'][:15]:<16} {p['selection']:<5} "
              f"{p['prob_model']:>5.3f} {p['odds']:>6.2f} "
              f"{p['ev'] * 100:>5.2f}% {p['stake']:>8.2f} {p['real_result']}")

    out_dir = root / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"picks_football_{target_season}.csv"
    picks_df.to_csv(out_file, index=False)
    print(f"\n[OK] {len(picks_df)} picks guardados en: {out_file}")

    # ---------- Simulacion bankroll compuesta (Kelly dinamico) ----------
    decided = picks_df[picks_df["real_result"] != "pending"].copy()
    if len(decided) > 0:
        print()
        print("=" * 125)
        print(f"  SIMULACION DE BANKROLL COMPUESTA ({len(decided)} picks decididos)")
        print("=" * 125)

        bank = BANKROLL
        peak = BANKROLL
        max_drawdown_pct = 0.0
        wins = losses = skipped = 0
        total_staked = 0.0
        total_returned = 0.0
        stop_loss_triggered = False

        for _, p in decided.sort_values("date").iterrows():
            if bank < BANKROLL * STOP_LOSS_PCT:
                skipped += 1
                stop_loss_triggered = True
                continue

            # Kelly sobre el bank VIVO, no el inicial
            f_live = min(
                kelly_fractional(p["prob_model"], p["odds"], fraction=KELLY_FRAC),
                MAX_STAKE_PCT,
            )
            stake_live = bank * f_live
            if stake_live <= 0:
                skipped += 1
                continue

            h, a = map(int, p["real_result"].split("-"))
            won = (
                (p["selection"] == "HOME" and h > a)
                or (p["selection"] == "DRAW" and h == a)
                or (p["selection"] == "AWAY" and h < a)
            )

            total_staked += stake_live
            if won:
                profit = stake_live * (p["odds"] - 1)
                bank += profit
                total_returned += stake_live + profit
                wins += 1
            else:
                bank -= stake_live
                losses += 1

            peak = max(peak, bank)
            dd_pct = (peak - bank) / peak * 100 if peak > 0 else 0.0
            max_drawdown_pct = max(max_drawdown_pct, dd_pct)

        n = wins + losses
        hit = 100 * wins / n if n else 0.0
        delta = bank - BANKROLL
        roi_bank = 100 * delta / BANKROLL
        roi_turn = 100 * (total_returned - total_staked) / total_staked if total_staked else 0.0

        print(f"  Apostados: {n}  |  Saltados por stop-loss: {skipped}")
        print(f"  Ganados: {wins}  |  Perdidos: {losses}  |  Hit-rate: {hit:.1f} %")
        print(f"  Total apostado (acumulado): {total_staked:,.2f}")
        print(f"  Bankroll inicial: {BANKROLL:,.2f}  ->  Final: {bank:,.2f}  (delta: {delta:+,.2f})")
        print(f"  ROI sobre bankroll: {roi_bank:+.2f} %")
        print(f"  ROI sobre turnover: {roi_turn:+.2f} %")
        print(f"  Peak bankroll: {peak:,.2f}  |  Max drawdown: {max_drawdown_pct:.1f} %")
        if stop_loss_triggered:
            print(f"  [!] Stop-loss activado durante la simulacion.")
        print()
        print("  AVISOS:")
        print("  - ROI > 0 en <500 picks puede ser suerte pura. Mira el ROI sobre turnover:")
        print("    cualquier valor entre -3% y +3% es consistente con 'no hay edge ni anti-edge'.")
        print("  - El 'edge real' solo se mide con CLV sostenido (cuota vs cierre de Pinnacle).")
        print("  - Si ves hit-rate <30 % con cuotas medias >3, estas haciendo longshot betting:")
        print("    endurece ODDS_MAX o sube MIN_EV.")

    print()
    print("[OK] Pipeline de picks completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
