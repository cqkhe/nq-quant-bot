#!/usr/bin/env python
"""Evalúa un experimento contra los gates del Decision Engine.

Fuentes aceptadas:
  --report CARPETA   carpeta de reporte de backtest (trades.csv + equity_curve.csv):
                     fuente COMPLETA — computa meses positivos, dependencia de
                     pocos trades, racha, drawdown, etc.
  --csv ARCHIVO      CSV de un validador/comparador (fila por estrategia):
                     fuente PARCIAL — los criterios sin datos quedan como
                     'no evaluables' y bloquean la candidatura a paper.

Metadata que el motor no puede inferir de los números (declararla):
  --oos si|no        ¿el período evaluado es out-of-sample para esta hipótesis?
  --overlaps si|no   ¿los datos se solapan con el período de diseño?

Devuelve: estado final, criterios cumplidos/fallidos/no evaluables, motivo y
recomendación. Guarda la evaluación en research/experiments/ (histórico).

Ejemplos:
    python scripts/evaluate_experiment.py --report reports/20260704_125049_MNQ_daytrading_vwap_liquidity_rr2 --oos no --overlaps si
    python scripts/evaluate_experiment.py --csv reports/atr_filter_validation_MNQ_2024_full_1m_ninjatrader_combined_clean.csv --strategy daytrading_vwap_liquidity_rr2_no_midday_atr_filter --oos si --overlaps no

No corre backtests ni modifica estrategias: solo evalúa reportes existentes.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nqbot.research.decision_engine import (   # noqa: E402
    evaluate,
    metrics_from_comparison_csv,
    metrics_from_report_folder,
)


def _tri(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() in ("si", "sí", "yes", "true", "1")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--report", help="Carpeta de reporte de backtest (fuente completa)")
    source.add_argument("--csv", help="CSV de validador/comparador (fuente parcial)")
    ap.add_argument("--strategy", help="Nombre de la estrategia (si el CSV tiene varias)")
    ap.add_argument("--oos", choices=["si", "no"], help="¿El período es out-of-sample?")
    ap.add_argument("--overlaps", choices=["si", "no"],
                    help="¿Los datos se solapan con el período de diseño?")
    ap.add_argument("--no-save", action="store_true",
                    help="No guardar la evaluación en research/experiments/")
    args = ap.parse_args()

    is_oos = _tri(args.oos)
    overlaps = _tri(args.overlaps)

    if args.report:
        metrics = metrics_from_report_folder(args.report, is_out_of_sample=is_oos,
                                             overlaps_design_period=overlaps)
    else:
        metrics = metrics_from_comparison_csv(args.csv, strategy=args.strategy,
                                              is_out_of_sample=is_oos,
                                              overlaps_design_period=overlaps)

    decision = evaluate(metrics)
    print(decision.to_text())

    if not args.no_save:
        out_dir = ROOT / "research" / "experiments"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in metrics.strategy)
        out_file = out_dir / f"EVAL_{stamp}_{safe_name}.md"
        out_file.write_text(decision.to_markdown(), encoding="utf-8")
        print(f"\nEvaluación guardada en: {out_file}")
        print("Recordatorio: si esto motiva una decisión, crear la ficha DXXX en "
              "research/decisions/ y actualizar el índice.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
