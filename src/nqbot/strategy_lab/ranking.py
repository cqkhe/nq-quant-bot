"""Ranking robusto para variantes de estrategia."""

from __future__ import annotations

import math

from .models import ExperimentResult, StrategyFilterConfig


def score_result(result: ExperimentResult, cfg: StrategyFilterConfig) -> float:
    """Puntua robustez; no usa PnL neto total como criterio de orden."""

    if result.error:
        return -1_000.0

    pf = _finite(result.profit_factor, default=0.0, cap=3.0)
    exp_r = max(result.expectancy_r or 0.0, -1.0)
    dd = result.max_drawdown_pct if result.max_drawdown_pct is not None else 100.0
    mc_neg = result.mc_probability_negative if result.mc_probability_negative is not None else 1.0
    mc_dd = (
        result.mc_probability_extreme_drawdown
        if result.mc_probability_extreme_drawdown is not None
        else 1.0
    )
    boot_bad = (
        result.bootstrap_probability_expectancy_le_zero
        if result.bootstrap_probability_expectancy_le_zero is not None
        else 1.0
    )

    score = 0.0
    score += min(result.n_trades / max(cfg.min_trades, 1), 1.5) * 20.0
    score += pf * 15.0
    score += exp_r * 60.0
    score -= max(dd, 0.0) * 2.0
    score -= mc_neg * 70.0
    score -= mc_dd * 40.0
    score -= boot_bad * 70.0

    if result.cost_stress_survives is False:
        score -= 40.0
    elif result.cost_stress_survives is True:
        score += 10.0

    if result.depends_on_top_winners is True:
        score -= 50.0
    elif result.depends_on_top_winners is False:
        score += 10.0

    if result.robustness_passed:
        score += 25.0
    if result.passed_filters:
        score += 25.0
    if result.decision_status == "PAPER_CANDIDATE":
        score += 30.0
    elif result.decision_status in {"REJECTED", "BLOCKED_FOR_PAPER"}:
        score -= 15.0

    return round(score, 6)


def rank_results(
    results: list[ExperimentResult],
    cfg: StrategyFilterConfig,
) -> list[ExperimentResult]:
    for result in results:
        result.rank_score = score_result(result, cfg)
    return sorted(results, key=lambda r: r.rank_score, reverse=True)


def _finite(value: float | None, *, default: float, cap: float) -> float:
    if value is None:
        return default
    if math.isinf(value):
        return cap
    if math.isnan(value):
        return default
    return min(float(value), cap)


__all__ = ["rank_results", "score_result"]
