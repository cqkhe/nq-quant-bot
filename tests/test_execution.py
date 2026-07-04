from datetime import datetime

import pytest

from nqbot.backtesting.models import Position
from nqbot.execution.simulator import ExecutionSimulator


def make_long(contracts=2, entry=21000.25, stop=20990.0, target=21010.0) -> Position:
    return Position(
        direction=1, contracts=contracts, entry_time=datetime(2026, 1, 5, 10, 0),
        entry_price=entry, stop_price=stop, target_price=target,
        initial_risk_dollars=(entry - stop) * 2.0 * contracts, reason="test",
    )


@pytest.fixture
def sim(mnq) -> ExecutionSimulator:
    return ExecutionSimulator(mnq, slippage_ticks=1)  # 1 tick = 0.25


def test_entry_fill_has_adverse_slippage(sim):
    assert sim.entry_fill_price(21000.0, +1) == 21000.25
    assert sim.entry_fill_price(21000.0, -1) == 20999.75


def test_spread_adds_half_spread_to_market_fills(mnq):
    # 1 tick de slippage + 2 ticks de spread -> costo adverso = (1 + 1) * 0.25 = 0.50
    sim = ExecutionSimulator(mnq, slippage_ticks=1, spread_ticks=2)
    assert sim.entry_fill_price(21000.0, +1) == 21000.50
    assert sim.entry_fill_price(21000.0, -1) == 20999.50
    assert sim.market_exit_price(21000.0, +1) == 20999.50   # vender cruza al bid
    assert sim.market_exit_price(21000.0, -1) == 21000.50   # cubrir cruza al ask


def test_stop_wins_when_stop_and_target_hit_same_bar(sim):
    pos = make_long()
    # La barra barre ambos niveles: supuesto conservador -> stop primero
    price, reason = sim.check_exit(pos, 21000.0, 21015.0, 20985.0, 21000.0, entered_this_bar=True)
    assert reason == "stop"
    assert price == 20990.0 - 0.25  # stop-market con slippage adverso


def test_gap_through_stop_fills_at_open_not_at_stop(sim):
    pos = make_long()
    price, reason = sim.check_exit(pos, 20980.0, 20990.0, 20975.0, 20985.0, entered_this_bar=False)
    assert reason == "stop_gap"
    assert price == 20980.0 - 0.25  # el open gapeado, no el precio del stop


def test_target_is_limit_fill_without_slippage(sim):
    pos = make_long()
    price, reason = sim.check_exit(pos, 21000.0, 21012.0, 20995.0, 21005.0, entered_this_bar=False)
    assert reason == "target"
    assert price == 21010.0  # limit exacta


def test_short_stop_slippage_is_adverse(sim):
    pos = Position(
        direction=-1, contracts=1, entry_time=datetime(2026, 1, 5, 10, 0),
        entry_price=20999.75, stop_price=21010.0, target_price=20980.0,
        initial_risk_dollars=20.5, reason="test",
    )
    price, reason = sim.check_exit(pos, 21000.0, 21012.0, 20998.0, 21008.0, entered_this_bar=False)
    assert reason == "stop"
    assert price == 21010.25  # para un short, el slippage empeora hacia arriba


def test_build_trade_pnl_commission_and_r(sim):
    pos = make_long(contracts=2)  # riesgo inicial: 10.25 pts * $2 * 2 = $41
    trade = sim.build_trade(pos, datetime(2026, 1, 5, 10, 30), 20989.75, "stop", bars_held=7)
    assert trade.pnl_gross == pytest.approx(-42.0)   # -10.5 pts * $2 * 2
    assert trade.commission == pytest.approx(4.0)    # $1 x 2 lados x 2 contratos
    assert trade.pnl_net == pytest.approx(-46.0)
    assert trade.r_multiple == pytest.approx(-46.0 / 41.0, abs=1e-3)
    assert trade.bars_held == 7
