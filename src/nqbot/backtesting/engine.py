"""Backtesting Engine — loop event-driven barra a barra.

Orden de operaciones por barra (crítico para la honestidad del backtest):
  1. Llenar la entrada pendiente (señal de la barra anterior) al OPEN.
  2. Evaluar stop / target de la posición abierta contra el rango de la barra.
  3. Flatten forzado por horario o por última barra de la sesión.
  4. Solo si está flat: pedir señal a la estrategia (al CIERRE de la barra),
     pasarla por el Risk Manager y el position sizing, y dejarla pendiente
     para el open de la barra siguiente.
  5. Marcar equity mark-to-market.

Garantías:
  * Ninguna señal se ejecuta en la misma barra que la genera.
  * Ninguna orden pendiente sobrevive un cambio de sesión.
  * Ninguna posición queda abierta overnight.
"""

from __future__ import annotations

import logging
from collections import Counter

import numpy as np
import pandas as pd

from ..config.settings import Config, ContractSpec
from ..execution.simulator import ExecutionSimulator
from ..portfolio.account import Account
from ..risk.manager import RiskManager
from ..risk.position_sizing import contracts_for_risk
from ..strategies.base import Strategy
from ..utils.sessions import time_in_range, trade_session_key
from .models import BacktestResult, PendingEntry, Position, Trade, TradeState


