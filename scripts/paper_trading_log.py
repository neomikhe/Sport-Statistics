"""
Sistema de paper trading para registrar picks y simular bankroll en el tiempo.

Lee picks de un CSV (data/processed/picks_football_*.csv generado por el pipeline)
y los registra en data/paper_trading/log.csv con timestamp.

Cuando los partidos terminen, la columna 'real_result' se rellena automaticamente
con un join contra football_matches en BD.

Uso:
    # Importar nuevos picks de un CSV (idempotente: no duplica)
    python scripts/paper_trading_log.py import data/processed/picks_football_2025-2026.csv

    # Actualizar resultados desde la BD
    python scripts/paper_trading_log.py update

    # Mostrar stats del log
    python scripts/paper_trading_log.py stats
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import get_sqlalchemy_engine  # noqa: E402
from core.betting.bankroll import BankrollTracker  # noqa: E402


LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "paper_trading" / "log.csv"
INITIAL_BANKROLL = 1000.0


def _ensure_log_exists():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        empty = pd.DataFrame(columns=[
            "logged_at", "pick_date", "league", "home", "away",
            "selection", "prob_model", "odds", "ev", "stake",
            "real_result", "won", "settled_at",
        ])
        empty.to_csv(LOG_PATH, index=False)


def cmd_import(picks_path: Path):
    _ensure_log_exists()
    if not picks_path.exists():
        print(f"[ERR] No existe {picks_path}")
        return 1

    new_picks = pd.read_csv(picks_path, parse_dates=["date"])
    log = pd.read_csv(LOG_PATH, parse_dates=["logged_at", "pick_date", "settled_at"])

    # Clave de unicidad: (pick_date, home, away, selection)
    if not log.empty:
        existing = set(zip(
            log["pick_date"].dt.strftime("%Y-%m-%d"),
            log["home"], log["away"], log["selection"],
        ))
    else:
        existing = set()

    rows = []
    now = datetime.now().isoformat(timespec="seconds")
    for _, p in new_picks.iterrows():
        key = (
            p["date"].strftime("%Y-%m-%d"),
            p["home"], p["away"], p["selection"],
        )
        if key in existing:
            continue
        rows.append({
            "logged_at": now,
            "pick_date": p["date"].strftime("%Y-%m-%d"),
            "league": p["league"],
            "home": p["home"],
            "away": p["away"],
            "selection": p["selection"],
            "prob_model": float(p["prob_model"]),
            "odds": float(p["odds"]),
            "ev": float(p["ev"]),
            "stake": float(p["stake"]),
            "real_result": p.get("real_result", "pending"),
            "won": None,
            "settled_at": None,
        })

    if not rows:
        print(f"[OK] Sin picks nuevos para importar ({len(new_picks)} ya existian).")
        return 0

    log = pd.concat([log, pd.DataFrame(rows)], ignore_index=True)
    log.to_csv(LOG_PATH, index=False)
    print(f"[OK] Importados {len(rows)} picks nuevos. Total log: {len(log)}.")
    return 0


def cmd_update():
    """Actualiza 'won' y 'real_result' consultando football_matches en BD."""
    _ensure_log_exists()
    log = pd.read_csv(LOG_PATH, parse_dates=["pick_date"])
    if log.empty:
        print("[OK] Log vacio, nada que actualizar.")
        return 0

    # Cast columnas que mezclan NaN + bool/str a object (pandas 3.x es estricto)
    for col in ("won", "settled_at", "real_result"):
        if col in log.columns:
            log[col] = log[col].astype(object)

    pending = log[log["won"].isna()].copy()
    if pending.empty:
        print("[OK] Todos los picks ya tienen resultado.")
        return 0

    print(f"Actualizando {len(pending)} picks pendientes desde BD...")

    engine = get_sqlalchemy_engine()
    matches = pd.read_sql(
        """
        SELECT m.date, h.name AS home, a.name AS away, m.home_goals, m.away_goals
        FROM football_matches m
        JOIN entities h ON h.id = m.home_team_id
        JOIN entities a ON a.id = m.away_team_id
        WHERE m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        """,
        engine,
        parse_dates=["date"],
    )
    matches["date_str"] = matches["date"].dt.strftime("%Y-%m-%d")

    n_updated = 0
    now = datetime.now().isoformat(timespec="seconds")
    for idx, p in pending.iterrows():
        date_str = p["pick_date"].strftime("%Y-%m-%d")
        m = matches[
            (matches["date_str"] == date_str)
            & (matches["home"] == p["home"])
            & (matches["away"] == p["away"])
        ]
        if m.empty:
            continue
        hg, ag = int(m.iloc[0]["home_goals"]), int(m.iloc[0]["away_goals"])
        won = (
            (p["selection"] == "HOME" and hg > ag)
            or (p["selection"] == "DRAW" and hg == ag)
            or (p["selection"] == "AWAY" and hg < ag)
        )
        log.at[idx, "real_result"] = f"{hg}-{ag}"
        log.at[idx, "won"] = bool(won)
        log.at[idx, "settled_at"] = now
        n_updated += 1

    log.to_csv(LOG_PATH, index=False)
    print(f"[OK] {n_updated} picks actualizados.")
    return 0


def cmd_stats():
    _ensure_log_exists()
    log = pd.read_csv(LOG_PATH, parse_dates=["logged_at", "pick_date"])
    if log.empty:
        print("Log vacio.")
        return 0

    print(f"Total picks en log: {len(log):,}")
    settled = log[log["won"].notna()].copy()
    pending = log[log["won"].isna()].copy()
    print(f"  Settled: {len(settled):,}")
    print(f"  Pending: {len(pending):,}")

    if settled.empty:
        print("Aun no hay picks settled. Ejecuta 'update' tras los partidos.")
        return 0

    bk = BankrollTracker(initial=INITIAL_BANKROLL)
    settled_sorted = settled.sort_values("pick_date")
    for _, p in settled_sorted.iterrows():
        bk.place_bet(
            stake=float(p["stake"]),
            odds=float(p["odds"]),
            won=bool(p["won"]),
            date=p["pick_date"],
        )

    print()
    print("=" * 60)
    print("  STATS DE BANKROLL (sobre picks settled)")
    print("=" * 60)
    print(f"  Bankroll inicial:    {INITIAL_BANKROLL:,.2f}")
    print(f"  Bankroll actual:     {bk.current:,.2f}")
    print(f"  ROI:                 {bk.roi * 100:+.2f} %")
    print(f"  ROI sobre turnover:  {bk.roi_turnover * 100:+.2f} %")
    print(f"  Hit-rate:            {bk.hit_rate * 100:.1f} %")
    print(f"  Total apostado:      {bk.total_staked:,.2f}")
    print(f"  Picks ganados:       {sum(1 for h in bk._history if h['won'])}")
    print(f"  Picks perdidos:      {sum(1 for h in bk._history if not h['won'])}")
    print(f"  Max drawdown:        {bk.max_drawdown * 100:.1f} %")
    print(f"  Peak bankroll:       {bk.peak:,.2f}")

    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1].lower()
    if cmd == "import":
        if len(sys.argv) < 3:
            print("Uso: paper_trading_log.py import <picks_csv>")
            return 1
        return cmd_import(Path(sys.argv[2]))
    elif cmd == "update":
        return cmd_update()
    elif cmd == "stats":
        return cmd_stats()
    else:
        print(f"Comando desconocido: {cmd}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
