"""Tests del Hypothesis Engine: validación, prioridad, contaminación y ficha."""

import pytest

from nqbot.research import (
    CausalClarity,
    ExpectedImpact,
    Hypothesis,
    HypothesisPriority,
    HypothesisRisk,
    HypothesisStatus,
    HypothesisType,
    HypothesisValidationPlan,
    check_oos_contamination,
    compute_priority,
    hypothesis_to_markdown,
    missing_for_design,
    save_hypothesis,
    validate_hypothesis,
)


def make_designed(**overrides) -> Hypothesis:
    """Hipótesis completa, lista para DESIGNED."""
    base = dict(
        id="H099", title="Hipótesis de prueba", type=HypothesisType.EXIT_LOGIC,
        statement="Los trades que no avanzan 0.5R en 20 minutos terminan en stop.",
        causal_mechanism="Sin participación temprana no hay continuación; la espera "
                         "solo financia el camino al stop.",
        origin="test", status=HypothesisStatus.DESIGNED, created="2026-07-05",
        expected_impact=ExpectedImpact.ALTO, causal_clarity=CausalClarity.ALTA,
        curve_fitting_risk=HypothesisRisk.MEDIO,
        validation=HypothesisValidationPlan(
            design_dataset="data/processed/dataset_diseno.csv",
            design_period="2024-2025",
            oos_dataset="PENDIENTE: jul-2026 en adelante",
            oos_period="jul-2026+", oos_pending=True,
            acceptance_criteria=["expR mejora vs base", "el mecanismo replica"],
            rejection_criteria=["mejora solo por recorte de muestra"],
        ),
    )
    base.update(overrides)
    return Hypothesis(**base)


# ---------------------------------------------------------------- estados y enums
def test_all_states_and_types_exist():
    assert {s.value for s in HypothesisStatus} == {
        "PROPOSED", "DESIGNED", "READY_FOR_TEST", "TESTED",
        "PROMOTED", "OBSERVATION", "REJECTED", "ARCHIVED",
    }
    assert {t.value for t in HypothesisType} == {
        "ENTRY_LOGIC", "EXIT_LOGIC", "RISK_MANAGEMENT", "MARKET_REGIME",
        "FILTER", "POSITION_SIZING", "EXECUTION", "DATA_QUALITY",
    }


# ---------------------------------------------------------------- validación
def test_designed_hypothesis_is_valid():
    assert validate_hypothesis(make_designed()) == []


def test_proposed_allows_incomplete_plan_but_reports_gaps():
    proposed = Hypothesis(id="H098", title="Idea", type=HypothesisType.FILTER,
                          status=HypothesisStatus.PROPOSED)
    assert validate_hypothesis(proposed) == []           # PROPOSED: identidad basta
    gaps = missing_for_design(proposed)
    assert any("mecanismo" in g for g in gaps)           # pero el plan está incompleto
    assert any("out-of-sample" in g for g in gaps)
    assert any("aceptación" in g for g in gaps)


def test_designed_without_mechanism_is_invalid():
    broken = make_designed(causal_mechanism="")
    assert any("mecanismo" in p for p in validate_hypothesis(broken))


def test_bad_id_is_invalid():
    assert any("id inválido" in p for p in validate_hypothesis(make_designed(id="X2")))


def test_oos_equal_to_design_is_invalid():
    h = make_designed()
    h.validation.oos_dataset = h.validation.design_dataset
    h.validation.oos_pending = False
    assert any("mismo dataset" in p for p in validate_hypothesis(h))


# ---------------------------------------------------------------- contaminación
def test_contaminated_oos_is_rejected():
    h = make_designed()
    h.validation.oos_dataset = "data/processed/MNQ_2024_full_1m_ninjatrader_combined_clean.csv"
    h.validation.oos_pending = False
    problems = validate_hypothesis(h)
    assert any("contaminado" in p for p in problems)


def test_pending_oos_skips_contamination_check():
    # declarar 'pendiente' significa que los datos no existen todavía: virgen
    assert validate_hypothesis(make_designed()) == []


def test_check_oos_contamination_ledger():
    assert check_oos_contamination("x/MNQ_2025_01_2026_06_combined.csv") is not None
    assert check_oos_contamination("x/MNQ_2023_full_clean.csv") is None


# ---------------------------------------------------------------- prioridad
def test_priority_high_for_clear_high_impact_low_risk():
    h = make_designed(expected_impact=ExpectedImpact.ALTO,
                      causal_clarity=CausalClarity.ALTA,
                      curve_fitting_risk=HypothesisRisk.MEDIO)
    assert compute_priority(h) == HypothesisPriority.ALTA  # 3+3-1 = 5


def test_priority_low_for_risky_unclear_hypothesis():
    h = make_designed(expected_impact=ExpectedImpact.MEDIO,
                      causal_clarity=CausalClarity.MEDIA,
                      curve_fitting_risk=HypothesisRisk.ALTO)
    assert compute_priority(h) == HypothesisPriority.BAJA  # 2+2-2 = 2


# ---------------------------------------------------------------- ficha
def test_markdown_contains_key_sections():
    md = hypothesis_to_markdown(make_designed())
    for fragment in ("# H099", "## Hipótesis", "## Mecanismo causal",
                     "## Criterios de ACEPTACIÓN", "## Criterios de DESCARTE",
                     "Riesgos de curve fitting", "PENDIENTE"):
        assert fragment in md


def test_save_refuses_to_overwrite(tmp_path):
    h = make_designed()
    path = save_hypothesis(h, tmp_path, slug="prueba")
    assert path.exists() and path.name == "H099_prueba.md"
    with pytest.raises(FileExistsError):
        save_hypothesis(h, tmp_path, slug="prueba")
