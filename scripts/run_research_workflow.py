#!/usr/bin/env python
"""Ejecuta Research Factory: backtest -> robustness -> Decision Engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from nqbot.research.factory import ResearchWorkflowConfig, run_research_workflow  # noqa: E402


def _tri(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() in ("si", "yes", "true", "1")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--initial-capital", type=float, required=True)
    parser.add_argument("--iterations", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hypothesis-id")
    parser.add_argument("--oos", choices=("si", "no"), help="Declarar si el dataset es OOS")
    parser.add_argument("--overlaps", choices=("si", "no"), help="Declarar si solapa el periodo de diseno")
    parser.add_argument("--reports-dir", default=str(ROOT / "reports"))
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    cfg = ResearchWorkflowConfig(
        strategy=args.strategy,
        symbol=args.symbol,
        data=Path(args.data),
        initial_capital=args.initial_capital,
        iterations=args.iterations,
        seed=args.seed,
        hypothesis_id=args.hypothesis_id,
        reports_dir=Path(args.reports_dir),
        research_dir=ROOT / "research" / "experiments",
        config_path=Path(args.config),
        is_out_of_sample=_tri(args.oos),
        overlaps_design_period=_tri(args.overlaps),
    )

    result = run_research_workflow(cfg)
    print("=" * 72)
    print("RESEARCH WORKFLOW COMPLETADO")
    print(f"Estrategia: {cfg.strategy}")
    print(f"Reporte:    {result.report_folder}")
    print(f"Trades:     {result.trades_csv}")
    print(f"Robustez:   {'ROBUSTA' if result.robustness_report.robust else 'FRAGIL'}")
    print(f"Decision:   {result.decision.status.value}")
    print(f"Registro:   {result.research_record}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
