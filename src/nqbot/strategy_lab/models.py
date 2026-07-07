"""Modelos del Strategy Lab.

El lab describe familias, variantes y resultados de investigacion. No define
reglas de entrada/salida: solo combina parametros de estrategias existentes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from itertools import product
from typing import Any


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class ParameterGrid:
    """Grilla determinista de parametros."""

    values: dict[str, list[Any]] = field(default_factory=dict)

    def combinations(self) -> list[dict[str, Any]]:
        if not self.values:
            return [{}]
        keys = sorted(self.values)
        value_lists = [self.values[key] for key in keys]
        if any(len(items) == 0 for items in value_lists):
            raise ValueError("La grilla no puede contener listas vacias")
        return [dict(zip(keys, items)) for items in product(*value_lists)]


@dataclass(frozen=True)
class StrategyFamily:
    """Familia de busqueda basada en una estrategia registrada."""

    name: str
    base_strategy: str
    parameter_grid: ParameterGrid
    description: str = ""
    fixed_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyVariant:
    family: str
    strategy_name: str
    variant_id: str
    params: dict[str, Any]

    @property
    def label(self) -> str:
        return f"{self.strategy_name}::{self.variant_id}"


@dataclass(frozen=True)
class StrategyFilterConfig:
    min_trades: int = 100
    min_profit_factor: float = 1.15
    min_expectancy_r: float = 0.0
    max_drawdown_pct: float = 10.0
    max_mc_probability_negative: float = 0.20
    max_bootstrap_probability_expectancy_le_zero: float = 0.25
    require_cost_stress: bool = True
    block_top_winner_dependency: bool = True


@dataclass
class ExperimentResult:
    variant: StrategyVariant
    n_trades: int
    pnl_net: float
    profit_factor: float | None
    expectancy_r: float | None
    max_drawdown_pct: float | None
    mc_probability_negative: float | None = None
    mc_probability_extreme_drawdown: float | None = None
    bootstrap_probability_expectancy_le_zero: float | None = None
    cost_stress_survives: bool | None = None
    depends_on_top_winners: bool | None = None
    robustness_passed: bool = False
    decision_status: str = "NOT_EVALUATED"
    passed_filters: bool = False
    rejection_reasons: list[str] = field(default_factory=list)
    rank_score: float = 0.0
    error: str | None = None

    @property
    def paper_candidate(self) -> bool:
        return (
            self.decision_status == "PAPER_CANDIDATE"
            and self.robustness_passed
            and self.passed_filters
            and self.error is None
        )


@dataclass(frozen=True)
class StrategyRanking:
    family: StrategyFamily
    results: list[ExperimentResult]
    generated_variants: int
    evaluated_variants: int

    @property
    def ranked(self) -> list[ExperimentResult]:
        return sorted(self.results, key=lambda r: r.rank_score, reverse=True)

    @property
    def paper_candidates(self) -> list[ExperimentResult]:
        return [r for r in self.ranked if r.paper_candidate]


@dataclass(frozen=True)
class StrategySearchConfig:
    family: StrategyFamily
    symbol: str
    data: str
    initial_capital: float
    max_variants: int
    iterations: int
    seed: int
    filters: StrategyFilterConfig = field(default_factory=StrategyFilterConfig)
    reports_dir: str = "reports"
    config_path: str = "config/config.yaml"


def make_variant(family: StrategyFamily, params: dict[str, Any]) -> StrategyVariant:
    merged = {**family.fixed_params, **params}
    digest = hashlib.sha1(_stable_json(merged).encode("utf-8")).hexdigest()[:10]
    return StrategyVariant(
        family=family.name,
        strategy_name=family.base_strategy,
        variant_id=f"v_{digest}",
        params=merged,
    )


def result_to_row(result: ExperimentResult) -> dict[str, Any]:
    return {
        "family": result.variant.family,
        "strategy": result.variant.strategy_name,
        "variant_id": result.variant.variant_id,
        "params": _stable_json(result.variant.params),
        "n_trades": result.n_trades,
        "pnl_net": result.pnl_net,
        "profit_factor": result.profit_factor,
        "expectancy_r": result.expectancy_r,
        "max_drawdown_pct": result.max_drawdown_pct,
        "mc_probability_negative": result.mc_probability_negative,
        "mc_probability_extreme_drawdown": result.mc_probability_extreme_drawdown,
        "bootstrap_probability_expectancy_le_zero": (
            result.bootstrap_probability_expectancy_le_zero
        ),
        "cost_stress_survives": result.cost_stress_survives,
        "depends_on_top_winners": result.depends_on_top_winners,
        "robustness_passed": result.robustness_passed,
        "decision_status": result.decision_status,
        "passed_filters": result.passed_filters,
        "paper_candidate": result.paper_candidate,
        "rank_score": result.rank_score,
        "rejection_reasons": "; ".join(result.rejection_reasons),
        "error": result.error,
    }


__all__ = [
    "ExperimentResult",
    "ParameterGrid",
    "StrategyFamily",
    "StrategyFilterConfig",
    "StrategyRanking",
    "StrategySearchConfig",
    "StrategyVariant",
    "make_variant",
    "result_to_row",
]
