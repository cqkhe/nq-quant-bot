"""Tests de daytrading_vwap_liquidity_rr2 y de sus garantías intradía.

La sesión sintética se construye a mano: tendencia alcista limpia, pullback
de 3 barras a la zona de valor (EMA25) y barra de rechazo alcista con pico
de volumen. Como el volumen relativo solo supera el umbral en esa barra, la
ubicación de la señal es determinista.
"""

from datetime import time

import pandas as pd
import pytest

from nqbot.backtesting.engine import BacktestEngine
from nqbot.backtesting.models import LONG, Signal
from nqbot.config.settings import (
    AccountConfig,
    Config,
    ContractSpec,
    ExecutionConfig,
    RiskConfig,
    SessionConfig,
)
from nqbot.strategies.base import Strategy
from nqbot.strategies.registry import available_strategies, create_strategy

STRATEGY_NAME = "daytrading_vwap_liquidity_rr2"
MNQ = ContractSpec(symbol="MNQ", tick_size=0.25, point_value=2.0, commission_per_side=0.79)


def make_trending_session(day: str, base: float = 21000.0, dip_at: int = 250) -> pd.DataFrame:
    """Sesión RTH 1m: rampa alcista + pullback en dip_at + rechazo con volumen."""
    n = 390
    idx = pd.date_range(f"{day} 09:30", periods=n, freq="1min")
    rows = []
    for i in range(n):
        ramp = base + 0.3 * i
        if dip_at <= i < dip_at + 3:          # pullback: 3 barras bajistas a la EMA25
            close, open_ = ramp - 8.0, ramp - 8.0 + 0.25
            high, low = open_ + 0.25, ramp - 10.0
            vol = 1000.0
        elif i == dip_at + 3:                  # rechazo alcista con pico de volumen
            open_ = (base + 0.3 * (i - 1)) - 8.0
            close = open_ + 8.0
            high, low = close + 0.5, open_ - 2.0
            vol = 5000.0
        else:                                  # rampa limpia
            close, open_ = ramp, ramp - 0.25
            high, low = ramp + 0.25, ramp - 0.5
            vol = 1000.0
        rows.append((open_, high, low, close, vol))
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"],
                      index=pd.DatetimeIndex(idx, name="datetime"))
    return df


def default_config(**risk_overrides) -> Config:
    risk = dict(
        risk_per_trade_pct=0.5, max_daily_loss_pct=2.0, max_trades_per_day=5,
        max_consecutive_losses=3, max_contracts=10, max_stop_points=100.0,
    )
    risk.update(risk_overrides)
    return Config(
        account=AccountConfig(initial_capital=25_000.0),
        risk=RiskConfig(**risk),
        execution=ExecutionConfig(slippage_ticks=1, spread_ticks=1),
        session=SessionConfig(),  # RTH, entradas 09:45-15:15, flatten 15:50
        contracts={"MNQ": MNQ},
    )


def run_backtest(df: pd.DataFrame, config: Config | None = None):
    config = config or default_config()
    strategy = create_strategy(STRATEGY_NAME, None, MNQ)
    return BacktestEngine(config, MNQ, strategy).run(df)


# ---------------------------------------------------------------- registro/CLI
def test_strategy_available_from_cli_registry():
    assert STRATEGY_NAME in available_strategies()
    strategy = create_strategy(STRATEGY_NAME, None, MNQ)
    assert strategy.params["rr"] == 2.0  # RR 2:1 por defecto


def test_config_yaml_declares_rr2():
    import yaml
    from pathlib import Path
    cfg = yaml.safe_load(
        (Path(__file__).parent.parent / "config" / "config.yaml").read_text(encoding="utf-8")
    )
    assert cfg["strategy"][STRATEGY_NAME]["rr"] == 2.0


# ---------------------------------------------------------------- señal y RR 2:1
def test_setup_detected_in_crafted_session():
    strategy = create_strategy(STRATEGY_NAME, None, MNQ)
    prepared = strategy.prepare(make_trending_session("2026-01-05"))
    assert prepared["long_setup"].any(), "la sesión construida debe producir al menos un setup"


