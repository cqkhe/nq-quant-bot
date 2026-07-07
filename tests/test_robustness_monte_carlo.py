import pytest

from nqbot.robustness import MonteCarloConfig, run_monte_carlo


def test_monte_carlo_is_reproducible_with_seed():
    trades = [120.0, -80.0, 90.0, -60.0, 75.0, -50.0]
    cfg = MonteCarloConfig(
        iterations=1_000,
        initial_capital=5_000.0,
        seed=123,
        drawdown_threshold_pct=5.0,
        sample_with_replacement=True,
    )

    first = run_monte_carlo(trades, cfg)
    second = run_monte_carlo(trades, cfg)

    assert first.final_pnl_percentiles == second.final_pnl_percentiles
    assert first.max_drawdown_pct_percentiles == second.max_drawdown_pct_percentiles
    assert first.losing_streak_percentiles == second.losing_streak_percentiles
    assert 0.0 <= first.probability_negative <= 1.0
    assert 0.0 <= first.probability_drawdown_exceeds_threshold <= 1.0
    assert first.final_pnl_percentiles["p05"] <= first.final_pnl_percentiles["p50"]
    assert first.final_pnl_percentiles["p50"] <= first.final_pnl_percentiles["p95"]


def test_shuffle_without_replacement_keeps_final_pnl_fixed():
    trades = [100.0, -50.0, 80.0, -40.0]
    cfg = MonteCarloConfig(
        iterations=200,
        initial_capital=1_000.0,
        seed=7,
        sample_with_replacement=False,
    )

    result = run_monte_carlo(trades, cfg)

    assert result.final_pnl_percentiles["p05"] == pytest.approx(sum(trades))
    assert result.final_pnl_percentiles["p50"] == pytest.approx(sum(trades))
    assert result.final_pnl_percentiles["p95"] == pytest.approx(sum(trades))
    assert result.max_drawdown_pct_percentiles["p95"] >= result.max_drawdown_pct_percentiles["p50"]
