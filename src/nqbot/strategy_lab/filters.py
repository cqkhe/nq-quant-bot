"""Filtros minimos configurables del Strategy Lab."""

from __future__ import annotations

from .models import ExperimentResult, StrategyFilterConfig


def apply_filters(result: ExperimentResult, cfg: StrategyFilterConfig) -> ExperimentResult:
    reasons: list[str] = []

    if result.error:
        reasons.append(result.error)
    if result.n_trades < cfg.min_trades:
        reasons.append(f"trades {result.n_trades} < minimo {cfg.min_trades}")
    if result.profit_factor is None or result.profit_factor < cfg.min_profit_factor:
        reasons.append(
            f"profit_factor {result.profit_factor} < minimo {cfg.min_profit_factor}"
        )
    if result.expectancy_r is None or result.expectancy_r <= cfg.min_expectancy_r:
        reasons.append(
            f"expectancy_r {result.expectancy_r} <= minimo {cfg.min_expectancy_r}"
        )
    if result.max_drawdown_pct is None or result.max_drawdown_pct > cfg.max_drawdown_pct:
        reasons.append(
            f"drawdown {result.max_drawdown_pct} > maximo {cfg.max_drawdown_pct}"
        )
    if (
        result.mc_probability_negative is None
        or result.mc_probability_negative > cfg.max_mc_probability_negative
    ):
        reasons.append(
            "mc_probability_negative "
            f"{result.mc_probability_negative} > maximo {cfg.max_mc_probability_negative}"
        )
    if (
        result.bootstrap_probability_expectancy_le_zero is None
        or result.bootstrap_probability_expectancy_le_zero
        > cfg.max_bootstrap_probability_expectancy_le_zero
    ):
        reasons.append(
            "bootstrap_probability_expectancy_le_zero "
            f"{result.bootstrap_probability_expectancy_le_zero} > maximo "
            f"{cfg.max_bootstrap_probability_expectancy_le_zero}"
        )
    if cfg.require_cost_stress and result.cost_stress_survives is not True:
        reasons.append("no sobrevive stress de costos/slippage")
    if cfg.block_top_winner_dependency and result.depends_on_top_winners is True:
        reasons.append("depende de pocos ganadores")
    if not result.robustness_passed:
        reasons.append("Robustness Engine marco fragilidad")

    result.rejection_reasons = reasons
    result.passed_filters = len(reasons) == 0
    return result


__all__ = ["apply_filters"]
