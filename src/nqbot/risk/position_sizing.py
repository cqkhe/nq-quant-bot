"""Position sizing por riesgo fijo fraccional.

contratos = floor( (equity * riesgo%) / (distancia_stop_pts * valor_punto) )

Si el riesgo permitido no alcanza para 1 contrato, se devuelve 0 y la
operación NO se toma: nunca se redondea hacia arriba el riesgo.
"""

from __future__ import annotations

import math


def contracts_for_risk(
    equity: float,
    risk_per_trade_pct: float,
    stop_distance_points: float,
    point_value: float,
    max_contracts: int,
) -> int:
    """Cantidad de contratos para arriesgar como máximo `risk_per_trade_pct` del equity."""
    if equity <= 0 or stop_distance_points <= 0 or point_value <= 0:
        return 0
    risk_dollars = equity * risk_per_trade_pct / 100.0
    risk_per_contract = stop_distance_points * point_value
    contracts = math.floor(risk_dollars / risk_per_contract)
    return max(0, min(contracts, max_contracts))
