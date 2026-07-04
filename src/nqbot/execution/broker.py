"""Interfaz de broker para ejecución real — DESHABILITADA POR DISEÑO.

Fase 3 del roadmap. Este módulo define el contrato que deberá cumplir
cualquier adaptador de broker (Tradovate, IBKR, Rithmic...) y una guarda
de seguridad de doble llave:

  1. Variable de entorno LIVE_TRADING=true (archivo .env)
  2. live_trading: true en config/config.yaml

Si falta cualquiera de las dos, instanciar LiveBroker aborta con
RuntimeError. Y aunque estén ambas, hoy lanza NotImplementedError:
no existe código capaz de enviar órdenes reales todavía.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

from dotenv import load_dotenv

from ..config.settings import Config


class BrokerInterface(ABC):
    """Contrato mínimo de un adaptador de ejecución."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def submit_order(self, order: Any) -> str:
        """Envía una orden y devuelve su id."""

    @abstractmethod
    def flatten_all(self) -> None:
        """Cierra toda posición abierta de inmediato (kill switch)."""


class LiveBroker(BrokerInterface):
    """Placeholder de ejecución real. Ver la guarda de doble llave arriba."""

    def __init__(self, config: Config) -> None:
        load_dotenv()
        env_ok = os.getenv("LIVE_TRADING", "false").strip().lower() == "true"
        if not (env_ok and config.live_trading):
            raise RuntimeError(
                "Ejecución real DESHABILITADA. Se requiere LIVE_TRADING=true en .env "
                "Y live_trading: true en config.yaml (doble llave de seguridad). "
                "Antes de considerar habilitarla: backtest robusto + paper trading."
            )
        raise NotImplementedError(
            "La ejecución real está intencionalmente sin implementar (fase 3). "
            "El flujo obligatorio es: backtest -> paper trading -> revisión -> live."
        )

    def connect(self) -> None:  # pragma: no cover - inalcanzable por diseño
        raise NotImplementedError

    def disconnect(self) -> None:  # pragma: no cover
        raise NotImplementedError

    def submit_order(self, order: Any) -> str:  # pragma: no cover
        raise NotImplementedError

    def flatten_all(self) -> None:  # pragma: no cover
        raise NotImplementedError
