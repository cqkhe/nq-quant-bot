"""Execution Simulator — reglas de fill deliberadamente conservadoras.

Supuestos documentados (sesgan el backtest EN CONTRA, nunca a favor):
  * Toda orden a MERCADO (entrada, stop-market, flatten) paga un costo
    adverso de `slippage_ticks` + medio spread bid/ask (`spread_ticks / 2`):
    el precio de la barra es el último operado, pero un market order cruza
    el libro y ejecuta contra el ask (long) o el bid (short).
  * Entradas: orden a mercado en el open de la barra siguiente a la señal.
  * Stop loss: stop-market. Fill al precio del stop + costo adverso. Si la
    barra abre gapeada más allá del stop, el fill es al open (peor), no al stop.
  * Take profit: orden límite. Fill exacto al precio objetivo, sin slippage
    ni spread. Si la barra abre más allá del objetivo, fill al open (mejor).
  * Si stop y target quedan dentro del rango de la misma barra, se asume que
    el stop se tocó primero (no hay datos intra-barra para saber el orden).
  * Comisión por lado y por contrato, cargada completa al cerrar el trade.
"""

from __future__ import annotations

from datetime import datetime

from ..backtesting.models import Position, Trade
from ..config.settings import ContractSpec


class ExecutionSimulator:
    def __init__(
        self,
        contract: ContractSpec,
        slippage_ticks: int = 1,
        spread_ticks: float = 0.0,
    ) -> None:
        self.contract = contract
        # costo adverso de toda orden a mercado: slippage + medio spread
        self.adverse_cost = (slippage_ticks + spread_ticks / 2.0) * contract.tick_size

    def entry_fill_price(self, bar_open: float, direction: int) -> float:
        """Fill de entrada a mercado: open de la barra + costo adverso."""
        return self.contract.round_to_tick(bar_open + direction * self.adverse_cost)

    def market_exit_price(self, price: float, direction: int) -> float:
        """Salida a mercado (flatten/stop): precio - costo adverso."""
        return self.contract.round_to_tick(price - direction * self.adverse_cost)

    def check_exit(
        self,
        position: Position,
        bar_open: float,
        bar_high: float,
        bar_low: float,
        bar_close: float,
        entered_this_bar: bool,
    ) -> tuple[float, str] | None:
        """Evalúa stop/target contra una barra. Devuelve (precio, motivo) o None.

        En la barra de entrada no se evalúan gaps de apertura (la posición se
        abrió justamente en ese open), pero sí el rango intra-barra.
        """
        d = position.direction

        if not entered_this_bar:
            # Gap de apertura más allá del stop: fill al open, no al stop.
            if (bar_open - position.stop_price) * d <= 0:
                return self.market_exit_price(bar_open, d), "stop_gap"
            # Gap de apertura más allá del target: la limit llena al open (mejor).
            if (bar_open - position.target_price) * d >= 0:
                return self.contract.round_to_tick(bar_open), "target_gap"

        hit_stop = (bar_low <= position.stop_price) if d > 0 else (bar_high >= position.stop_price)
        hit_target = (bar_high >= position.target_price) if d > 0 else (bar_low <= position.target_price)

        if hit_stop:  # conservador: si ambos se tocan, gana el stop
            return self.market_exit_price(position.stop_price, d), "stop"
        if hit_target:
            return self.contract.round_to_tick(position.target_price), "target"
        return None

    def build_trade(
        self,
        position: Position,
        exit_time: datetime,
        exit_price: float,
        exit_reason: str,
        bars_held: int,
    ) -> Trade:
        """Cierra la posición y liquida PnL, comisiones y R múltiplo."""
        pv = self.contract.point_value
        gross = (exit_price - position.entry_price) * position.direction * pv * position.contracts
        commission = self.contract.commission_per_side * 2 * position.contracts
        net = gross - commission
        risk = position.initial_risk_dollars
        return Trade(
            symbol=self.contract.symbol,
            direction=position.direction,
            contracts=position.contracts,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=exit_time,
            exit_price=exit_price,
            stop_price=position.stop_price,
            target_price=position.target_price,
            exit_reason=exit_reason,
            pnl_gross=round(gross, 2),
            commission=round(commission, 2),
            pnl_net=round(net, 2),
            initial_risk_dollars=round(risk, 2),
            r_multiple=round(net / risk, 3) if risk > 0 else 0.0,
            bars_held=bars_held,
            reason=position.reason,
        )
