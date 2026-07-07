"""Modelos del Decision Engine (Quant Brain, Fase 2).

El motor de decisión evalúa métricas ESTRUCTURADAS: no sabe de archivos ni
de estrategias, solo de números y de los criterios pre-registrados. Los
adaptadores de entrada viven en decision_engine.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DecisionStatus(str, Enum):
    """Estados posibles de un experimento evaluado."""

    PAPER_CANDIDATE = "PAPER_CANDIDATE"            # cumple TODO: puede proponerse a paper
    APPROVED_FOR_RESEARCH = "APPROVED_FOR_RESEARCH"  # señales positivas: seguir el protocolo
    OBSERVATION = "OBSERVATION"                    # evidencia mixta o muestra insuficiente
    REJECTED = "REJECTED"                          # sin edge: descartar y registrar
    BLOCKED_FOR_PAPER = "BLOCKED_FOR_PAPER"        # números de nivel paper, sin validación limpia


@dataclass(frozen=True)
class PaperCriteria:
    """Umbrales PRE-REGISTRADOS para la candidatura a paper trading.

    Fuente: docs/quant_brain_architecture.md §6 y
    research/decisions/decision_engine_rules.md. Cambiarlos requiere una
    decisión registrada ANTES de evaluar al próximo candidato — nunca
    después de ver un resultado.
    """

    min_trades: int = 100
    min_profit_factor: float = 1.15
    min_expectancy_r: float = 0.0        # exclusivo: la expectancia debe ser > 0
    max_drawdown_pct: float = 10.0       # sobre el capital, mark-to-market
    min_sample_for_verdict: int = 30     # por debajo: OBSERVATION (muestra insuficiente)
    max_mc_probability_negative: float = 0.20
    max_mc_probability_extreme_drawdown: float = 0.20
    max_bootstrap_probability_expectancy_le_zero: float = 0.25


@dataclass
class ExperimentMetrics:
    """Métricas de un experimento, con metadata de procedencia de los datos.

    Los campos None significan 'no disponible con esta fuente de datos':
    el criterio asociado queda como NO EVALUABLE (y bloquea la candidatura
    a paper, porque un criterio no verificado no está cumplido).
    """

    source: str
    strategy: str
    n_trades: int
    pnl_net: float
    profit_factor: float | None
    expectancy_r: float | None
    winrate_pct: float | None = None
    max_drawdown_usd: float | None = None
    max_drawdown_pct: float | None = None
    max_losing_streak: int | None = None
    n_months: int | None = None
    pct_positive_months: float | None = None
    pnl_without_top5: float | None = None          # dependencia de pocos trades
    is_out_of_sample: bool | None = None           # declarado por el investigador
    overlaps_design_period: bool | None = None     # contaminación con el diseño
    mc_probability_negative: float | None = None
    mc_probability_extreme_drawdown: float | None = None
    bootstrap_probability_expectancy_le_zero: float | None = None
    depends_on_few_winners: bool | None = None
    cost_stress_survives: bool | None = None


@dataclass(frozen=True)
class CriterionResult:
    name: str
    passed: bool | None    # None = no evaluable con los datos disponibles
    detail: str


@dataclass
class Decision:
    status: DecisionStatus
    strategy: str
    source: str
    criteria: list[CriterionResult] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    recommendation: str = ""

    @property
    def passed(self) -> list[CriterionResult]:
        return [c for c in self.criteria if c.passed is True]

    @property
    def failed(self) -> list[CriterionResult]:
        return [c for c in self.criteria if c.passed is False]

    @property
    def not_evaluable(self) -> list[CriterionResult]:
        return [c for c in self.criteria if c.passed is None]

    def to_text(self) -> str:
        lines = [
            "=" * 70,
            "  DECISION ENGINE — evaluación de experimento",
            f"  Estrategia: {self.strategy}",
            f"  Fuente:     {self.source}",
            "=" * 70,
            f"  ESTADO: {self.status.value}",
            "-" * 70,
            "  Criterios:",
        ]
        for c in self.criteria:
            mark = {True: "[CUMPLE]     ", False: "[FALLA]      ", None: "[NO EVALUABLE]"}[c.passed]
            lines.append(f"    {mark} {c.name}: {c.detail}")
        lines += ["-" * 70, "  Motivo:"]
        lines += [f"    - {r}" for r in self.reasons]
        lines += ["-" * 70, f"  Recomendación: {self.recommendation}", "=" * 70]
        return "\n".join(lines)

    def to_markdown(self) -> str:
        lines = [
            f"# Evaluación — {self.strategy}",
            "",
            f"- **Fuente:** `{self.source}`",
            f"- **Estado:** **{self.status.value}**",
            "",
            "## Criterios",
            "",
            "| Criterio | Resultado | Detalle |",
            "|---|---|---|",
        ]
        for c in self.criteria:
            mark = {True: "CUMPLE", False: "FALLA", None: "no evaluable"}[c.passed]
            lines.append(f"| {c.name} | {mark} | {c.detail} |")
        lines += ["", "## Motivo", ""]
        lines += [f"- {r}" for r in self.reasons]
        lines += ["", "## Recomendación", "", self.recommendation, ""]
        return "\n".join(lines)


# ======================================================================
# Hypothesis Engine (Fase 4)
# ======================================================================

class HypothesisStatus(str, Enum):
    PROPOSED = "PROPOSED"              # idea registrada, plan incompleto
    DESIGNED = "DESIGNED"              # plan completo, criterios congelados
    READY_FOR_TEST = "READY_FOR_TEST"  # variante implementada, sin correr
    TESTED = "TESTED"                  # resultados documentados
    PROMOTED = "PROMOTED"              # decisión aprobatoria registrada
    OBSERVATION = "OBSERVATION"        # evidencia mixta: esperar datos nuevos
    REJECTED = "REJECTED"              # descartada con evidencia
    ARCHIVED = "ARCHIVED"              # fuera de alcance / superada


class HypothesisType(str, Enum):
    ENTRY_LOGIC = "ENTRY_LOGIC"
    EXIT_LOGIC = "EXIT_LOGIC"
    RISK_MANAGEMENT = "RISK_MANAGEMENT"
    MARKET_REGIME = "MARKET_REGIME"
    FILTER = "FILTER"
    POSITION_SIZING = "POSITION_SIZING"
    EXECUTION = "EXECUTION"
    DATA_QUALITY = "DATA_QUALITY"


class HypothesisPriority(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class ExpectedImpact(str, Enum):
    ALTO = "ALTO"
    MEDIO = "MEDIO"
    BAJO = "BAJO"


class CausalClarity(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class HypothesisRisk(str, Enum):
    """Riesgo de curve fitting de la hipótesis."""

    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"


@dataclass
class HypothesisValidationPlan:
    """Plan de validación: se congela al pasar a DESIGNED.

    `oos_pending=True` significa que el OOS está DECLARADO pero los datos
    aún no existen/no se adquirieron (p. ej. "jul-2026 en adelante"): es el
    único caso legítimo de OOS sin archivo, porque garantiza que nadie lo
    miró todavía.
    """

    design_dataset: str = ""
    design_period: str = ""
    oos_dataset: str = ""
    oos_period: str = ""
    oos_pending: bool = False
    acceptance_criteria: list[str] = field(default_factory=list)
    rejection_criteria: list[str] = field(default_factory=list)
    min_sample_trades: int = 30


@dataclass
class Hypothesis:
    """Ficha estructurada de una hipótesis de investigación."""

    id: str
    title: str
    type: HypothesisType
    statement: str = ""
    causal_mechanism: str = ""
    origin: str = ""
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    created: str = ""                      # YYYY-MM-DD
    expected_impact: ExpectedImpact = ExpectedImpact.MEDIO
    causal_clarity: CausalClarity = CausalClarity.MEDIA
    curve_fitting_risk: HypothesisRisk = HypothesisRisk.MEDIO
    risk_notes: str = ""
    validation: HypothesisValidationPlan = field(default_factory=HypothesisValidationPlan)
    notes: str = ""
