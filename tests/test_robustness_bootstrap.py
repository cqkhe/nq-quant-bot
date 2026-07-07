import pandas as pd
import pytest

from nqbot.robustness import run_bootstrap


def test_bootstrap_calculates_confidence_intervals_and_seed_reproducibility():
    trades = pd.DataFrame({
        "pnl_net": [200.0, -50.0, 180.0, -40.0, 160.0, -30.0],
        "r_multiple": [2.0, -0.5, 1.8, -0.4, 1.6, -0.3],
    })

    first = run_bootstrap(trades, iterations=1_000, seed=99)
    second = run_bootstrap(trades, iterations=1_000, seed=99)

    assert first.expectancy_r_mean == pytest.approx(trades["r_multiple"].mean())
    assert first.expectancy_r_ci == second.expectancy_r_ci
    assert first.profit_factor_ci == second.profit_factor_ci
    assert first.winrate_pct_ci == second.winrate_pct_ci
    assert first.avg_pnl_per_trade_ci[0] <= first.avg_pnl_per_trade_mean
    assert first.avg_pnl_per_trade_ci[1] >= first.avg_pnl_per_trade_mean
    assert first.probability_expectancy_le_zero < 0.10


def test_bootstrap_without_r_column_uses_pnl_for_expectancy_sign_only():
    trades = pd.DataFrame({"pnl_net": [100.0, -20.0, 80.0, -10.0]})

    result = run_bootstrap(trades, iterations=300, seed=5)

    assert result.expectancy_r_mean is None
    assert result.expectancy_r_ci is None
    assert result.expectancy_sign_source == "pnl_net"
    assert result.probability_expectancy_le_zero < 0.50
