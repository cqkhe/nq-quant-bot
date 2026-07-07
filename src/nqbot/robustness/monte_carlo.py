"""Monte Carlo empirico para secuencias de trades ya generadas."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .models import MonteCarloConfig, MonteCarloResult, Percentiles


def _trade_values(trades: Sequence[float] | np.ndarray | pd.DataFrame, column: str) -> np.ndarray:
    if isinstance(trades, pd.DataFrame):
        if column not in trades.columns:
            raise ValueError(f"El DataFrame no tiene columna {column!r}")
        values = trades[column].to_numpy(dtype=float)
    else:
        values = np.asarray(trades, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("Se requiere al menos un trade numerico")
    return values


def _percentiles(values: np.ndarray) -> Percentiles:
    p5, p50, p95 = np.percentile(values, [5, 50, 95])
    return {"p05": float(p5), "p50": float(p50), "p95": float(p95)}


def _max_drawdown(path_pnl: np.ndarray, initial_capital: float) -> tuple[float, float]:
    equity = initial_capital + np.cumsum(path_pnl)
    equity = np.concatenate(([initial_capital], equity))
    peaks = np.maximum.accumulate(equity)
    dd_usd = peaks - equity
    max_dd_usd = float(np.max(dd_usd))
    peak_at_max = float(peaks[int(np.argmax(dd_usd))])
    max_dd_pct = 0.0 if peak_at_max <= 0 else max_dd_usd / peak_at_max * 100.0
    return max_dd_usd, max_dd_pct


def _max_losing_streak(path_pnl: np.ndarray) -> int:
    best = current = 0
    for pnl in path_pnl:
        current = current + 1 if pnl < 0 else 0
        best = max(best, current)
    return best


def run_monte_carlo(
    trades: Sequence[float] | np.ndarray | pd.DataFrame,
    config: MonteCarloConfig | None = None,
    pnl_column: str = "pnl_net",
) -> MonteCarloResult:
    """Simula curvas de equity a partir de una distribucion empirica de trades."""

    cfg = config or MonteCarloConfig()
    if cfg.iterations <= 0:
        raise ValueError("iterations debe ser > 0")
    if cfg.initial_capital <= 0:
        raise ValueError("initial_capital debe ser > 0")

    pnls = _trade_values(trades, pnl_column)
    rng = np.random.default_rng(cfg.seed)
    final_pnls = np.empty(cfg.iterations, dtype=float)
    drawdowns_usd = np.empty(cfg.iterations, dtype=float)
    drawdowns_pct = np.empty(cfg.iterations, dtype=float)
    losing_streaks = np.empty(cfg.iterations, dtype=float)

    for i in range(cfg.iterations):
        if cfg.sample_with_replacement:
            sample = rng.choice(pnls, size=pnls.size, replace=True)
        else:
            sample = rng.permutation(pnls)
        final_pnls[i] = float(sample.sum())
        dd_usd, dd_pct = _max_drawdown(sample, cfg.initial_capital)
        drawdowns_usd[i] = dd_usd
        drawdowns_pct[i] = dd_pct
        losing_streaks[i] = _max_losing_streak(sample)

    return MonteCarloResult(
        iterations=cfg.iterations,
        n_trades=int(pnls.size),
        initial_capital=float(cfg.initial_capital),
        seed=cfg.seed,
        sample_with_replacement=cfg.sample_with_replacement,
        drawdown_threshold_pct=float(cfg.drawdown_threshold_pct),
        final_pnl_mean=float(final_pnls.mean()),
        final_pnl_percentiles=_percentiles(final_pnls),
        max_drawdown_pct_mean=float(drawdowns_pct.mean()),
        max_drawdown_pct_percentiles=_percentiles(drawdowns_pct),
        max_drawdown_usd_percentiles=_percentiles(drawdowns_usd),
        losing_streak_percentiles=_percentiles(losing_streaks),
        probability_negative=float(np.mean(final_pnls < 0.0)),
        probability_drawdown_exceeds_threshold=float(
            np.mean(drawdowns_pct >= cfg.drawdown_threshold_pct)
        ),
    )


__all__ = ["run_monte_carlo"]
