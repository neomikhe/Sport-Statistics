"""
BankrollTracker: simula la evolucion del bankroll registrando apuesta a apuesta.

Uso:
    bk = BankrollTracker(initial=1000.0)
    bk.place_bet(stake=10.0, odds=2.10, won=True, date=date(2024, 9, 1))
    bk.place_bet(stake=12.0, odds=1.80, won=False, date=date(2024, 9, 8))
    print(bk.current, bk.roi, bk.max_drawdown)
    df_hist = bk.to_dataframe()
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional

import pandas as pd


@dataclass
class BankrollTracker:
    initial: float
    _current: float = field(init=False)
    _peak: float = field(init=False)
    _history: List[dict] = field(default_factory=list, init=False)

    def __post_init__(self):
        self._current = float(self.initial)
        self._peak = float(self.initial)

    # -------- API principal --------
    def place_bet(self, stake: float, odds: float, won: bool,
                  date: Optional[Any] = None, meta: Optional[dict] = None) -> None:
        """Registra el resultado de una apuesta y actualiza el bankroll."""
        stake = float(stake)
        odds = float(odds)
        before = self._current

        if won:
            profit = stake * (odds - 1.0)
            self._current += profit
            pnl = profit
        else:
            self._current -= stake
            pnl = -stake

        if self._current > self._peak:
            self._peak = self._current

        self._history.append({
            "date": date,
            "stake": stake,
            "odds": odds,
            "won": bool(won),
            "pnl": pnl,
            "bankroll_before": before,
            "bankroll_after": self._current,
            "meta": meta or {},
        })

    # -------- Propiedades de lectura --------
    @property
    def current(self) -> float:
        return self._current

    @property
    def peak(self) -> float:
        return self._peak

    @property
    def total_bets(self) -> int:
        return len(self._history)

    @property
    def roi(self) -> float:
        """ROI absoluto sobre bankroll inicial. Puede ser negativo."""
        if self.initial <= 0:
            return 0.0
        return (self._current - self.initial) / self.initial

    @property
    def hit_rate(self) -> float:
        """Fraccion de apuestas ganadas."""
        if not self._history:
            return 0.0
        return sum(1 for h in self._history if h["won"]) / len(self._history)

    @property
    def total_staked(self) -> float:
        return sum(h["stake"] for h in self._history)

    @property
    def roi_turnover(self) -> float:
        """ROI sobre turnover (por unidad apostada, no por bankroll)."""
        staked = self.total_staked
        if staked <= 0:
            return 0.0
        profit = sum(h["pnl"] for h in self._history)
        return profit / staked

    @property
    def max_drawdown(self) -> float:
        """Maximo drawdown relativo al peak a lo largo de la historia."""
        if not self._history:
            return 0.0
        running_peak = self.initial
        max_dd = 0.0
        for h in self._history:
            running_peak = max(running_peak, h["bankroll_after"])
            if running_peak > 0:
                dd = (running_peak - h["bankroll_after"]) / running_peak
                max_dd = max(max_dd, dd)
        return max_dd

    def to_dataframe(self) -> pd.DataFrame:
        """Historial como DataFrame para graficar curva / analizar."""
        return pd.DataFrame(self._history)