def test_take_profit_is_exactly_2r():
    result = run_backtest(make_trending_session("2026-01-05"))
    assert len(result.trades) >= 1
    trade = result.trades[0]
    assert trade.direction == LONG
    risk_pts = trade.entry_price - trade.stop_price
    reward_pts = trade.target_price - trade.entry_price
    # 2R exacto salvo el redondeo del target al tick (0.25)
    assert reward_pts == pytest.approx(2.0 * risk_pts, abs=MNQ.tick_size)


def test_stop_of_20_points_gives_40_point_target():
    """La relación 2:1 del enunciado, verificada con la mecánica real del motor."""

    class FixedStopLong(Strategy):
        name = "fixed_stop"

        def prepare(self, df):
            return df

        def signal_for_bar(self, ts, row):
            if ts == self._t:
                return Signal(ts, LONG, row["close"] - 20.0, 2.0, "test")
            return None

    idx = pd.date_range("2026-01-05 09:45", periods=60, freq="1min")
    df = pd.DataFrame(
        {"open": 21000.0, "high": 21000.0, "low": 21000.0, "close": 21000.0, "volume": 1000.0},
        index=pd.DatetimeIndex(idx, name="datetime"),
    )
    cfg = default_config()
    cfg = Config(
        account=cfg.account, risk=cfg.risk,
        execution=ExecutionConfig(slippage_ticks=0, spread_ticks=0),
        session=cfg.session, contracts=cfg.contracts,
    )
    strategy = FixedStopLong(None, MNQ)
    strategy._t = idx[5]
    result = BacktestEngine(cfg, MNQ, strategy).run(df)
    trade = result.trades[0]
    assert trade.entry_price - trade.stop_price == pytest.approx(20.0)
    assert trade.target_price - trade.entry_price == pytest.approx(40.0)  # 2R


# ---------------------------------------------------------------- horarios / overnight
def two_session_trades():
    df = pd.concat(
        [make_trending_session("2026-01-05"), make_trending_session("2026-01-06")]
    )
    return run_backtest(df).trades


def test_no_entries_outside_allowed_hours():
    trades = two_session_trades()
    assert trades, "se esperaba al menos un trade en las sesiones construidas"
    for t in trades:
        assert time(9, 45) <= t.entry_time.time() <= time(15, 15)


def test_no_overnight_positions():
    for t in two_session_trades():
        assert t.entry_time.date() == t.exit_time.date()      # intradía estricto
        assert t.exit_time.time() <= time(15, 50)             # antes del cierre RTH


# ---------------------------------------------------------------- límites diarios
class AlwaysLong(Strategy):
    """Señal en cada barra: fuerza al Risk Manager a intervenir."""

    name = "always_long"

    def prepare(self, df):
        return df

    def signal_for_bar(self, ts, row):
        return Signal(ts, LONG, row["close"] - 2.0, 1.0, "test")


def falling_df() -> pd.DataFrame:
    """Precio cayendo 1 pt/min: cada long muere en el stop enseguida."""
    idx = pd.date_range("2026-01-05 09:45", periods=60, freq="1min")
    rows = []
    for i in range(60):
        close = 1000.0 - i
        rows.append((close + 0.5, close + 0.75, close - 0.5, close, 1000.0))
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"],
                        index=pd.DatetimeIndex(idx, name="datetime"))


def stripped_config(**risk_overrides) -> Config:
    cfg = default_config(**risk_overrides)
    return Config(
        account=AccountConfig(initial_capital=10_000.0), risk=cfg.risk,
        execution=ExecutionConfig(slippage_ticks=0, spread_ticks=0),
        session=cfg.session,
        contracts={"MNQ": ContractSpec("MNQ", 0.25, 2.0, commission_per_side=0.0)},
    )


def test_max_trades_per_day_is_enforced():
    cfg = stripped_config(max_trades_per_day=2, max_consecutive_losses=99,
                          max_daily_loss_pct=90.0)
    result = BacktestEngine(cfg, MNQ, AlwaysLong(None, MNQ)).run(falling_df())
    assert len(result.trades) == 2  # la tercera señal queda bloqueada


def test_consecutive_losses_lock_the_session():
    cfg = stripped_config(max_trades_per_day=99, max_consecutive_losses=2,
                          max_daily_loss_pct=90.0)
    result = BacktestEngine(cfg, MNQ, AlwaysLong(None, MNQ)).run(falling_df())
    assert len(result.trades) == 2  # dos pérdidas seguidas -> bloqueo
    assert all(t.pnl_net < 0 for t in result.trades)
