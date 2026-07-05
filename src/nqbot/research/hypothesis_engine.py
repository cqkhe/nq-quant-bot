"""Hypothesis Engine — registro estructurado de hipótesis (Quant Brain, Fase 4).

Función: que ninguna idea toque código de estrategia sin pasar antes por una
ficha con mecanismo causal, datasets declarados, criterios pre-registrados y
prioridad calculada. La ficha se escribe ANTES de mirar resultados.

Piezas:
  * validate_hypothesis(h)   -> problemas duros para su estado actual
  * missing_for_design(h)    -> qué falta para congelar el plan (DESIGNED)
  * compute_priority(h)      -> ALTA/MEDIA/BAJA (impacto + claridad - riesgo)
  * check_oos_contamination  -> el OOS no puede ser un dataset ya mirado
  * hypothesis_to_markdown / save_hypothesis -> ficha en research/hypotheses/

Registro de contaminación: TODOS los datasets actuales del proyecto fueron
mirados durante el ciclo H001 (diseño, diagnósticos o validación OOS ya
consumida). Una hipótesis nueva debe declarar su OOS como PENDIENTE (datos
futuros jul-2026+ o histórico 2023 sin adquirir): es el único OOS que
garantiza que nadie lo vio.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .models import (
    Hypothesis,
    HypothesisPriority,
    HypothesisRisk,
    HypothesisStatus,
)

# Datasets ya MIRADOS (diseño, diagnóstico o validación consumida) y por qué.
# Usarlos como OOS de una hipótesis nueva es contaminación.
CONTAMINATED_DATASETS: dict[str, str] = {
    "MNQ_2025_12_2026_06": "período de diseño original de H001",
    "MNQ_2025_01_2025_11": "OOS de no_midday + fuente de los diagnósticos de H001",
    "MNQ_2025_01_2026_06": "dataset combinado usado en diagnósticos/validaciones de H001",
    "MNQ_2024_full": "OOS final de H001 (resultados ya vistos)",
    "MNQ_ninjatrader": "tramos parciales del ciclo H001",
    "MNQ_proveedor_bueno": "sample sintético/de prueba del pipeline",
}

_ID_PATTERN = re.compile(r"^H\d{3}$")

_IMPACT_SCORE = {"ALTO": 3, "MEDIO": 2, "BAJO": 1}
_CLARITY_SCORE = {"ALTA": 3, "MEDIA": 2, "BAJA": 1}
_RISK_PENALTY = {"BAJO": 0, "MEDIO": 1, "ALTO": 2}


# ------------------------------------------------------------------ prioridad
def compute_priority(h: Hypothesis) -> HypothesisPriority:
    """Prioridad = impacto esperado + claridad causal - riesgo de curve fitting.

    Escala determinista y documentada (decision_engine_rules / doc del motor):
    score >= 5 -> ALTA | 3-4 -> MEDIA | <= 2 -> BAJA.
    Codifica las lecciones del ciclo H001: una idea de alto impacto con
    mecanismo claro y bajo riesgo de ajuste vale más que cualquier métrica
    prometedora sin mecanismo.
    """
    score = (
        _IMPACT_SCORE[h.expected_impact.value]
        + _CLARITY_SCORE[h.causal_clarity.value]
        - _RISK_PENALTY[h.curve_fitting_risk.value]
    )
    if score >= 5:
        return HypothesisPriority.ALTA
    if score >= 3:
        return HypothesisPriority.MEDIA
    return HypothesisPriority.BAJA


# ------------------------------------------------------------------ validación
def check_oos_contamination(oos_dataset: str,
                            contaminated: dict[str, str] | None = None) -> str | None:
    """Devuelve el motivo de contaminación si el OOS declarado ya fue mirado."""
    ledger = CONTAMINATED_DATASETS if contaminated is None else contaminated
    for key, reason in ledger.items():
        if key.lower() in oos_dataset.lower():
            return f"{key}: {reason}"
    return None


def validate_hypothesis(h: Hypothesis,
                        contaminated: dict[str, str] | None = None) -> list[str]:
    """Problemas DUROS para el estado actual de la hipótesis.

    PROPOSED exige identidad válida (id, título, tipo) y coherencia de lo ya
    declarado. Los estados DESIGNED en adelante exigen además el plan
    completo (ver missing_for_design).
    """
    problems: list[str] = []
    if not _ID_PATTERN.match(h.id):
        problems.append(f"id inválido: {h.id!r} (formato HNNN, p.ej. H002)")
    if not h.title.strip():
        problems.append("falta el título")

    plan = h.validation
    # coherencia de lo declarado (aplica en cualquier estado)
    if plan.oos_dataset and plan.design_dataset and plan.oos_dataset == plan.design_dataset:
        problems.append("el OOS no puede ser el mismo dataset de diseño")
    if plan.oos_dataset and not plan.oos_pending:
        reason = check_oos_contamination(plan.oos_dataset, contaminated)
        if reason:
            problems.append(f"OOS contaminado ({reason}): declarar un OOS virgen "
                            "o marcarlo como pendiente de datos futuros")

    if h.status not in (HypothesisStatus.PROPOSED, HypothesisStatus.ARCHIVED):
        problems.extend(missing_for_design(h))
    return problems


def missing_for_design(h: Hypothesis) -> list[str]:
    """Qué le falta a la ficha para poder congelarse como DESIGNED."""
    plan = h.validation
    missing: list[str] = []
    if len(h.statement.strip()) < 20:
        missing.append("hipótesis medible y falsable (statement)")
    if len(h.causal_mechanism.strip()) < 30:
        missing.append("mecanismo causal explicado ANTES de medir")
    if not plan.design_dataset.strip():
        missing.append("dataset de diseño declarado")
    if not plan.oos_dataset.strip():
        missing.append("dataset out-of-sample declarado (o marcado pendiente)")
    if not plan.acceptance_criteria:
        missing.append("criterios de aceptación pre-registrados")
    if not plan.rejection_criteria:
        missing.append("criterios de descarte pre-registrados")
    return missing


# ------------------------------------------------------------------ ficha
def hypothesis_to_markdown(h: Hypothesis) -> str:
    priority = compute_priority(h)
    plan = h.validation
    frozen = h.status != HypothesisStatus.PROPOSED
    criteria_note = "" if frozen else " *(borrador: se congelan al pasar a DESIGNED)*"

    def block(items: list[str]) -> list[str]:
        return [f"{i}. {item}" for i, item in enumerate(items, 1)] or ["*(pendiente)*"]

    oos_shown = plan.oos_dataset or "*(pendiente de declarar)*"
    if plan.oos_pending:
        oos_shown += " — **PENDIENTE: datos aún no disponibles/adquiridos (garantía de OOS virgen)**"

    lines = [
        f"# {h.id} — {h.title}",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| **ID** | {h.id} |",
        f"| **Fecha de registro** | {h.created or date.today().isoformat()} |",
        f"| **Estado** | {h.status.value} |",
        f"| **Tipo** | {h.type.value} |",
        f"| **Prioridad (calculada)** | {priority.value} — impacto {h.expected_impact.value}, "
        f"claridad {h.causal_clarity.value}, riesgo CF {h.curve_fitting_risk.value} |",
        f"| **Origen** | {h.origin or '*(completar)*'} |",
        "",
        "## Hipótesis", "", h.statement or "*(completar antes de DESIGNED)*", "",
        "## Mecanismo causal esperado", "",
        h.causal_mechanism or "*(completar antes de DESIGNED — sin mecanismo no se mide)*", "",
        "## Datasets", "",
        "| Rol | Dataset | Período |",
        "|---|---|---|",
        f"| Diseño (in-sample) | {plan.design_dataset or '*(pendiente)*'} | {plan.design_period or '-'} |",
        f"| Out-of-sample (RESERVADO) | {oos_shown} | {plan.oos_period or '-'} |",
        "",
        f"Muestra mínima para veredicto: **{plan.min_sample_trades} trades**.",
        "",
        f"## Criterios de ACEPTACIÓN{criteria_note}", "", *block(plan.acceptance_criteria), "",
        f"## Criterios de DESCARTE{criteria_note}", "", *block(plan.rejection_criteria), "",
        "## Riesgos de curve fitting", "",
        f"**Nivel: {h.curve_fitting_risk.value}.** {h.risk_notes or ''}".rstrip(), "",
    ]
    if h.notes:
        lines += ["## Notas", "", h.notes, ""]
    lines += [
        "## Resultado final", "", "*(pendiente)*", "",
        "## Decisión", "", "*(pendiente — se registra como DXXX en research/decisions/)*", "",
    ]
    return "\n".join(lines)


def save_hypothesis(
    h: Hypothesis,
    directory: str | Path,
    slug: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Escribe la ficha en research/hypotheses/. No pisa fichas existentes."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    safe_slug = slug or re.sub(r"[^a-z0-9]+", "_", h.title.lower()).strip("_")[:48]
    path = directory / f"{h.id}_{safe_slug}.md"
    if path.exists() and not overwrite:
        raise FileExistsError(f"Ya existe {path.name}: las fichas no se pisan "
                              "(usar overwrite=True solo si es un borrador propio)")
    path.write_text(hypothesis_to_markdown(h), encoding="utf-8")
    return path
