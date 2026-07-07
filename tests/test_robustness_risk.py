from nqbot.robustness import estimate_risk


def test_estimate_risk_is_reproducible_and_reports_drawdown_metrics():
    trades = [200.0, -100.0, 150.0, -80.0, 120.0, -60.0]

    risk_a, drawdown_a = estimate_risk(
        trades,
        initial_capital=5_000.0,
        iterations=1_000,
        seed=11,
        ruin_threshold_pct=50.0,
        loss_threshold_pct=20.0,
    )
    risk_b, drawdown_b = estimate_risk(
        trades,
        initial_capital=5_000.0,
        iterations=1_000,
        seed=11,
        ruin_threshold_pct=50.0,
        loss_threshold_pct=20.0,
    )

    assert risk_a == risk_b
    assert drawdown_a == drawdown_b
    assert 0.0 <= risk_a.risk_of_ruin <= 1.0
    assert 0.0 <= risk_a.probability_loss_threshold <= 1.0
    assert risk_a.suggested_min_capital > 0.0
    assert drawdown_a.drawdown_pct_p95 >= drawdown_a.expected_max_drawdown_pct
    assert drawdown_a.worst_losing_streak_p95 >= 1
