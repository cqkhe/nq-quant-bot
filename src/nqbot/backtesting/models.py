"""Modelos de dominio compartidos por estrategia, motor, riesgo y ejecución.

Convención de dirección: +1 = long, -1 = short.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

LONG = 1
SHORT = -1


@dataclass(frozen=True)
class Signal:
    """Intención de entrada emitida por una estrategia al cierre de una barra.

    El precio de entrada NO viene en la señal: la ejecución es a mercado en
    el open de la barra siguiente (lo decide el simulador, no la estrategia).
    """

    time: datetime
    direction: int          # LONG (+1) o SHORT (-1)
    stop_price: float       # stop técnico absoluto
    rr: float               # take profit = rr * distancia al stop, desde el fill real
    reason: str             # etiqueta auditable del setup


@dataclass(frozen=True)
class PendingEntry:
    """Señal aprobada por riesgo, esperando el open de la próxima barra."""

    signal: Signal
    contracts: int


@dataclass
class Position:
    """Posición abierta."""

    direction: int
    contracts: int
    entry_time: datetime
    entry_price: float
    stop_price: float
    target_price: float
    initial_risk_dollars: float  # (entry - stop) * point_value * contratos
    reason: str

    def unrealized(self, mark_price: float, point_value: float) -> float:
        return (mark_price - self.entry_price) * self.direction * point_value * self.contracts


@dataclass(frozen=True)
class Trade:
    """Operación cerrada, con toda la información para auditoría y métricas."""

    symbol: str
    direction: int
    contracts: int
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    stop_price: float
    target_price: float
    exit_reason: str          # "stop" | "stop_gap" | "target" | "target_gap" | "session_flatten"
    pnl_gross: float
    commission: float
    pnl_net: float
    initial_risk_dollars: float
    r_multiple: float         # pnl_net / riesgo inicial
    bars_held: int
    reason: str               # etiqueta del setup que originó la entrada


@dataclass
class BacktestResult:
    """Salida completa de una corrida de backtest."""

    symbol: str
    strategy_name: str
    initial_capital: float
    trades: list[Trade]
    equity_curve: pd.Series          # equity mark-to-market por barra
    skipped_signals: dict[str, int]  # motivo -> cantidad de señales descartadas
    start: datetime
    end: datetime
    params: dict[str, Any] = field(default_factory=dict)
