#!/usr/bin/env python
"""Ejecuta una busqueda limitada del Strategy Lab."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nqbot.strategy_lab import (  # noqa: E402
    StrategySearchConfig,
    get_family,
    run_strategy_search,
    write_strategy_search_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--initial-capital", type=float, required=True)
    parser.add_argument("--max-variants", type=int, required=True)
    parser.add_argument("--iterations", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reports-dir", default=str(ROOT / "reports"))
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    family = get_family(args.family)
    cfg = StrategySearchConfig(
        family=family,
        symbol=args.symbol,
        data=args.data,
        initial_capital=args.initial_capital,
        max_variants=args.max_variants,
        iterations=args.iterations,
        seed=args.seed,
        reports_dir=args.reports_dir,
        config_path=args.config,
    )

    ranking = run_strategy_search(cfg)
    csv_path, summary_path = write_strategy_search_outputs(ranking, args.reports_dir)
    print("=" * 72)
    print("STRATEGY SEARCH COMPLETADA")
    print(f"Familia:     {family.name}")
    print(f"Estrategia:  {family.base_strategy}")
    print(f"Variantes:   {ranking.evaluated_variants}")
    print(f"Resultados:  {csv_path}")
    print(f"Resumen:     {summary_path}")
    print(f"Paper candidates: {len(ranking.paper_candidates)}")
    if ranking.ranked:
        top = ranking.ranked[0]
        print(f"Top robusto: {top.variant.variant_id} | score {top.rank_score:.2f}")
        print(f"Decision:    {top.decision_status}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
