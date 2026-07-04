"""Estado de la cuenta: capital inicial + PnL realizado acumulado.

El equity mark-to-market (con flotante de la posición abierta) lo calcula
el motor barra a barra; acá solo vive el estado realizado, que es lo que
usan el position sizing y los límites de riesgo.
"""

from __future__ import annotations

from ..backtesting.models import Trade


class Account:
    def __init__(self, initial_capital: float) -> None:
        if initial_capital <= 0:
            raise ValueError(f"Capital inicial inválido: {initial_capital}")
        self.initial_capital = initial_capital
        self.realized_pnl = 0.0
        self.trades_count = 0

    @property
    def equity(self) -> float:
        """Equity realizado (sin flotante)."""
        return self.initial_capital + self.realized_pnl

    def apply_trade(self, trade: Trade) -> None:
        self.realized_pnl += trade.pnl_net
        self.trades_count += 1
