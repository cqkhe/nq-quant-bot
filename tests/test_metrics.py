from datetime import datetime

import pandas as pd
import pytest

from nqbot.backtesting.metrics import compute_metrics
from nqbot.backtesting.models import BacktestResult


def _result(trades, equity_values) -> BacktestResult:
    idx = pd.date_range("2026-01-05 09:30", periods=len(equity_values), freq="1min")
    return BacktestResult(
        symbol="MNQ", strategy_name="test", initial_capital=10_000.0,
        trades=trades, equity_curve=pd.Series(equity_values, index=idx),
        skipped_signals={}, start=datetime(2026, 1, 5, 9, 30), end=datetime(2026, 1, 5, 10, 0),
    )


def test_core_trade_metrics(make_trade):
    trades = [
        make_trade(+100.0, 2.0),
        make_trade(-50.0, -1.0),
        make_trade(+100.0, 2.0),
        make_trade(-50.0, -1.0),
    ]
    m = compute_metrics(_result(trades, [10_000, 10_100, 10_050, 10_150, 10_100]))

    assert m["n_trades"] == 4
    assert m["n_long"] == 4 and m["n_short"] == 0
    # make_trade: entry 100, stop 99, target 102 -> RR planificado = 2.0
    assert m["avg_planned_rr"] == pytest.approx(2.0)
    assert m["winrate_pct"] == pytest.approx(50.0)
    assert m["profit_factor"] == pytest.approx(2.0)      # 200 / 100
    assert m["expectancy_usd"] == pytest.approx(25.0)
    assert m["expectancy_r"] == pytest.approx(0.5)
    assert m["best_trade"] == 100.0
    assert m["worst_trade"] == -50.0
    assert m["max_consecutive_wins"] == 1
    assert m["max_consecutive_losses"] == 1


def test_drawdown_from_equity_curve(make_trade):
    m = compute_metrics(_result([], [10_000, 10_100, 10_050, 10_150, 10_100]))
    assert m["max_drawdown"] == pytest.approx(50.0)
    assert m["max_drawdown_pct"] == pytest.approx(50.0 / 10_100 * 100.0)


def test_sharpe_requires_two_sessions(make_trade):
    # Una sola sesión -> no hay retornos diarios suficientes
    m = compute_metrics(_result([], [10_000, 10_050]))
    assert m["sharpe"] is None
    assert m["n_sessions"] == 1
