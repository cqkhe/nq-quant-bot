"""Ejecucion de busquedas limitadas de variantes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

from nqbot.backtesting.engine import BacktestEngine
from nqbot.backtesting.metrics import compute_metrics
from nqbot.backtesting.models import BacktestResult
from nqbot.config.settings import AccountConfig, Config
from nqbot.data.loader import parse_ohlcv_csv
from nqbot.data.quality import DataQualityChecker
from nqbot.data.validators import validate_ohlcv
from nqbot.research.decision_engine import evaluate
from nqbot.research.factory import build_robustness_report
from nqbot.research.models import ExperimentMetrics
from nqbot.strategies.registry import create_strategy
from nqbot.utils.logger import setup_logger
from nqbot.utils.sessions import filter_to_trade_session

from .filters import apply_filters
from .models import (
    ExperimentResult,
    StrategyRanking,
    StrategySearchConfig,
    StrategyVariant,
    result_to_row,
)
from .ranking import rank_results
from .variants import generate_variants


VariantEvaluator = Callable[[StrategyVariant, StrategySearchConfig], ExperimentResult]


def run_strategy_search(
    cfg: StrategySearchConfig,
    evaluator: VariantEvaluator | None = None,
) -> StrategyRanking:
    if cfg.max_variants <= 0:
        raise ValueError("max_variants debe ser > 0")
    if cfg.iterations <= 0:
        raise ValueError("iterations debe ser > 0")
    if cfg.initial_capital <= 0:
        raise ValueError("initial_capital debe ser > 0")

    variants = generate_variants(cfg.family, max_variants=cfg.max_variants, seed=cfg.seed)
    context = None if evaluator else _load_context(cfg)
    results: list[ExperimentResult] = []

    for variant in variants:
        try:
            if evaluator is not None:
                result = evaluator(variant, cfg)
            else:
                assert context is not None
                result = _evaluate_variant(variant, cfg, context)
        except Exception as exc:  # pragma: no cover - defensive audit path
            result = ExperimentResult(
                variant=variant,
                n_trades=0,
                pnl_net=0.0,
                profit_factor=None,
                expectancy_r=None,
                max_drawdown_pct=None,
                error=str(exc),
            )
        results.append(apply_filters(result, cfg.filters))

    ranked = rank_results(results, cfg.filters)
    return StrategyRanking(
        family=cfg.family,
        results=ranked,
        generated_variants=len(variants),
        evaluated_variants=len(results),
    )


def write_strategy_search_outputs(
    ranking: StrategyRanking,
    reports_dir: str | Path,
) -> tuple[Path, Path]:
    out_dir = Path(reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "strategy_search_results.csv"
    summary_path = out_dir / "strategy_search_summary.md"

    pd.DataFrame([result_to_row(r) for r in ranking.ranked]).to_csv(csv_path, index=False)
    summary_path.write_text(_summary_markdown(ranking, csv_path), encoding="utf-8")
    return csv_path, summary_path


def _load_context(cfg: StrategySearchConfig) -> dict[str, Any]:
    logger = setup_logger()
    config = Config.from_yaml(cfg.config_path)
    config = replace(config, account=AccountConfig(initial_capital=cfg.initial_capital))
    contract = config.contract(cfg.symbol)

    df_raw, meta = parse_ohlcv_csv(cfg.data, logger, timezone=config.session.timezone)
    quality = DataQualityChecker(
        config.session, config.data_quality, calendar=config.calendar, logger=logger
    ).check(df_raw, meta)
    if quality.has_errors:
        raise ValueError("Los datos no son aptos para backtest en Strategy Lab")

    df, warnings = validate_ohlcv(df_raw)
    for warning in warnings:
        logger.warning("Datos: %s", warning)
    df = filter_to_trade_session(df, config.session)
    if df.empty:
        raise ValueError("No quedaron barras dentro de la sesion operada")

    return {"config": config, "contract": contract, "df": df, "logger": logger}


def _evaluate_variant(
    variant: StrategyVariant,
    cfg: StrategySearchConfig,
    context: dict[str, Any],
) -> ExperimentResult:
    config: Config = context["config"]
    contract = context["contract"]
    df = context["df"]
    logger = context["logger"]

    strategy = create_strategy(variant.strategy_name, variant.params, contract)
    backtest = BacktestEngine(config, contract, strategy, logger).run(df)
    metrics = compute_metrics(backtest)
    return experiment_result_from_backtest(variant, cfg, backtest, metrics)


def experiment_result_from_backtest(
    variant: StrategyVariant,
    cfg: StrategySearchConfig,
    backtest: BacktestResult,
    metrics: dict[str, Any] | None = None,
) -> ExperimentResult:
    metrics = metrics or compute_metrics(backtest)
    if not backtest.trades:
        result = ExperimentResult(
            variant=variant,
            n_trades=0,
            pnl_net=float(metrics.get("total_net_pnl", 0.0)),
            profit_factor=None,
            expectancy_r=None,
            max_drawdown_pct=float(metrics.get("max_drawdown_pct", 0.0)),
            robustness_passed=False,
        )
        decision = evaluate(_decision_metrics(result, metrics, None))
        result.decision_status = decision.status.value
        return result

    trades = pd.DataFrame([asdict(t) for t in backtest.trades])
    temp_csv = _trades_frame_to_temp_csv(trades)
    try:
        robustness, _, _ = build_robustness_report(
            temp_csv,
            initial_capital=cfg.initial_capital,
            iterations=cfg.iterations,
            seed=cfg.seed,
        )
    finally:
        temp_csv.unlink(missing_ok=True)

    fields = robustness.decision_engine_fields()
    result = ExperimentResult(
        variant=variant,
        n_trades=int(metrics["n_trades"]),
        pnl_net=float(metrics["total_net_pnl"]),
        profit_factor=_none_if_nan(metrics.get("profit_factor")),
        expectancy_r=_none_if_nan(metrics.get("expectancy_r")),
        max_drawdown_pct=_none_if_nan(metrics.get("max_drawdown_pct")),
        mc_probability_negative=float(fields["mc_probability_negative"]),
        mc_probability_extreme_drawdown=float(fields["mc_probability_extreme_drawdown"]),
        bootstrap_probability_expectancy_le_zero=float(
            fields["bootstrap_probability_expectancy_le_zero"]
        ),
        cost_stress_survives=bool(fields["cost_stress_survives"]),
        depends_on_top_winners=(
            None if fields["depends_on_few_winners"] is None
            else bool(fields["depends_on_few_winners"])
        ),
        robustness_passed=robustness.robust,
    )
    decision = evaluate(_decision_metrics(result, metrics, trades))
    result.decision_status = decision.status.value
    return result


def _decision_metrics(
    result: ExperimentResult,
    metrics: dict[str, Any],
    trades: pd.DataFrame | None,
) -> ExperimentMetrics:
    pnl_without_top5: float | None = None
    n_months: int | None = None
    pct_positive_months: float | None = None
    if trades is not None and len(trades):
        pnl = trades["pnl_net"].astype(float)
        wins = pnl > 0
        pnl_without_top5 = float(pnl.sum() - pnl[wins].nlargest(5).sum())
        entry = pd.to_datetime(trades["entry_time"])
        monthly = pnl.groupby(entry.dt.to_period("M").astype(str).to_numpy()).sum()
        n_months = len(monthly)
        pct_positive_months = float((monthly > 0).mean() * 100.0) if len(monthly) else None

    return ExperimentMetrics(
        source=f"strategy_lab:{result.variant.variant_id}",
        strategy=result.variant.label,
        n_trades=result.n_trades,
        pnl_net=result.pnl_net,
        profit_factor=result.profit_factor,
        expectancy_r=result.expectancy_r,
        winrate_pct=_none_if_nan(metrics.get("winrate_pct")),
        max_drawdown_usd=_none_if_nan(metrics.get("max_drawdown")),
        max_drawdown_pct=result.max_drawdown_pct,
        max_losing_streak=metrics.get("max_consecutive_losses"),
        n_months=n_months,
        pct_positive_months=pct_positive_months,
        pnl_without_top5=pnl_without_top5,
        is_out_of_sample=None,
        overlaps_design_period=None,
        mc_probability_negative=result.mc_probability_negative,
        mc_probability_extreme_drawdown=result.mc_probability_extreme_drawdown,
        bootstrap_probability_expectancy_le_zero=(
            result.bootstrap_probability_expectancy_le_zero
        ),
        depends_on_few_winners=result.depends_on_top_winners,
        cost_stress_survives=result.cost_stress_survives,
    )


def _trades_frame_to_temp_csv(trades: pd.DataFrame) -> Path:
    import tempfile

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix="_strategy_lab_trades.csv",
        delete=False,
        encoding="utf-8",
        newline="",
    )
    path = Path(handle.name)
    try:
        trades.to_csv(handle, index=False)
    finally:
        handle.close()
    return path


def _summary_markdown(ranking: StrategyRanking, csv_path: Path) -> str:
    lines = [
        "# Strategy Search Summary",
        "",
        f"- **Family:** `{ranking.family.name}`",
        f"- **Base strategy:** `{ranking.family.base_strategy}`",
        f"- **Generated variants:** {ranking.generated_variants}",
        f"- **Evaluated variants:** {ranking.evaluated_variants}",
        f"- **Results CSV:** `{csv_path}`",
        f"- **PAPER_CANDIDATE count:** {len(ranking.paper_candidates)}",
        "",
        "## Ranking",
        "",
        "| Rank | Variant | Score | Decision | Filters | Robust | Trades | PF | Exp R | DD % |",
        "|---:|---|---:|---|---|---|---:|---:|---:|---:|",
    ]
    for i, result in enumerate(ranking.ranked, start=1):
        lines.append(
            f"| {i} | `{result.variant.variant_id}` | {result.rank_score:.2f} | "
            f"{result.decision_status} | {'pass' if result.passed_filters else 'fail'} | "
            f"{'pass' if result.robustness_passed else 'fail'} | {result.n_trades} | "
            f"{_fmt(result.profit_factor)} | {_fmt(result.expectancy_r)} | "
            f"{_fmt(result.max_drawdown_pct)} |"
        )
    lines += [
        "",
        "## Nota metodologica",
        "",
        "El ranking no ordena por PnL neto total. Penaliza drawdown, baja muestra, "
        "fragilidad por Monte Carlo/Bootstrap, dependencia de top winners y falla "
        "ante costos/slippage. Una variante solo puede figurar como PAPER_CANDIDATE "
        "si tambien pasa Decision Engine y Robustness Engine.",
        "",
    ]
    return "\n".join(lines)


def _none_if_nan(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return float(value)


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


__all__ = [
    "VariantEvaluator",
    "experiment_result_from_backtest",
    "run_strategy_search",
    "write_strategy_search_outputs",
]
