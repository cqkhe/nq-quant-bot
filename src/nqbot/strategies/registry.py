"""Registro de estrategias: nombre CLI -> clase.

Para agregar una estrategia nueva: crear el módulo, heredar de Strategy
y sumarla al dict. El CLI y la config la levantan por nombre.
"""

from __future__ import annotations

from typing import Any

from ..config.settings import ContractSpec
from .base import Strategy
from .base_vwap_ema import BaseVwapEmaStrategy
from .daytrading_vwap_liquidity_rr2 import DaytradingVwapLiquidityRR2
from .variants_rr2 import (
    LongsOnlyRR2,
    MorningOnlyRR2,
    NoMiddayAtrFilterRR2,
    NoMiddayLongsOnlyRR2,
    NoMiddayNearVwapRR2,
    NoMiddayRR2,
)

_REGISTRY: dict[str, type[Strategy]] = {
    BaseVwapEmaStrategy.name: BaseVwapEmaStrategy,
    DaytradingVwapLiquidityRR2.name: DaytradingVwapLiquidityRR2,
    # Variantes experimentales (ver docstring de variants_rr2: sesgo in-sample)
    NoMiddayRR2.name: NoMiddayRR2,
    LongsOnlyRR2.name: LongsOnlyRR2,
    MorningOnlyRR2.name: MorningOnlyRR2,
    NoMiddayLongsOnlyRR2.name: NoMiddayLongsOnlyRR2,
    NoMiddayNearVwapRR2.name: NoMiddayNearVwapRR2,
    NoMiddayAtrFilterRR2.name: NoMiddayAtrFilterRR2,
}


def available_strategies() -> list[str]:
    return sorted(_REGISTRY)


def create_strategy(name: str, params: dict[str, Any] | None, contract: ContractSpec) -> Strategy:
    try:
        cls = _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Estrategia desconocida: {name!r}. Disponibles: {', '.join(available_strategies())}"
        )
    return cls(params, contract)
