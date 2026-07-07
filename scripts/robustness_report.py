#!/usr/bin/env python
"""Genera un reporte de robustez desde un CSV de trades ya existente.

No corre backtests, no modifica estrategias y no optimiza parametros.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nqbot.robustness import (  # noqa: E402
    MonteCarloConfig,
    RobustnessReport,
    estimate_risk,
    run_bootstrap,
    run_monte_carlo,
    run_stress_suite,
)


PNL_COLUMNS = ("pnl_net", "net_pnl", "pnl", "profit", "pnl_usd")
R_COLUMNS = ("r_multiple", "r", "R", "r_mult")


def _find_column(df: pd.DataFrame, candidates: tuple[str, ...], required: bool = True) -> str | None:
    normalized = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]
    if required:
        raise ValueError(
            "No pude identificar la columna de PnL. Candidatas: "
            + ", ".join(candidates)
        )
    return None


def _pct(value: float) -> str:
    return f"{value * 100.0:.1f}%"


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    return f"{value:.4f}"


def _classify(report: RobustnessReport) -> tuple[bool, list[str]]:
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


def _rows(report: RobustnessReport) -> list[dict[str, Any]]:
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
        {
            "section": "monte_carlo",
            "metric": "losing_streak_p95",
            "value": mc.losing_streak_percentiles["p95"],
        },
        {
            "section": "bootstrap",
            "metric": "probability_expectancy_le_zero",
            "value": boot.probability_expectancy_le_zero,
        },
        {"section": "bootstrap", "metric": "expectancy_r_mean", "value": boot.expectancy_r_mean},
        {
            "section": "bootstrap",
            "metric": "expectancy_r_ci_low",
            "value": None if boot.expectancy_r_ci is None else boot.expectancy_r_ci[0],
        },
        {
            "section": "bootstrap",
            "metric": "expectancy_r_ci_high",
            "value": None if boot.expectancy_r_ci is None else boot.expectancy_r_ci[1],
        },
        {"section": "bootstrap", "metric": "profit_factor_mean", "value": boot.profit_factor_mean},
        {"section": "bootstrap", "metric": "profit_factor_ci_low", "value": boot.profit_factor_ci[0]},
        {"section": "bootstrap", "metric": "profit_factor_ci_high", "value": boot.profit_factor_ci[1]},
        {"section": "bootstrap", "metric": "winrate_pct_mean", "value": boot.winrate_pct_mean},
        {"section": "bootstrap", "metric": "winrate_pct_ci_low", "value": boot.winrate_pct_ci[0]},
        {"section": "bootstrap", "metric": "winrate_pct_ci_high", "value": boot.winrate_pct_ci[1]},
        {
            "section": "bootstrap",
            "metric": "avg_pnl_per_trade_mean",
            "value": boot.avg_pnl_per_trade_mean,
        },
        {
            "section": "bootstrap",
            "metric": "avg_pnl_per_trade_ci_low",
            "value": boot.avg_pnl_per_trade_ci[0],
        },
        {
            "section": "bootstrap",
            "metric": "avg_pnl_per_trade_ci_high",
            "value": boot.avg_pnl_per_trade_ci[1],
        },
        {"section": "risk", "metric": "risk_of_ruin", "value": risk.risk_of_ruin},
        {
            "section": "risk",
            "metric": "probability_loss_threshold",
            "value": risk.probability_loss_threshold,
        },
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
                "metric": "expectancy_r",
                "value": stress.expectancy_r,
            },
            {
                "section": "stress",
                "scenario": stress.scenario,
                "metric": "edge_survives",
                "value": stress.edge_survives,
            },
        ])
    return rows


def _summary(report: RobustnessReport, trades_path: Path, pnl_column: str, r_column: str | None) -> str:
    mc = report.monte_carlo
    boot = report.bootstrap
    risk = report.risk_of_ruin
    dd = report.drawdown_risk
    by_name = {s.scenario: s for s in report.stress_tests}

    robust_label = "ROBUSTA" if report.robust else "FRAGIL"
    luck_risk = (
        "alto"
        if boot.probability_expectancy_le_zero > 0.25
        or boot.avg_pnl_per_trade_ci[0] <= 0
        else "bajo/moderado"
    )
    top5 = by_name.get("remove_top_5_winners")
    costs = by_name.get("costs_plus_reasonable")

    lines = [
        "# Quant Robustness Report",
        "",
        f"- **Trades:** `{trades_path}`",
        f"- **Columna PnL:** `{pnl_column}`",
        f"- **Columna R:** `{r_column or 'no disponible'}`",
        f"- **Iteraciones:** {mc.iterations:,}",
        f"- **Capital inicial:** {_money(mc.initial_capital)}",
        f"- **Seed:** {mc.seed}",
        "",
        f"## Veredicto: {robust_label}",
        "",
    ]
    if report.warnings:
        lines += [f"- {warning}" for warning in report.warnings]
    else:
        lines.append("- No aparecieron alertas contra los umbrales sugeridos.")

    lines += [
        "",
        "## Respuestas clave",
        "",
        f"- **Probabilidad de terminar negativo:** {_pct(mc.probability_negative)}.",
        (
            "- **Drawdown esperado:** "
            f"{dd.expected_max_drawdown_pct:.2f}% ({_money(dd.expected_max_drawdown_usd)})."
        ),
        (
            "- **Drawdown extremo percentil 95:** "
            f"{dd.drawdown_pct_p95:.2f}% ({_money(dd.drawdown_usd_p95)})."
        ),
        f"- **Peor racha esperada:** {dd.worst_losing_streak_p95} perdedoras consecutivas (p95).",
        (
            "- **Riesgo de ruina:** "
            f"{_pct(risk.risk_of_ruin)} para una perdida de {risk.ruin_threshold_pct:.0f}% del capital."
        ),
        (
            "- **Dependencia de pocos ganadores:** "
            + (
                "alta; al eliminar top 5 ganadores el edge no sobrevive."
                if top5 and not top5.edge_survives
                else "no critica bajo el test top 5."
            )
        ),
        (
            "- **Stress de costos:** "
            + (
                "sobrevive costos razonablemente mas altos."
                if costs and costs.edge_survives
                else "no sobrevive costos razonablemente mas altos."
            )
        ),
        (
            "- **Posible suerte/azar:** "
            f"riesgo {luck_risk}; bootstrap P(expectancia <= 0) = "
            f"{_pct(boot.probability_expectancy_le_zero)}."
        ),
        "",
        "## Bootstrap",
        "",
        (
            "- **Expectancia R:** "
            f"{_fmt(boot.expectancy_r_mean)}; IC {boot.confidence_level:.0%}: "
            + (
                "n/a"
                if boot.expectancy_r_ci is None
                else f"[{boot.expectancy_r_ci[0]:.4f}, {boot.expectancy_r_ci[1]:.4f}]"
            )
        ),
        (
            "- **Profit factor:** "
            f"{_fmt(boot.profit_factor_mean)}; IC {boot.confidence_level:.0%}: "
            f"[{boot.profit_factor_ci[0]:.4f}, {boot.profit_factor_ci[1]:.4f}]"
        ),
        (
            "- **Winrate:** "
            f"{boot.winrate_pct_mean:.2f}%; IC {boot.confidence_level:.0%}: "
            f"[{boot.winrate_pct_ci[0]:.2f}%, {boot.winrate_pct_ci[1]:.2f}%]"
        ),
        (
            "- **PnL medio por trade:** "
            f"{_money(boot.avg_pnl_per_trade_mean)}; IC {boot.confidence_level:.0%}: "
            f"[{_money(boot.avg_pnl_per_trade_ci[0])}, {_money(boot.avg_pnl_per_trade_ci[1])}]"
        ),
        "",
        "## Stress tests",
        "",
        "| Escenario | PnL neto | PF | Exp R | Sobrevive |",
        "|---|---:|---:|---:|---|",
    ]
    for stress in report.stress_tests:
        lines.append(
            f"| {stress.scenario} | {_money(stress.pnl_net)} | "
            f"{_fmt(stress.profit_factor)} | {_fmt(stress.expectancy_r)} | "
            f"{'si' if stress.edge_survives else 'no'} |"
        )

    lines += [
        "",
        "## Campos para Decision Engine",
        "",
        "- `mc_probability_negative`",
        "- `mc_probability_extreme_drawdown`",
        "- `bootstrap_probability_expectancy_le_zero`",
        "- `depends_on_few_winners`",
        "- `cost_stress_survives`",
        "",
        "Si estos campos se pasan a `ExperimentMetrics`, cualquier falla bloquea `PAPER_CANDIDATE`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", required=True, help="CSV de trades ya generado")
    parser.add_argument("--initial-capital", type=float, required=True)
    parser.add_argument("--iterations", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    trades_path = Path(args.trades)
    trades = pd.read_csv(trades_path)
    pnl_column = _find_column(trades, PNL_COLUMNS, required=True)
    assert pnl_column is not None
    r_column = _find_column(trades, R_COLUMNS, required=False)
    r_for_functions = r_column or "__missing_r_multiple__"

    mc = run_monte_carlo(
        trades,
        MonteCarloConfig(
            iterations=args.iterations,
            initial_capital=args.initial_capital,
            seed=args.seed,
            drawdown_threshold_pct=20.0,
            sample_with_replacement=True,
        ),
        pnl_column=pnl_column,
    )
    bootstrap = run_bootstrap(
        trades,
        iterations=args.iterations,
        seed=args.seed,
        pnl_column=pnl_column,
        r_column=r_for_functions,
    )
    risk, drawdown = estimate_risk(
        trades,
        initial_capital=args.initial_capital,
        iterations=args.iterations,
        seed=args.seed,
        pnl_column=pnl_column,
    )
    stress_tests = run_stress_suite(
        trades,
        initial_capital=args.initial_capital,
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
    robust, warnings = _classify(draft)
    report = RobustnessReport(
        monte_carlo=mc,
        bootstrap=bootstrap,
        risk_of_ruin=risk,
        drawdown_risk=drawdown,
        stress_tests=stress_tests,
        robust=robust,
        warnings=warnings,
    )

    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "robustness_report.csv"
    summary_path = out_dir / "robustness_report_summary.md"
    pd.DataFrame(_rows(report)).to_csv(csv_path, index=False)
    summary_path.write_text(_summary(report, trades_path, pnl_column, r_column), encoding="utf-8")

    print(f"Reporte CSV: {csv_path}")
    print(f"Resumen Markdown: {summary_path}")
    print(f"Veredicto: {'ROBUSTA' if robust else 'FRAGIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
