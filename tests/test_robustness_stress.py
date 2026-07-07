import pandas as pd
import pytest

from nqbot.robustness import apply_stress, run_stress_suite


def test_remove_top_winners_detects_dependency():
    trades = pd.DataFrame({
        "pnl_net": [1_000.0, 200.0, 200.0, -100.0, -100.0, -100.0],
        "r_multiple": [10.0, 2.0, 2.0, -1.0, -1.0, -1.0],
    })

    result = apply_stress(
        trades,
        initial_capital=10_000.0,
        scenario="remove_top_5_winners",
        remove_top_winners=5,
    )

    assert result.pnl_net == pytest.approx(-300.0)
    assert result.edge_survives is False
    assert result.expectancy_r is not None
    assert result.expectancy_r < 0.0


def test_cost_stress_can_erase_small_edge():
    trades = [120.0, 80.0, -90.0, -70.0]

    result = apply_stress(
        trades,
        initial_capital=5_000.0,
        scenario="costs_plus_reasonable",
        commission_increase_per_trade=5.0,
        slippage_increase_per_trade=10.0,
    )

    assert result.pnl_net == pytest.approx(-20.0)
    assert result.edge_survives is False


def test_standard_stress_suite_contains_expected_scenarios():
    trades = [300.0, -100.0, 250.0, -80.0, 200.0, -70.0]

    results = run_stress_suite(trades, initial_capital=10_000.0)
    names = {result.scenario for result in results}

    assert "baseline" in names
    assert "commission_plus_reasonable" in names
    assert "slippage_plus_reasonable" in names
    assert "costs_plus_reasonable" in names
    assert "remove_top_5_winners" in names
    assert "remove_top_10_winners" in names
    assert "edge_minus_10pct" in names
