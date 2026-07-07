"""Riesgo de ruina y drawdown basado en simulacion empirica."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .models import DrawdownRiskResult, RiskOfRuinResult
from .monte_carlo import _max_drawdown, _max_losing_streak, _trade_values


def estimate_risk(
    trades: Sequence[float] | np.ndarray | pd.DataFrame,
    initial_capital: float = 25_000.0,
    iterations: int = 10_000,
    seed: int | None = 42,
    ruin_threshold_pct: float = 50.0,
    loss_threshold_pct: float = 25.0,
    capital_tolerance_drawdown_pct: float = 20.0,
    pnl_column: str = "pnl_net",
) -> tuple[RiskOfRuinResult, DrawdownRiskResult]:
    """Estima riesgo de ruina y drawdown remuestreando trades con reemplazo."""

    if initial_capital <= 0:
        raise ValueError("initial_capital debe ser > 0")
    if iterations <= 0:
        raise ValueError("iterations debe ser > 0")
    if not 0.0 < ruin_threshold_pct < 100.0:
        raise ValueError("ruin_threshold_pct debe estar entre 0 y 100")
    if not 0.0 < loss_threshold_pct < 100.0:
        raise ValueError("loss_threshold_pct debe estar entre 0 y 100")
    if not 0.0 < capital_tolerance_drawdown_pct < 100.0:
        raise ValueError("capital_tolerance_drawdown_pct debe estar entre 0 y 100")

    pnls = _trade_values(trades, pnl_column)
    rng = np.random.default_rng(seed)
    max_dd_usd = np.empty(iterations, dtype=float)
    max_dd_pct = np.empty(iterations, dtype=float)
    losing_streaks = np.empty(iterations, dtype=float)
    ruined = np.empty(iterations, dtype=bool)
    lost_threshold = np.empty(iterations, dtype=bool)

    ruin_floor = initial_capital * (1.0 - ruin_threshold_pct / 100.0)
    loss_floor = initial_capital * (1.0 - loss_threshold_pct / 100.0)

    for i in range(iterations):
        sample = rng.choice(pnls, size=pnls.size, replace=True)
        equity = initial_capital + np.cumsum(sample)
        min_equity = float(np.min(np.concatenate(([initial_capital], equity))))
        ruined[i] = min_equity <= ruin_floor
        lost_threshold[i] = min_equity <= loss_floor
        dd_usd, dd_pct = _max_drawdown(sample, initial_capital)
        max_dd_usd[i] = dd_usd
        max_dd_pct[i] = dd_pct
        losing_streaks[i] = _max_losing_streak(sample)

    dd_usd_p95 = float(np.percentile(max_dd_usd, 95))
    suggested_min_capital = dd_usd_p95 / (capital_tolerance_drawdown_pct / 100.0)

    risk = RiskOfRuinResult(
        initial_capital=float(initial_capital),
        ruin_threshold_pct=float(ruin_threshold_pct),
        loss_threshold_pct=float(loss_threshold_pct),
        risk_of_ruin=float(np.mean(ruined)),
        probability_loss_threshold=float(np.mean(lost_threshold)),
        suggested_min_capital=float(suggested_min_capital),
        capital_tolerance_drawdown_pct=float(capital_tolerance_drawdown_pct),
    )
    drawdown = DrawdownRiskResult(
        expected_max_drawdown_pct=float(np.mean(max_dd_pct)),
        expected_max_drawdown_usd=float(np.mean(max_dd_usd)),
        drawdown_pct_p95=float(np.percentile(max_dd_pct, 95)),
        drawdown_usd_p95=dd_usd_p95,
        worst_losing_streak_p95=int(np.ceil(np.percentile(losing_streaks, 95))),
    )
    return risk, drawdown


__all__ = ["estimate_risk"]
