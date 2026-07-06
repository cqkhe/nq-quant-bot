"""Tests de la extensión de salidas dinámicas del motor.

Garantías verificadas:
  1. Sin hook (o hook que devuelve None) el motor produce EXACTAMENTE los
     mismos trades que antes (además, toda la suite existente sigue verde).
  2. Una estrategia dummy puede emitir early_exit y cierra el trade bien.
  3. El hook no se llama sin posición abierta (ni antes del fill ni después
     del cierre).
  4. El early_exit no pisa stop/target si ocurren primero en la misma barra.
  5. El motivo queda registrado como exit_reason="early_exit".
  6. Sin lookahead: el TradeState del hook solo contiene información de
     barras ya transcurridas (un spike futuro no aparece en el MFE).
  7. El session_flatten sigue funcionando igual con el hook presente.
"""

from dataclasses import asdict
from datetime import datetime, time

import pandas as pd
import pytest

from nqbot.backtesting.engine import BacktestEngine
from nqbot.backtesting.models import (
    LONG,
    EarlyExitReason,
    EarlyExitSignal,
    Signal,
)
from nqbot.config.settings import (
    AccountConfig,
    Config,
    ContractSpec,
    ExecutionConfig,
    RiskConfig,
    SessionConfig,
)
from nqbot.strategies.base import Strategy

MNQ = ContractSpec(symbol="MNQ", tick_size=0.25, point_value=2.0, commission_per_side=0.0)


def config() -> Config:
    return Config(
        account=AccountConfig(initial_capital=10_000.0),
        risk=RiskConfig(risk_per_trade_pct=1.0, max_daily_loss_pct=90.0,
                        max_trades_per_day=10, max_consecutive_losses=99,
                        max_contracts=10, max_stop_points=100.0),
        execution=ExecutionConfig(slippage_ticks=0, spread_ticks=0),
        session=SessionConfig(entry_start=time(9, 30)),
        contracts={"MNQ": MNQ},
    )


def flat_df(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2026-01-05 09:30", periods=n, freq="1min")
    return pd.DataFrame(
        {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1000.0},
        index=pd.DatetimeIndex(idx, name="datetime"),
    )


class OneShot(Strategy):
    """Entrada única en un timestamp fijo; sin salida dinámica."""

    name = "oneshot"

    def __init__(self, contract, signal_time, stop=90.0, rr=5.0):
        super().__init__({"rr": rr}, contract)
        self._t, self._stop = signal_time, stop

    def prepare(self, df):
        return df

    def signal_for_bar(self, ts, row):
        if ts == self._t:
            return Signal(ts, LONG, self._stop, self.params["rr"], "test")
        return None


class OneShotHookNone(OneShot):
    """Idéntica, pero con el hook implementado devolviendo siempre None."""

    name = "oneshot_hook_none"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hook_calls: list = []

    def should_exit_early(self, ts, row, trade_state):
        self.hook_calls.append((ts, trade_state))
        return None


class OneShotEarlyExit(OneShotHookNone):
    """Sale anticipadamente cuando el trade lleva >= `minutes` minutos."""

    name = "oneshot_early_exit"

    def __init__(self, *args, minutes=5, **kwargs):
        super().__init__(*args, **kwargs)
        self._minutes = minutes

    def should_exit_early(self, ts, row, trade_state):
        self.hook_calls.append((ts, trade_state))
        if trade_state.minutes_held >= self._minutes:
            return EarlyExitSignal(EarlyExitReason.NO_PROGRESS, "test >= X min")
        return None


def run(strategy, df):
    return BacktestEngine(config(), MNQ, strategy).run(df)


# ------------------------------------------------- 1) equivalencia exacta
def test_hook_returning_none_is_bitwise_identical_to_no_hook():
    df = flat_df()
    baseline = run(OneShot(MNQ, df.index[5]), df)
    with_hook = run(OneShotHookNone(MNQ, df.index[5]), df)
    assert [asdict(t) for t in baseline.trades] == [asdict(t) for t in with_hook.trades]
    assert baseline.equity_curve.equals(with_hook.equity_curve)


# ------------------------------------------------- 2, 5) early exit funciona
def test_early_exit_closes_trade_with_reason():
    df = flat_df()
    strategy = OneShotEarlyExit(MNQ, df.index[5], minutes=5)
    result = run(strategy, df)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "early_exit"                    # motivo registrado
    assert trade.entry_time == df.index[6]                      # fill al open siguiente
    assert trade.exit_time == df.index[11]                      # 5 min después (>=)
    assert trade.exit_price == pytest.approx(100.0)             # cierre, sin costos en test
    assert trade.pnl_net == pytest.approx(0.0)


# ------------------------------------------------- 3) hook solo con posición
def test_hook_only_called_while_position_is_open():
    df = flat_df()
    strategy = OneShotEarlyExit(MNQ, df.index[5], minutes=5)
    run(strategy, df)

    call_times = [ts for ts, _ in strategy.hook_calls]
    assert call_times[0] == df.index[6]     # primera llamada: barra de entrada
    assert call_times[-1] == df.index[11]   # última: la barra del early_exit
    assert len(call_times) == 6             # barras 6..11, nunca sin posición


# ------------------------------------------------- 4) stop gana en la misma barra
def test_stop_beats_early_exit_on_same_bar():
    df = flat_df()
    df.loc[df.index[8], "low"] = 85.0       # el stop (90) se toca en la barra 8
    strategy = OneShotEarlyExit(MNQ, df.index[5], minutes=2)  # querría salir en barra 8
    result = run(strategy, df)

    trade = result.trades[0]
    assert trade.exit_reason == "stop"      # stop/target se evalúan primero
    assert trade.exit_time == df.index[8]
    # y el hook NO fue llamado en la barra del stop (la posición ya cerró)
    assert df.index[8] not in [ts for ts, _ in strategy.hook_calls]


def test_target_beats_early_exit_on_same_bar():
    df = flat_df()
    df.loc[df.index[8], "high"] = 200.0     # target (rr=5 -> 150) se toca en barra 8
    strategy = OneShotEarlyExit(MNQ, df.index[5], minutes=2)
    result = run(strategy, df)
    assert result.trades[0].exit_reason == "target"


# ------------------------------------------------- 6) sin lookahead
def test_trade_state_cannot_see_future_spike():
    df = flat_df(100)
    df.loc[df.index[30], "high"] = 130.0    # spike futuro (+3R con stop a 10 pts)
    strategy = OneShotHookNone(MNQ, df.index[5])  # nunca sale: solo graba estados
    run(strategy, df)

    states = {ts: st for ts, st in strategy.hook_calls}
    assert states[df.index[10]].mfe_r == pytest.approx(0.0)   # el spike NO se ve antes
    assert states[df.index[29]].mfe_r == pytest.approx(0.0)
    assert states[df.index[31]].mfe_r == pytest.approx(3.0)   # y SÍ después de ocurrir
    assert states[df.index[10]].minutes_held == pytest.approx(4.0)
    assert states[df.index[10]].current_r == pytest.approx(0.0)


# ------------------------------------------------- 7) flatten intacto
def test_session_flatten_still_works_with_hook_present():
    df = flat_df(30)
    strategy = OneShotHookNone(MNQ, df.index[5])  # hook presente, nunca sale
    result = run(strategy, df)
    assert result.trades[0].exit_reason == "session_flatten"
    assert result.trades[0].exit_time == df.index[-1]
