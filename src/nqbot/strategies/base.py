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

from ..backtesting.models import Signal
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
