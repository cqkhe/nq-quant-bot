#!/usr/bin/env python
"""Crea una ficha de hipótesis en research/hypotheses/ vía el Hypothesis Engine.

La ficha se registra ANTES de mirar resultados. Con solo id/título/tipo se
crea un esqueleto en estado PROPOSED con los campos pendientes marcados; el
motor reporta qué falta para poder congelarla como DESIGNED.

Ejemplos:
    python scripts/create_hypothesis.py --id H005 --title "Mi idea" --type EXIT_LOGIC
    python scripts/create_hypothesis.py --id H005 --title "Mi idea" --type FILTER \
        --statement "..." --mechanism "..." --impact ALTO --clarity MEDIA --cf-risk MEDIO \
        --design-dataset data/processed/X.csv --oos-dataset "PENDIENTE jul-2026+" --oos-pending \
        --acceptance "expR mejora vs base" --rejection "flip de signo entre períodos"

No corre backtests ni modifica estrategias.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nqbot.research import (                     # noqa: E402
    CausalClarity,
    ExpectedImpact,
    Hypothesis,
    HypothesisRisk,
    HypothesisStatus,
    HypothesisType,
    HypothesisValidationPlan,
    compute_priority,
    missing_for_design,
    save_hypothesis,
    validate_hypothesis,
)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--id", required=True, help="Formato HNNN (p.ej. H005)")
    ap.add_argument("--title", required=True)
    ap.add_argument("--type", required=True, choices=[t.value for t in HypothesisType])
    ap.add_argument("--statement", default="", help="Hipótesis medible y falsable")
    ap.add_argument("--mechanism", default="", help="Mecanismo causal esperado")
    ap.add_argument("--origin", default="")
    ap.add_argument("--impact", default="MEDIO", choices=[i.value for i in ExpectedImpact])
    ap.add_argument("--clarity", default="MEDIA", choices=[c.value for c in CausalClarity])
    ap.add_argument("--cf-risk", default="MEDIO", choices=[r.value for r in HypothesisRisk])
    ap.add_argument("--risk-notes", default="")
    ap.add_argument("--design-dataset", default="")
    ap.add_argument("--design-period", default="")
    ap.add_argument("--oos-dataset", default="")
    ap.add_argument("--oos-period", default="")
    ap.add_argument("--oos-pending", action="store_true",
                    help="El OOS está declarado pero los datos aún no existen (OOS virgen)")
    ap.add_argument("--acceptance", action="append", default=[],
                    help="Criterio de aceptación (repetible)")
    ap.add_argument("--rejection", action="append", default=[],
                    help="Criterio de descarte (repetible)")
    ap.add_argument("--notes", default="")
    ap.add_argument("--slug", default=None, help="Nombre de archivo: HNNN_<slug>.md")
    ap.add_argument("--out-dir", default=str(ROOT / "research" / "hypotheses"))
    args = ap.parse_args()

    hypothesis = Hypothesis(
        id=args.id, title=args.title, type=HypothesisType(args.type),
        statement=args.statement, causal_mechanism=args.mechanism, origin=args.origin,
        status=HypothesisStatus.PROPOSED, created=date.today().isoformat(),
        expected_impact=ExpectedImpact(args.impact),
        causal_clarity=CausalClarity(args.clarity),
        curve_fitting_risk=HypothesisRisk(args.cf_risk),
        risk_notes=args.risk_notes,
        validation=HypothesisValidationPlan(
            design_dataset=args.design_dataset, design_period=args.design_period,
            oos_dataset=args.oos_dataset, oos_period=args.oos_period,
            oos_pending=args.oos_pending,
            acceptance_criteria=args.acceptance, rejection_criteria=args.rejection,
        ),
        notes=args.notes,
    )

    problems = validate_hypothesis(hypothesis)
    if problems:
        print("ERRORES (la ficha no se guardó):")
        for p in problems:
            print(f"  - {p}")
        return 2

    path = save_hypothesis(hypothesis, args.out_dir, slug=args.slug)
    print(f"Ficha creada: {path}")
    print(f"Estado: {hypothesis.status.value} | Prioridad calculada: "
          f"{compute_priority(hypothesis).value}")
    gaps = missing_for_design(hypothesis)
    if gaps:
        print("\nPendiente para pasar a DESIGNED:")
        for g in gaps:
            print(f"  - {g}")
    print("\nRecordatorio: registrar la fila en research/research_memory_index.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
