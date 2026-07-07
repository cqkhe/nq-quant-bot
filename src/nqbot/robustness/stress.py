"""Stress tests sobre distribuciones de trades existentes."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .models import StressTestResult
from .monte_carlo import _max_drawdown, _trade_values


def _optional_values(
    trades: Sequence[float] | np.ndarray | pd.DataFrame,
    column: str,
) -> np.ndarray | None:
    if not isinstance(trades, pd.DataFrame) or column not in trades.columns:
        return None
    values = trades[column].to_numpy(dtype=float)
    return values[np.isfinite(values)]


def _profit_factor(pnls: np.ndarray) -> float:
    gross_profit = float(pnls[pnls > 0].sum())
    gross_loss = float(-pnls[pnls < 0].sum())
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _stress_rs(original_pnls: np.ndarray, stressed_pnls: np.ndarray, rs: np.ndarray | None) -> float | None:
    if rs is None:
        return None
    scaled = rs.copy()
    for i, original in enumerate(original_pnls):
        if original != 0:
            scaled[i] = rs[i] * (stressed_pnls[i] / original)
    return float(scaled.mean())


def summarize_stress(
    scenario: str,
    original_pnls: np.ndarray,
    stressed_pnls: np.ndarray,
    initial_capital: float,
    rs: np.ndarray | None = None,
    notes: str = "",
) -> StressTestResult:
    dd_usd, dd_pct = _max_drawdown(stressed_pnls, initial_capital)
    del dd_usd
    pf = _profit_factor(stressed_pnls)
    expectancy_r = _stress_rs(original_pnls, stressed_pnls, rs)
    pnl_net = float(stressed_pnls.sum())
    edge_survives = pnl_net > 0.0 and pf >= 1.0
    if expectancy_r is not None:
        edge_survives = edge_survives and expectancy_r > 0.0
    return StressTestResult(
        scenario=scenario,
        n_trades=int(stressed_pnls.size),
        pnl_net=pnl_net,
        pnl_delta=float(pnl_net - original_pnls.sum()),
        profit_factor=float(pf),
        winrate_pct=float(np.mean(stressed_pnls > 0.0) * 100.0),
        avg_pnl_per_trade=float(stressed_pnls.mean()),
        expectancy_r=expectancy_r,
        max_drawdown_pct=float(dd_pct),
        edge_survives=bool(edge_survives),
        notes=notes,
    )


def apply_stress(
    trades: Sequence[float] | np.ndarray | pd.DataFrame,
    *,
    initial_capital: float = 25_000.0,
    scenario: str = "custom",
    extra_cost_per_trade: float = 0.0,
    commission_increase_per_trade: float = 0.0,
    slippage_increase_per_trade: float = 0.0,
    reduce_winners_pct: float = 0.0,
    increase_losers_pct: float = 0.0,
    remove_top_winners: int = 0,
    edge_degradation_pct: float = 0.0,
    pnl_column: str = "pnl_net",
    r_column: str = "r_multiple",
    notes: str = "",
) -> StressTestResult:
    """Aplica un escenario de degradacion sobre los PnL existentes."""

    if initial_capital <= 0:
        raise ValueError("initial_capital debe ser > 0")
    original = _trade_values(trades, pnl_column)
    stressed = original.copy()
    rs = _optional_values(trades, r_column)
    if rs is not None and rs.size != original.size:
        rs = None

    total_extra_cost = (
        float(extra_cost_per_trade)
        + float(commission_increase_per_trade)
        + float(slippage_increase_per_trade)
    )
    if total_extra_cost:
        stressed -= total_extra_cost
    if reduce_winners_pct:
        winners = stressed > 0
        stressed[winners] *= 1.0 - float(reduce_winners_pct)
    if increase_losers_pct:
        losers = stressed < 0
        stressed[losers] *= 1.0 + float(increase_losers_pct)
    if edge_degradation_pct:
        winners = stressed > 0
        losers = stressed < 0
        stressed[winners] *= 1.0 - float(edge_degradation_pct)
        stressed[losers] *= 1.0 + float(edge_degradation_pct)
    if remove_top_winners > 0:
        winners_idx = np.where(stressed > 0)[0]
        if winners_idx.size:
            top_idx = winners_idx[np.argsort(stressed[winners_idx])[-remove_top_winners:]]
            stressed[top_idx] = 0.0

    return summarize_stress(scenario, original, stressed, initial_capital, rs=rs, notes=notes)


def run_stress_suite(
    trades: Sequence[float] | np.ndarray | pd.DataFrame,
    *,
    initial_capital: float = 25_000.0,
    reasonable_extra_cost_per_trade: float = 5.0,
    pnl_column: str = "pnl_net",
    r_column: str = "r_multiple",
) -> list[StressTestResult]:
    """Escenarios estandar para detectar fragilidad del edge."""

    return [
        apply_stress(
            trades,
            initial_capital=initial_capital,
            scenario="baseline",
            pnl_column=pnl_column,
            r_column=r_column,
            notes="sin degradacion",
        ),
        apply_stress(
            trades,
            initial_capital=initial_capital,
            scenario="commission_plus_reasonable",
            commission_increase_per_trade=2.0,
            pnl_column=pnl_column,
            r_column=r_column,
            notes="comision adicional razonable por trade",
        ),
        apply_stress(
            trades,
            initial_capital=initial_capital,
            scenario="slippage_plus_reasonable",
            slippage_increase_per_trade=3.0,
            pnl_column=pnl_column,
            r_column=r_column,
            notes="slippage adicional razonable por trade",
        ),
        apply_stress(
            trades,
            initial_capital=initial_capital,
            scenario="costs_plus_reasonable",
            extra_cost_per_trade=reasonable_extra_cost_per_trade,
            pnl_column=pnl_column,
            r_column=r_column,
            notes=f"costo adicional de {reasonable_extra_cost_per_trade:.2f} por trade",
        ),
        apply_stress(
            trades,
            initial_capital=initial_capital,
            scenario="winners_minus_10pct",
            reduce_winners_pct=0.10,
            pnl_column=pnl_column,
            r_column=r_column,
        ),
        apply_stress(
            trades,
            initial_capital=initial_capital,
            scenario="losers_plus_10pct",
            increase_losers_pct=0.10,
            pnl_column=pnl_column,
            r_column=r_column,
        ),
        apply_stress(
            trades,
            initial_capital=initial_capital,
            scenario="remove_top_5_winners",
            remove_top_winners=5,
            pnl_column=pnl_column,
            r_column=r_column,
        ),
        apply_stress(
            trades,
            initial_capital=initial_capital,
            scenario="remove_top_10_winners",
            remove_top_winners=10,
            pnl_column=pnl_column,
            r_column=r_column,
        ),
        apply_stress(
            trades,
            initial_capital=initial_capital,
            scenario="edge_minus_10pct",
            edge_degradation_pct=0.10,
            pnl_column=pnl_column,
            r_column=r_column,
        ),
    ]


__all__ = ["apply_stress", "run_stress_suite", "summarize_stress"]
