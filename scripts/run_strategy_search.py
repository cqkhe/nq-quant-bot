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
    registered_families,
    run_strategy_search,
    run_strategy_search_suite,
    write_strategy_search_outputs,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--initial-capital", type=float, required=True)
    parser.add_argument("--max-variants", type=int)
    parser.add_argument("--max-variants-per-family", type=int)
    parser.add_argument("--iterations", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reports-dir", default=str(ROOT / "reports"))
    parser.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    if args.family == "all":
        limit = args.max_variants_per_family or args.max_variants
        if limit is None:
            raise SystemExit("--family all requiere --max-variants-per-family o --max-variants")
        all_families = registered_families()
        executable_families = [family for family in all_families if family.implemented]
        configs = [
            StrategySearchConfig(
                family=family,
                symbol=args.symbol,
                data=args.data,
                initial_capital=args.initial_capital,
                max_variants=limit,
                iterations=args.iterations,
                seed=args.seed,
                reports_dir=args.reports_dir,
                config_path=args.config,
            )
            for family in executable_families
        ]
        ranking = run_strategy_search_suite(configs, registered_families=all_families)
        family_label = "all"
        base_strategy = "multiple"
        evaluated = ranking.evaluated_variants
        paper_count = len(ranking.paper_candidates)
        top = ranking.ranked[0] if ranking.ranked else None
        registered_count = len(all_families)
        executable_count = len(executable_families)
        scaffold_count = registered_count - executable_count
    else:
        if args.max_variants is None:
            raise SystemExit("--max-variants es obligatorio para una familia individual")
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
        family_label = family.name
        base_strategy = family.base_strategy
        evaluated = ranking.evaluated_variants
        paper_count = len(ranking.paper_candidates)
        top = ranking.ranked[0] if ranking.ranked else None
        registered_count = 1
        executable_count = 1 if family.implemented else 0
        scaffold_count = 0 if family.implemented else 1

    csv_path, summary_path, family_summary_path = write_strategy_search_outputs(
        ranking, args.reports_dir
    )
    print("=" * 72)
    print("STRATEGY SEARCH COMPLETADA")
    print(f"Familia:     {family_label}")
    print(f"Estrategia:  {base_strategy}")
    print(f"Registradas: {registered_count}")
    print(f"Ejecutables: {executable_count}")
    print(f"Scaffolding: {scaffold_count}")
    print(f"Variantes:   {evaluated}")
    print(f"Resultados:  {csv_path}")
    print(f"Resumen:     {summary_path}")
    print(f"Resumen familias: {family_summary_path}")
    print(f"Paper candidates: {paper_count}")
    if top is not None:
        print(f"Top robusto: {top.variant.variant_id} | score {top.rank_score:.2f}")
        print(f"Decision:    {top.decision_status}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
