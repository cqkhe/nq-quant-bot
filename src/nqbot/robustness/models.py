"""Modelos del Quant Robustness Engine.

El motor trabaja sobre trades ya generados. No conoce estrategias, reglas de
entrada/salida ni backtests: solo consume distribuciones de PnL/R.
"""

from __future__ import annotations

from dataclasses import dataclass, field


Percentiles = dict[str, float]
ConfidenceInterval = tuple[float, float]


@dataclass(frozen=True)
class MonteCarloConfig:
    """Configuracion de simulacion Monte Carlo.

    `sample_with_replacement=True` modela incertidumbre de resultados futuros a
    partir de la distribucion empirica de trades. Con `False`, solo reordena los
    mismos trades; el PnL final queda fijo y cambia el path/drawdown.
    """

    iterations: int = 10_000
    initial_capital: float = 25_000.0
    seed: int | None = 42
    drawdown_threshold_pct: float = 20.0
    sample_with_replacement: bool = True


@dataclass(frozen=True)
class MonteCarloResult:
    iterations: int
    n_trades: int
    initial_capital: float
    seed: int | None
    sample_with_replacement: bool
    drawdown_threshold_pct: float
    final_pnl_mean: float
    final_pnl_percentiles: Percentiles
    max_drawdown_pct_mean: float
    max_drawdown_pct_percentiles: Percentiles
    max_drawdown_usd_percentiles: Percentiles
    losing_streak_percentiles: Percentiles
    probability_negative: float
    probability_drawdown_exceeds_threshold: float


@dataclass(frozen=True)
class BootstrapResult:
    iterations: int
    n_trades: int
    seed: int | None
    confidence_level: float
    expectancy_r_mean: float | None
    expectancy_r_ci: ConfidenceInterval | None
    profit_factor_mean: float
    profit_factor_ci: ConfidenceInterval
    winrate_pct_mean: float
    winrate_pct_ci: ConfidenceInterval
    avg_pnl_per_trade_mean: float
    avg_pnl_per_trade_ci: ConfidenceInterval
    probability_expectancy_le_zero: float
    expectancy_sign_source: str


@dataclass(frozen=True)
class RiskOfRuinResult:
    initial_capital: float
    ruin_threshold_pct: float
    loss_threshold_pct: float
    risk_of_ruin: float
    probability_loss_threshold: float
    suggested_min_capital: float
    capital_tolerance_drawdown_pct: float


@dataclass(frozen=True)
class DrawdownRiskResult:
    expected_max_drawdown_pct: float
    expected_max_drawdown_usd: float
    drawdown_pct_p95: float
    drawdown_usd_p95: float
    worst_losing_streak_p95: int


@dataclass(frozen=True)
class StressTestResult:
    scenario: str
    n_trades: int
    pnl_net: float
    pnl_delta: float
    profit_factor: float
    winrate_pct: float
    avg_pnl_per_trade: float
    expectancy_r: float | None
    max_drawdown_pct: float
    edge_survives: bool
    notes: str = ""


@dataclass(frozen=True)
class RobustnessReport:
    monte_carlo: MonteCarloResult
    bootstrap: BootstrapResult
    risk_of_ruin: RiskOfRuinResult
    drawdown_risk: DrawdownRiskResult
    stress_tests: list[StressTestResult] = field(default_factory=list)
    robust: bool = False
    warnings: list[str] = field(default_factory=list)

    def decision_engine_fields(self) -> dict[str, float | bool]:
        """Campos opcionales que entiende el Decision Engine."""

        top5 = next((s for s in self.stress_tests if s.scenario == "remove_top_5_winners"), None)
        cost = next((s for s in self.stress_tests if s.scenario == "costs_plus_reasonable"), None)
        return {
            "mc_probability_negative": self.monte_carlo.probability_negative,
            "mc_probability_extreme_drawdown": (
                self.monte_carlo.probability_drawdown_exceeds_threshold
            ),
            "bootstrap_probability_expectancy_le_zero": (
                self.bootstrap.probability_expectancy_le_zero
            ),
            "depends_on_few_winners": None if top5 is None else not top5.edge_survives,
            "cost_stress_survives": False if cost is None else cost.edge_survives,
        }
