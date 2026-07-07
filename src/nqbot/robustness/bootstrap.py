"""Bootstrap de metricas de performance por trade."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .models import BootstrapResult, ConfidenceInterval


def _series_from(
    trades: Sequence[float] | np.ndarray | pd.DataFrame,
    column: str,
    required: bool = True,
) -> np.ndarray | None:
    if isinstance(trades, pd.DataFrame):
        if column not in trades.columns:
            if required:
                raise ValueError(f"El DataFrame no tiene columna {column!r}")
            return None
        values = trades[column].to_numpy(dtype=float)
    else:
        if required:
            values = np.asarray(trades, dtype=float)
        else:
            return None
    values = values[np.isfinite(values)]
    if required and values.size == 0:
        raise ValueError("Se requiere al menos un trade numerico")
    return values


def _profit_factor(pnls: np.ndarray) -> float:
    gross_profit = float(pnls[pnls > 0].sum())
    gross_loss = float(-pnls[pnls < 0].sum())
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _ci(values: np.ndarray, confidence_level: float) -> ConfidenceInterval:
    tail = (1.0 - confidence_level) / 2.0
    lo, hi = np.percentile(values, [tail * 100.0, (1.0 - tail) * 100.0])
    return float(lo), float(hi)


def run_bootstrap(
    trades: Sequence[float] | np.ndarray | pd.DataFrame,
    iterations: int = 10_000,
    seed: int | None = 42,
    confidence_level: float = 0.90,
    pnl_column: str = "pnl_net",
    r_column: str = "r_multiple",
) -> BootstrapResult:
    """Calcula intervalos de confianza por remuestreo con reemplazo."""

    if iterations <= 0:
        raise ValueError("iterations debe ser > 0")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level debe estar entre 0 y 1")

    pnls = _series_from(trades, pnl_column, required=True)
    assert pnls is not None
    rs = _series_from(trades, r_column, required=False)
    if rs is not None and rs.size != pnls.size:
        raise ValueError("Las columnas de PnL y R deben tener la misma cantidad de datos")

    rng = np.random.default_rng(seed)
    avg_pnls = np.empty(iterations, dtype=float)
    profit_factors = np.empty(iterations, dtype=float)
    winrates = np.empty(iterations, dtype=float)
    expectancy_samples = np.empty(iterations, dtype=float)

    sign_values = rs if rs is not None else pnls
    for i in range(iterations):
        idx = rng.integers(0, pnls.size, size=pnls.size)
        sample_pnl = pnls[idx]
        sample_sign = sign_values[idx]
        avg_pnls[i] = float(sample_pnl.mean())
        profit_factors[i] = _profit_factor(sample_pnl)
        winrates[i] = float(np.mean(sample_pnl > 0.0) * 100.0)
        expectancy_samples[i] = float(sample_sign.mean())

    finite_pf = profit_factors[np.isfinite(profit_factors)]
    if finite_pf.size == 0:
        finite_pf = np.array([float("inf")])

    expectancy_r_mean: float | None
    expectancy_r_ci: ConfidenceInterval | None
    if rs is None:
        expectancy_r_mean = None
        expectancy_r_ci = None
    else:
        expectancy_r_mean = float(rs.mean())
        expectancy_r_ci = _ci(expectancy_samples, confidence_level)

    return BootstrapResult(
        iterations=iterations,
        n_trades=int(pnls.size),
        seed=seed,
        confidence_level=float(confidence_level),
        expectancy_r_mean=expectancy_r_mean,
        expectancy_r_ci=expectancy_r_ci,
        profit_factor_mean=float(finite_pf.mean()),
        profit_factor_ci=_ci(finite_pf, confidence_level),
        winrate_pct_mean=float(np.mean(pnls > 0.0) * 100.0),
        winrate_pct_ci=_ci(winrates, confidence_level),
        avg_pnl_per_trade_mean=float(pnls.mean()),
        avg_pnl_per_trade_ci=_ci(avg_pnls, confidence_level),
        probability_expectancy_le_zero=float(np.mean(expectancy_samples <= 0.0)),
        expectancy_sign_source="r_multiple" if rs is not None else "pnl_net",
    )


__all__ = ["run_bootstrap"]
