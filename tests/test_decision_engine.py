"""Tests del Decision Engine: árbol de decisión y adaptadores de entrada."""

from pathlib import Path

import pandas as pd
import pytest

from nqbot.research.decision_engine import (
    evaluate,
    metrics_from_comparison_csv,
    metrics_from_report_folder,
)
from nqbot.research.models import DecisionStatus, ExperimentMetrics


def make_metrics(**overrides) -> ExperimentMetrics:
    """Métricas que cumplen TODOS los criterios de paper por defecto."""
    base = dict(
        source="test", strategy="test_strategy",
        n_trades=150, pnl_net=5_000.0, profit_factor=1.40, expectancy_r=0.20,
        winrate_pct=45.0, max_drawdown_usd=1_500.0, max_drawdown_pct=6.0,
        max_losing_streak=6, n_months=12, pct_positive_months=66.0,
        pnl_without_top5=2_500.0, is_out_of_sample=True,
        overlaps_design_period=False,
    )
    base.update(overrides)
    return ExperimentMetrics(**base)


# ---------------------------------------------------------------- árbol de decisión
def test_paper_candidate_when_all_criteria_met():
    decision = evaluate(make_metrics())
    assert decision.status == DecisionStatus.PAPER_CANDIDATE
    assert not decision.failed


def test_blocked_for_paper_when_data_is_contaminated():
    decision = evaluate(make_metrics(overlaps_design_period=True))
    assert decision.status == DecisionStatus.BLOCKED_FOR_PAPER


def test_blocked_for_paper_when_not_out_of_sample():
    decision = evaluate(make_metrics(is_out_of_sample=False))
    assert decision.status == DecisionStatus.BLOCKED_FOR_PAPER


def test_blocked_for_paper_when_depends_on_few_trades():
    # sin los 5 mejores trades el PnL se hace negativo -> dependencia
    decision = evaluate(make_metrics(pnl_without_top5=-200.0))
    assert decision.status == DecisionStatus.BLOCKED_FOR_PAPER


def test_undeclared_oos_cannot_be_paper_candidate():
    decision = evaluate(make_metrics(is_out_of_sample=None, overlaps_design_period=None))
    assert decision.status == DecisionStatus.BLOCKED_FOR_PAPER
    assert any("no evaluable" in r.lower() for r in decision.reasons)


def test_rejected_when_no_edge_with_enough_sample():
    # el caso real de la familia RR2 en 2024: expR negativa, PF < 1
    decision = evaluate(make_metrics(
        n_trades=258, pnl_net=-2_948.06, profit_factor=0.818, expectancy_r=-0.12,
        max_drawdown_pct=14.2, pnl_without_top5=-4_000.0,
    ))
    assert decision.status == DecisionStatus.REJECTED


def test_observation_when_sample_too_small():
    decision = evaluate(make_metrics(n_trades=12, profit_factor=0.5, expectancy_r=-0.4))
    assert decision.status == DecisionStatus.OBSERVATION


def test_approved_for_research_when_positive_but_below_paper_level():
    # edge chico y muestra corta para paper, pero señales positivas
    decision = evaluate(make_metrics(n_trades=60, profit_factor=1.20, expectancy_r=0.10))
    assert decision.status == DecisionStatus.APPROVED_FOR_RESEARCH


def test_paper_candidate_requires_positive_oos_pnl():
    decision = evaluate(make_metrics(pnl_net=-100.0, profit_factor=1.16, expectancy_r=0.01))
    assert decision.status != DecisionStatus.PAPER_CANDIDATE


def test_robustness_fields_can_block_paper_candidate():
    decision = evaluate(make_metrics(
        mc_probability_negative=0.35,
        mc_probability_extreme_drawdown=0.05,
        bootstrap_probability_expectancy_le_zero=0.10,
        depends_on_few_winners=False,
        cost_stress_survives=True,
    ))
    assert decision.status == DecisionStatus.BLOCKED_FOR_PAPER
    assert any("robustez_mc_probabilidad_negativa" == c.name for c in decision.failed)


# ---------------------------------------------------------------- adaptadores
def test_metrics_from_comparison_csv(tmp_path):
    csv = tmp_path / "validation.csv"
    pd.DataFrame([
        {"dataset": "X", "estrategia": "base", "trades": 332, "pnl_net": -4716.30,
         "profit_factor": 0.765, "winrate_pct": 31.33, "expectancy_r": -0.149,
         "max_drawdown_usd": 5359.78, "max_drawdown_pct": 21.4, "racha_perdedora_max": 10},
        {"dataset": "X", "estrategia": "candidata", "trades": 258, "pnl_net": -2948.06,
         "profit_factor": 0.818, "winrate_pct": 31.78, "expectancy_r": -0.120,
         "max_drawdown_usd": 3553.20, "max_drawdown_pct": 14.2, "racha_perdedora_max": 12},
        {"dataset": "X", "estrategia": "delta", "trades": -74, "pnl_net": 1768.24,
         "profit_factor": 0.053, "winrate_pct": 0.45, "expectancy_r": 0.029,
         "max_drawdown_usd": -1806.58, "max_drawdown_pct": -7.2, "racha_perdedora_max": 2},
    ]).to_csv(csv, index=False)

    metrics = metrics_from_comparison_csv(csv, strategy="candidata",
                                          is_out_of_sample=True,
                                          overlaps_design_period=False)
    assert metrics.n_trades == 258
    assert metrics.expectancy_r == pytest.approx(-0.120)
    assert metrics.pnl_without_top5 is None  # el CSV no trae trades: no evaluable

    decision = evaluate(metrics)
    assert decision.status == DecisionStatus.REJECTED  # sin edge en OOS

    with pytest.raises(ValueError):
        metrics_from_comparison_csv(csv)  # varias estrategias sin --strategy


def test_metrics_from_report_folder(tmp_path):
    folder = tmp_path / "report"
    folder.mkdir()
    entries = pd.date_range("2026-01-05 10:00", periods=6, freq="1D")
    pd.DataFrame({
        "entry_time": entries,
        "exit_time": entries + pd.Timedelta(minutes=30),
        "pnl_net": [200.0, -100.0, 200.0, -100.0, 200.0, -100.0],
        "r_multiple": [2.0, -1.0, 2.0, -1.0, 2.0, -1.0],
    }).to_csv(folder / "trades.csv", index=False)
    equity = pd.Series([10_000, 10_200, 10_100, 10_300, 10_200, 10_400, 10_300],
                       index=pd.date_range("2026-01-05", periods=7, freq="1D"),
                       name="equity")
    equity.index.name = "datetime"
    equity.to_csv(folder / "equity_curve.csv")

    metrics = metrics_from_report_folder(folder)
    assert metrics.n_trades == 6
    assert metrics.pnl_net == pytest.approx(300.0)
    assert metrics.profit_factor == pytest.approx(2.0)
    assert metrics.expectancy_r == pytest.approx(0.5)
    assert metrics.max_losing_streak == 1
    assert metrics.pct_positive_months == pytest.approx(100.0)  # un solo mes, positivo
    # PnL sin top-5 ganadores: 300 - (200*3) = -300 -> dependencia detectada
    assert metrics.pnl_without_top5 == pytest.approx(-300.0)
    assert metrics.max_drawdown_usd == pytest.approx(100.0)
