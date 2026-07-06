"""Contrato base de toda estrategia.

Separación de responsabilidades estricta:
  * La estrategia emite Signals (dirección + stop técnico + RR + motivo).
  * El tamaño de posición lo decide el Risk Manager, no la estrategia.
  * El precio de fill lo decide el Execution Simulator, no la estrategia.

Regla anti-lookahead: todo lo que `prepare` calcule para la barra t solo
puede usar información disponible al CIERRE de t. El motor ejecuta las
señales en el open de t+1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import pandas as pd

from ..backtesting.models import EarlyExitSignal, Signal, TradeState
from ..config.settings import ContractSpec


class Strategy(ABC):
    name: str = "abstract"

    def __init__(self, params: dict[str, Any] | None, contract: ContractSpec) -> None:
        self.params: dict[str, Any] = {**self.default_params(), **(params or {})}
        self.contract = contract

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {}

    @abstractmethod
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Precalcula indicadores/columnas de setup sobre el dataset completo."""

    @abstractmethod
    def signal_for_bar(self, ts: datetime, row: pd.Series) -> Signal | None:
        """Evalúa la barra t (ya preparada) y devuelve una señal o None."""

    def should_exit_early(
        self, ts: datetime, row: pd.Series, trade_state: TradeState
    ) -> EarlyExitSignal | None:
        """Hook OPCIONAL de salida dinámica dentro del trade.

        El motor lo llama al cierre de cada barra con posición abierta,
        DESPUÉS de evaluar stop/target/session_flatten (nunca los pisa).
        Recibe la barra preparada (indicadores incluidos) y un TradeState
        causal (MFE/MAE/mark solo con barras transcurridas). Si devuelve un
        EarlyExitSignal, la posición se cierra a mercado al cierre de esa
        barra (misma convención y costos que session_flatten) y el Trade
        registra exit_reason="early_exit".

        El default devuelve None: una estrategia que no lo implemente se
        comporta EXACTAMENTE igual que antes de esta extensión.
        """
        return None