class BacktestEngine:
    def __init__(
        self,
        config: Config,
        contract: ContractSpec,
        strategy: Strategy,
        logger: logging.Logger | None = None,
    ) -> None:
        self.cfg = config
        self.contract = contract
        self.strategy = strategy
        self.log = logger or logging.getLogger("nqbot")
        self.sim = ExecutionSimulator(
            contract, config.execution.slippage_ticks, config.execution.spread_ticks
        )

    def run(self, df: pd.DataFrame) -> BacktestResult:
        self.log.info(
            "Backtest: %s | estrategia=%s | capital inicial=%.2f",
            self.contract.symbol, self.strategy.name, self.cfg.account.initial_capital,
        )
        data = self.strategy.prepare(df)

        idx = data.index
        n = len(data)
        opens = data["open"].to_numpy()
        highs = data["high"].to_numpy()
        lows = data["low"].to_numpy()
        closes = data["close"].to_numpy()
        bar_times = idx.time
        sess = self.cfg.session
        # Fecha de sesión de TRADING (no calendario): las barras >= globex_open
        # pertenecen a la sesión del día siguiente. Para datos solo-RTH es
        # idéntico a la fecha calendario.
        session_dates = trade_session_key(idx, sess)
        last_bar_of_session = np.empty(n, dtype=bool)
        last_bar_of_session[:-1] = (session_dates[1:] != session_dates[:-1])
        last_bar_of_session[-1] = True

        # El flatten por horario solo aplica si flatten_time cae dentro de la
        # ventana operada (en overnight, un "15:50" heredado no debe disparar).
        win_start, win_end = sess.trade_window()
        flatten_in_window = time_in_range(sess.flatten_time, win_start, win_end, inclusive_end=True)

        account = Account(self.cfg.account.initial_capital)
        risk = RiskManager(self.cfg.risk, self.log)
        pv = self.contract.point_value

        trades: list[Trade] = []
        skipped: Counter[str] = Counter()
        equity = np.empty(n, dtype=float)
        pending: PendingEntry | None = None
        position: Position | None = None
        bars_held = 0
        # excursiones de la posición abierta (en puntos), acumuladas de forma
        # causal barra a barra: insumo del TradeState del hook de salida dinámica
        pos_risk_pts = 0.0
        pos_mfe_pts = 0.0
        pos_mae_pts = 0.0
        current_session = None

        for i in range(n):
            ts = idx[i]
            t = bar_times[i]

            if session_dates[i] != current_session:
                current_session = session_dates[i]
                if pending is not None:
                    skipped["orden_cancelada_cambio_sesion"] += 1
                    pending = None
                risk.new_session(current_session.date(), account.equity)

            entered_this_bar = False

            # 1) Fill de la entrada pendiente al open
            if pending is not None:
                sig, contracts = pending.signal, pending.contracts
                pending = None
                fill = self.sim.entry_fill_price(opens[i], sig.direction)
                dist = (fill - sig.stop_price) * sig.direction
                if dist <= 0:
                    skipped["stop_invalido_tras_fill"] += 1
                    self.log.debug("%s señal descartada: el open gapeó más allá del stop", ts)
                else:
                    target = self.contract.round_to_tick(fill + sig.direction * sig.rr * dist)
                    # Validación explícita del RR planificado: el target se calcula
                    # sobre el fill real (ya incluye slippage/spread), así que el RR
                    # solo puede desviarse por el redondeo del target al tick.
                    planned_rr = (target - fill) * sig.direction / dist
                    if abs(planned_rr - sig.rr) > 0.02 * sig.rr:
                        self.log.warning(
                            "%s RR planificado %.3f difiere del objetivo %.2f "
                            "(redondeo al tick sobre stop de %.2f pts)",
                            ts, planned_rr, sig.rr, dist,
                        )
                    else:
                        self.log.debug(
                            "%s RR planificado %.4f (objetivo %.2f) OK", ts, planned_rr, sig.rr
                        )
                    position = Position(
                        direction=sig.direction,
                        contracts=contracts,
                        entry_time=ts,
                        entry_price=fill,
                        stop_price=sig.stop_price,
                        target_price=target,
                        initial_risk_dollars=dist * pv * contracts,
                        reason=sig.reason,
                    )
                    bars_held = 0
                    pos_risk_pts = dist
                    pos_mfe_pts = 0.0
                    pos_mae_pts = 0.0
                    entered_this_bar = True
                    risk.on_position_opened()
                    self.log.info(
                        "%s ENTRADA %s x%d @ %.2f | SL %.2f | TP %.2f | riesgo $%.2f [%s]",
                        ts, "LONG" if sig.direction > 0 else "SHORT", contracts,
                        fill, sig.stop_price, target, position.initial_risk_dollars, sig.reason,
                    )

            # 2) Gestión de la posición abierta: stop / target
            if position is not None:
                bars_held += 1
                d = position.direction
                fav = (highs[i] - position.entry_price) if d > 0 else (position.entry_price - lows[i])
                adv = (position.entry_price - lows[i]) if d > 0 else (highs[i] - position.entry_price)
                pos_mfe_pts = max(pos_mfe_pts, fav)
                pos_mae_pts = max(pos_mae_pts, adv)
                exit_ = self.sim.check_exit(
                    position, opens[i], highs[i], lows[i], closes[i], entered_this_bar
                )
                if exit_ is not None:
                    position, trade = None, self.sim.build_trade(position, ts, exit_[0], exit_[1], bars_held)
                    self._settle(trade, account, risk, trades)

            # 3) Flatten por horario o fin de sesión: nunca se retiene la posición
            #    fuera de la ventana operada
            if position is not None and (
                (flatten_in_window and time_in_range(t, sess.flatten_time, win_end, inclusive_end=True))
                or last_bar_of_session[i]
            ):
                price = self.sim.market_exit_price(closes[i], position.direction)
                position, trade = None, self.sim.build_trade(position, ts, price, "session_flatten", bars_held)
                self._settle(trade, account, risk, trades)

            # 3b) Salida dinámica OPCIONAL de la estrategia (hook causal).
            # Se evalúa DESPUÉS de stop/target/flatten: jamás los pisa. Usa
            # solo la barra actual cerrada y el TradeState acumulado hasta acá;
            # el fill es a mercado al cierre (misma convención que el flatten).
            if position is not None:
                state = TradeState(
                    direction=position.direction,
                    contracts=position.contracts,
                    entry_time=position.entry_time,
                    entry_price=position.entry_price,
                    stop_price=position.stop_price,
                    target_price=position.target_price,
                    initial_risk_dollars=position.initial_risk_dollars,
                    bars_held=bars_held,
                    minutes_held=(ts - position.entry_time).total_seconds() / 60.0,
                    current_close=closes[i],
                    current_r=(closes[i] - position.entry_price) * position.direction / pos_risk_pts,
                    mfe_r=pos_mfe_pts / pos_risk_pts,
                    mae_r=pos_mae_pts / pos_risk_pts,
                )
                early = self.strategy.should_exit_early(ts, data.iloc[i], state)
                if early is not None:
                    price = self.sim.market_exit_price(closes[i], position.direction)
                    position, trade = None, self.sim.build_trade(position, ts, price, "early_exit", bars_held)
                    self._settle(trade, account, risk, trades)
                    self.log.info(
                        "%s EARLY EXIT [%s] %s | estado: %.1f min, MFE %.2fR, mark %.2fR",
                        ts, getattr(early.reason, "value", early.reason), early.detail,
                        state.minutes_held, state.mfe_r, state.current_r,
                    )

            # 4) Búsqueda de señal nueva (solo flat y dentro de la ventana horaria)
            if (
                position is None
                and pending is None
                and not last_bar_of_session[i]
                and time_in_range(t, sess.entry_start, sess.entry_cutoff, inclusive_end=True)
            ):
                decision = risk.can_open()
                if decision.allowed:
                    sig = self.strategy.signal_for_bar(ts, data.iloc[i])
                    if sig is not None:
                        pending = self._size_signal(sig, closes[i], account, skipped)

            # 5) Equity mark-to-market
            eq = account.equity
            if position is not None:
                eq += position.unrealized(closes[i], pv)
            equity[i] = eq

        result = BacktestResult(
            symbol=self.contract.symbol,
            strategy_name=self.strategy.name,
            initial_capital=self.cfg.account.initial_capital,
            trades=trades,
            equity_curve=pd.Series(equity, index=idx, name="equity"),
            skipped_signals=dict(skipped),
            start=idx[0].to_pydatetime(),
            end=idx[-1].to_pydatetime(),
            params=dict(self.strategy.params),
        )
        self.log.info(
            "Backtest terminado: %d trades | PnL neto $%.2f | equity final $%.2f",
            len(trades), account.realized_pnl, account.equity,
        )
        return result

    # ------------------------------------------------------------------ helpers
    def _settle(
        self,
        trade: Trade,
        account: Account,
        risk: RiskManager,
        trades: list[Trade],
    ) -> None:
        account.apply_trade(trade)
        risk.on_trade_closed(trade)
        trades.append(trade)
        self.log.info(
            "%s SALIDA %s @ %.2f [%s] | PnL $%+.2f (%.2fR) | equity $%.2f",
            trade.exit_time, "LONG" if trade.direction > 0 else "SHORT",
            trade.exit_price, trade.exit_reason, trade.pnl_net, trade.r_multiple, account.equity,
        )

    def _size_signal(
        self,
        sig,
        close: float,
        account: Account,
        skipped: Counter,
    ) -> PendingEntry | None:
        dist = (close - sig.stop_price) * sig.direction
        if dist <= 0:
            skipped["stop_invalido"] += 1
            return None
        if dist > self.cfg.risk.max_stop_points:
            skipped["stop_demasiado_lejos"] += 1
            self.log.debug("%s señal descartada: stop a %.2f pts (máx %.2f)",
                           sig.time, dist, self.cfg.risk.max_stop_points)
            return None
        contracts = contracts_for_risk(
            equity=account.equity,
            risk_per_trade_pct=self.cfg.risk.risk_per_trade_pct,
            stop_distance_points=dist,
            point_value=self.contract.point_value,
            max_contracts=self.cfg.risk.max_contracts,
        )
        if contracts == 0:
            skipped["riesgo_insuficiente_para_1_contrato"] += 1
            self.log.debug("%s señal descartada: el riesgo permitido no cubre 1 contrato", sig.time)
            return None
        self.log.info(
            "%s SEÑAL %s [%s] stop %.2f (%.2f pts) -> %d contrato(s) al próximo open",
            sig.time, "LONG" if sig.direction > 0 else "SHORT",
            sig.reason, sig.stop_price, dist, contracts,
        )
        return PendingEntry(signal=sig, contracts=contracts)
