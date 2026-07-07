"""Research Factory: backtest -> robustness -> Decision Engine -> registro.

El workflow coordina motores existentes. No cambia estrategias, reglas de
entrada/salida ni risk manager.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from nqbot.robustness import (
    MonteCarloConfig,
    RobustnessReport,
    estimate_risk,
    run_bootstrap,
    run_monte_carlo,
    run_stress_suite,
)
from nqbot.research.decision_engine import evaluate, metrics_from_report_folder
from nqbot.research.models import Decision


BacktestRunner = Callable[[list[str]], int]

PNL_COLUMNS = ("pnl_net", "net_pnl", "pnl", "profit", "pnl_usd")
R_COLUMNS = ("r_multiple", "r", "R", "r_mult")


@dataclass(frozen=True)
class ResearchWorkflowConfig:
    strategy: str
    symbol: str
    data: Path
    initial_capital: float
    iterations: int
    seed: int
    hypothesis_id: str | None = None
    reports_dir: Path = Path("reports")
    research_dir: Path = Path("research/experiments")
    config_path: Path = Path("config/config.yaml")
    is_out_of_sample: bool | None = None
    overlaps_design_period: bool | None = None


@dataclass(frozen=True)
class ResearchWorkflowResult:
    report_folder: Path
    trades_csv: Path
    robustness_csv: Path
    robustness_summary: Path
    decision_summary: Path
    research_record: Path
    decision: Decision
    robustness_report: RobustnessReport


def run_research_workflow(
    cfg: ResearchWorkflowConfig,
    backtest_runner: BacktestRunner | None = None,
) -> ResearchWorkflowResult:
    """Ejecuta el flujo completo de investigacion reproducible."""

    if cfg.iterations <= 0:
        raise ValueError("iterations debe ser > 0")
    if cfg.initial_capital <= 0:
        raise ValueError("initial_capital debe ser > 0")

    reports_dir = Path(cfg.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    before = _report_folders(reports_dir)

    code = _run_backtest(cfg, backtest_runner)
    if code != 0:
        raise RuntimeError(f"El backtest fallo con exit code {code}")

    report_folder = _find_new_report_folder(reports_dir, before, cfg.strategy, cfg.symbol)
    trades_csv = report_folder / "trades.csv"
    if not trades_csv.exists():
        raise FileNotFoundError(f"No se encontro trades.csv en {report_folder}")

    robustness_report, pnl_column, r_column = build_robustness_report(
        trades_csv,
        initial_capital=cfg.initial_capital,
        iterations=cfg.iterations,
        seed=cfg.seed,
    )
    robustness_csv, robustness_summary = write_robustness_outputs(
        report_folder, robustness_report, trades_csv, pnl_column, r_column
    )

    metrics = metrics_from_report_folder(
        report_folder,
        is_out_of_sample=cfg.is_out_of_sample,
        overlaps_design_period=cfg.overlaps_design_period,
    )
    metrics.strategy = cfg.strategy
    for field_name, value in robustness_report.decision_engine_fields().items():
        setattr(metrics, field_name, value)
    decision = evaluate(metrics)

    decision_summary = report_folder / "decision_engine_summary.md"
    decision_summary.write_text(decision.to_markdown(), encoding="utf-8")

    research_record = write_research_record(
        cfg=cfg,
        report_folder=report_folder,
        trades_csv=trades_csv,
        robustness_csv=robustness_csv,
        robustness_summary=robustness_summary,
        decision_summary=decision_summary,
        decision=decision,
        robustness_report=robustness_report,
    )

    return ResearchWorkflowResult(
        report_folder=report_folder,
        trades_csv=trades_csv,
        robustness_csv=robustness_csv,
        robustness_summary=robustness_summary,
        decision_summary=decision_summary,
        research_record=research_record,
        decision=decision,
        robustness_report=robustness_report,
    )


def build_robustness_report(
    trades_csv: Path,
    *,
    initial_capital: float,
    iterations: int,
    seed: int,
) -> tuple[RobustnessReport, str, str | None]:
    trades = pd.read_csv(trades_csv)
    pnl_column = _find_column(trades, PNL_COLUMNS, required=True)
    assert pnl_column is not None
    r_column = _find_column(trades, R_COLUMNS, required=False)
    r_for_functions = r_column or "__missing_r_multiple__"

    mc = run_monte_carlo(
        trades,
        MonteCarloConfig(
            iterations=iterations,
            initial_capital=initial_capital,
            seed=seed,
            drawdown_threshold_pct=20.0,
            sample_with_replacement=True,
        ),
        pnl_column=pnl_column,
    )
    bootstrap = run_bootstrap(
        trades,
        iterations=iterations,
        seed=seed,
        pnl_column=pnl_column,
        r_column=r_for_functions,
    )
    risk, drawdown = estimate_risk(
        trades,
        initial_capital=initial_capital,
        iterations=iterations,
        seed=seed,
        pnl_column=pnl_column,
    )
    stress_tests = run_stress_suite(
        trades,
        initial_capital=initial_capital,
        pnl_column=pnl_column,
        r_column=r_for_functions,
    )

    draft = RobustnessReport(
        monte_carlo=mc,
        bootstrap=bootstrap,
        risk_of_ruin=risk,
        drawdown_risk=drawdown,
        stress_tests=stress_tests,
    )
    robust, warnings = classify_robustness(draft)
    report = RobustnessReport(
        monte_carlo=mc,
        bootstrap=bootstrap,
        risk_of_ruin=risk,
        drawdown_risk=drawdown,
        stress_tests=stress_tests,
        robust=robust,
        warnings=warnings,
    )
    return report, pnl_column, r_column


def classify_robustness(report: RobustnessReport) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    mc = report.monte_carlo
    boot = report.bootstrap
    risk = report.risk_of_ruin

    if mc.probability_negative > 0.20:
        warnings.append("Monte Carlo muestra probabilidad alta de terminar negativo.")
    if mc.probability_drawdown_exceeds_threshold > 0.20:
        warnings.append("Monte Carlo muestra riesgo alto de drawdown extremo.")
    if boot.probability_expectancy_le_zero > 0.25:
        warnings.append("Bootstrap muestra probabilidad alta de expectancia no positiva.")
    if risk.risk_of_ruin > 0.05:
        warnings.append("El riesgo de ruina estimado supera 5%.")

    by_name = {s.scenario: s for s in report.stress_tests}
    if by_name.get("remove_top_5_winners") and not by_name["remove_top_5_winners"].edge_survives:
        warnings.append("El resultado depende demasiado de los 5 mejores ganadores.")
    if by_name.get("costs_plus_reasonable") and not by_name["costs_plus_reasonable"].edge_survives:
        warnings.append("El edge no sobrevive a costos razonablemente mas altos.")
    if by_name.get("edge_minus_10pct") and not by_name["edge_minus_10pct"].edge_survives:
        warnings.append("Una degradacion moderada del edge borra la ventaja.")

    return len(warnings) == 0, warnings


def write_robustness_outputs(
    report_folder: Path,
    report: RobustnessReport,
    trades_csv: Path,
    pnl_column: str,
    r_column: str | None,
) -> tuple[Path, Path]:
    csv_path = report_folder / "robustness_report.csv"
    summary_path = report_folder / "robustness_report_summary.md"
    pd.DataFrame(_robustness_rows(report)).to_csv(csv_path, index=False)
    summary_path.write_text(
        _robustness_summary(report, trades_csv, pnl_column, r_column),
        encoding="utf-8",
    )
    return csv_path, summary_path


def write_research_record(
    *,
    cfg: ResearchWorkflowConfig,
    report_folder: Path,
    trades_csv: Path,
    robustness_csv: Path,
    robustness_summary: Path,
    decision_summary: Path,
    decision: Decision,
    robustness_report: RobustnessReport,
) -> Path:
    research_dir = Path(cfg.research_dir)
    research_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_strategy = _safe_name(cfg.strategy)
    hyp = f"{cfg.hypothesis_id}_" if cfg.hypothesis_id else ""
    record_path = research_dir / f"WORKFLOW_{stamp}_{hyp}{safe_strategy}.md"
    record_path.write_text(
        _workflow_record_markdown(
            cfg=cfg,
            report_folder=report_folder,
            trades_csv=trades_csv,
            robustness_csv=robustness_csv,
            robustness_summary=robustness_summary,
            decision_summary=decision_summary,
            decision=decision,
            robustness_report=robustness_report,
        ),
        encoding="utf-8",
    )
    return record_path


def _run_backtest(cfg: ResearchWorkflowConfig, runner: BacktestRunner | None) -> int:
    if runner is None:
        main_module = importlib.import_module("main")
        runner = main_module.main

    argv = [
        "--mode", "backtest",
        "--symbol", cfg.symbol,
        "--strategy", cfg.strategy,
        "--data", str(cfg.data),
        "--capital", str(cfg.initial_capital),
        "--reports-dir", str(cfg.reports_dir),
        "--config", str(cfg.config_path),
    ]
    return int(runner(argv))


def _report_folders(reports_dir: Path) -> set[Path]:
    if not reports_dir.exists():
        return set()
    return {p.resolve() for p in reports_dir.iterdir() if p.is_dir()}


def _find_new_report_folder(
    reports_dir: Path,
    before: set[Path],
    strategy: str,
    symbol: str,
) -> Path:
    after = _report_folders(reports_dir)
    created = [p for p in after - before if p.is_dir()]
    with_trades = [p for p in created if (p / "trades.csv").exists()]
    matching = [
        p for p in with_trades
        if symbol in p.name and strategy in p.name
    ]
    candidates = matching or with_trades
    if not candidates:
        created_names = ", ".join(str(p) for p in created) or "ninguna carpeta nueva"
        raise FileNotFoundError(
            "No se pudo detectar una carpeta nueva con trades.csv. "
            f"Carpetas nuevas: {created_names}"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _find_column(df: pd.DataFrame, candidates: tuple[str, ...], required: bool) -> str | None:
    normalized = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]
    if required:
        raise ValueError("No se encontro columna de PnL en trades.csv")
    return None


def _robustness_rows(report: RobustnessReport) -> list[dict[str, Any]]:
    mc = report.monte_carlo
    boot = report.bootstrap
    risk = report.risk_of_ruin
    dd = report.drawdown_risk
    rows: list[dict[str, Any]] = [
        {"section": "monte_carlo", "metric": "probability_negative", "value": mc.probability_negative},
        {
            "section": "monte_carlo",
            "metric": "probability_drawdown_exceeds_threshold",
            "value": mc.probability_drawdown_exceeds_threshold,
        },
        {"section": "monte_carlo", "metric": "final_pnl_p05", "value": mc.final_pnl_percentiles["p05"]},
        {"section": "monte_carlo", "metric": "final_pnl_p50", "value": mc.final_pnl_percentiles["p50"]},
        {"section": "monte_carlo", "metric": "final_pnl_p95", "value": mc.final_pnl_percentiles["p95"]},
        {
            "section": "monte_carlo",
            "metric": "max_drawdown_pct_p95",
            "value": mc.max_drawdown_pct_percentiles["p95"],
        },
        {"section": "monte_carlo", "metric": "losing_streak_p95", "value": mc.losing_streak_percentiles["p95"]},
        {
            "section": "bootstrap",
            "metric": "probability_expectancy_le_zero",
            "value": boot.probability_expectancy_le_zero,
        },
        {"section": "bootstrap", "metric": "expectancy_r_mean", "value": boot.expectancy_r_mean},
        {"section": "bootstrap", "metric": "profit_factor_mean", "value": boot.profit_factor_mean},
        {"section": "bootstrap", "metric": "winrate_pct_mean", "value": boot.winrate_pct_mean},
        {
            "section": "bootstrap",
            "metric": "avg_pnl_per_trade_mean",
            "value": boot.avg_pnl_per_trade_mean,
        },
        {"section": "risk", "metric": "risk_of_ruin", "value": risk.risk_of_ruin},
        {"section": "risk", "metric": "probability_loss_threshold", "value": risk.probability_loss_threshold},
        {"section": "risk", "metric": "suggested_min_capital", "value": risk.suggested_min_capital},
        {"section": "risk", "metric": "expected_max_drawdown_pct", "value": dd.expected_max_drawdown_pct},
        {"section": "risk", "metric": "drawdown_pct_p95", "value": dd.drawdown_pct_p95},
        {"section": "risk", "metric": "worst_losing_streak_p95", "value": dd.worst_losing_streak_p95},
    ]
    for stress in report.stress_tests:
        rows.extend([
            {"section": "stress", "scenario": stress.scenario, "metric": "pnl_net", "value": stress.pnl_net},
            {
                "section": "stress",
                "scenario": stress.scenario,
                "metric": "profit_factor",
                "value": stress.profit_factor,
            },
            {
                "section": "stress",
                "scenario": stress.scenario,
                "metric": "edge_survives",
                "value": stress.edge_survives,
            },
        ])
    return rows


def _robustness_summary(
    report: RobustnessReport,
    trades_csv: Path,
    pnl_column: str,
    r_column: str | None,
) -> str:
    mc = report.monte_carlo
    boot = report.bootstrap
    dd = report.drawdown_risk
    risk = report.risk_of_ruin
    verdict = "ROBUSTA" if report.robust else "FRAGIL"
    lines = [
        "# Robustness summary",
        "",
        f"- **Trades:** `{trades_csv}`",
        f"- **PnL column:** `{pnl_column}`",
        f"- **R column:** `{r_column or 'no disponible'}`",
        f"- **Veredicto:** **{verdict}**",
        "",
        "## Key metrics",
        "",
        f"- Probability negative: {mc.probability_negative:.1%}",
        f"- Probability extreme drawdown: {mc.probability_drawdown_exceeds_threshold:.1%}",
        f"- Expected max drawdown: {dd.expected_max_drawdown_pct:.2f}%",
        f"- Max drawdown p95: {dd.drawdown_pct_p95:.2f}%",
        f"- Worst losing streak p95: {dd.worst_losing_streak_p95}",
        f"- Risk of ruin: {risk.risk_of_ruin:.1%}",
        f"- Bootstrap P(expectancy <= 0): {boot.probability_expectancy_le_zero:.1%}",
        "",
        "## Warnings",
        "",
    ]
    lines += [f"- {warning}" for warning in report.warnings] or ["- Sin alertas."]
    lines += [
        "",
        "## Stress tests",
        "",
        "| Scenario | PnL net | Profit factor | Edge survives |",
        "|---|---:|---:|---|",
    ]
    for stress in report.stress_tests:
        lines.append(
            f"| {stress.scenario} | {stress.pnl_net:.2f} | "
            f"{stress.profit_factor:.4f} | {'si' if stress.edge_survives else 'no'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _workflow_record_markdown(
    *,
    cfg: ResearchWorkflowConfig,
    report_folder: Path,
    trades_csv: Path,
    robustness_csv: Path,
    robustness_summary: Path,
    decision_summary: Path,
    decision: Decision,
    robustness_report: RobustnessReport,
) -> str:
    robust_label = "ROBUSTA" if robustness_report.robust else "FRAGIL"
    lines = [
        f"# Research Workflow - {cfg.strategy}",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Fecha | {datetime.now().date().isoformat()} |",
        f"| Hipotesis | {cfg.hypothesis_id or 'no declarada'} |",
        f"| Estrategia | `{cfg.strategy}` |",
        f"| Simbolo | `{cfg.symbol}` |",
        f"| Dataset | `{cfg.data}` |",
        f"| Capital inicial | {cfg.initial_capital:.2f} |",
        f"| Iteraciones robustez | {cfg.iterations} |",
        f"| Seed | {cfg.seed} |",
        f"| OOS declarado | {cfg.is_out_of_sample} |",
        f"| Solapa diseno | {cfg.overlaps_design_period} |",
        "",
        "## Pipeline",
        "",
        "1. Hypothesis metadata",
        "2. Backtest",
        "3. trades.csv",
        "4. Robustness Engine",
        "5. Decision Engine",
        "6. Registro en Research Memory",
        "",
        "## Artefactos",
        "",
        f"- Backtest report: `{report_folder}`",
        f"- Trades: `{trades_csv}`",
        f"- Robustness CSV: `{robustness_csv}`",
        f"- Robustness summary: `{robustness_summary}`",
        f"- Decision Engine summary: `{decision_summary}`",
        "",
        "## Resultado",
        "",
        f"- Robustness Engine: **{robust_label}**",
        f"- Decision Engine: **{decision.status.value}**",
        "",
        "## Motivos del Decision Engine",
        "",
    ]
    lines += [f"- {reason}" for reason in decision.reasons]
    lines += [
        "",
        "## Bloqueo operativo",
        "",
        "Este registro no habilita paper/live/fondeo por si solo. "
        "Si el estado fuera PAPER_CANDIDATE, requiere decision humana DXXX.",
        "",
    ]
    return "\n".join(lines)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)


__all__ = [
    "ResearchWorkflowConfig",
    "ResearchWorkflowResult",
    "build_robustness_report",
    "classify_robustness",
    "run_research_workflow",
    "write_research_record",
    "write_robustness_outputs",
]
