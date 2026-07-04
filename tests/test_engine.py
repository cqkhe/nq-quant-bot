"""Test end-to-end del motor con una estrategia sintética de control.

Verifica el ciclo completo y la ausencia de lookahead: la señal se genera
al cierre de la barra t y el fill ocurre exactamente en el open de t+1.
"""

from datetime import datetime, time

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


class OneShotLong(Strategy):
    """Emite una única señal long en un timestamp exacto (control total)."""

    name = "oneshot_long"

    def __init__(self, contract: ContractSpec, signal_time: datetime, stop: float, rr: float):
        super().__init__({"rr": rr}, contract)
        self._signal_time = signal_time
        self._stop = stop

    def prepare(self, df):
        return df

    def signal_for_bar(self, ts, row):
        if ts == self._signal_time:
            return Signal(ts, LONG, self._stop, self.params["rr"], "test")
        return None


def _config(contract: ContractSpec) -> Config:
    return Config(
        account=AccountConfig(initial_capital=10_000.0),
        risk=RiskConfig(
            risk_per_trade_pct=1.0, max_daily_loss_pct=50.0, max_trades_per_day=10,
            max_consecutive_losses=10, max_contracts=10, max_stop_points=100.0,
        ),
        execution=ExecutionConfig(slippage_ticks=0),
        session=SessionConfig(entry_start=time(9, 30)),
        contracts={contract.symbol: contract},
    )


def test_signal_fills_next_open_and_exits_at_target(flat_df):
    contract = ContractSpec("MNQ", tick_size=0.25, point_value=2.0, commission_per_side=0.0)
    df = flat_df.copy()
    idx = df.index
    df.loc[idx[20], "high"] = 115.0  # el target (110) se alcanza en la barra 20

    strategy = OneShotLong(contract, idx[10], stop=90.0, rr=1.0)
    result = BacktestEngine(_config(contract), contract, strategy).run(df)

    assert len(result.trades) == 1
    trade = result.trades[0]
    # Señal al cierre de idx[10] -> fill en el OPEN de idx[11] (sin lookahead)
    assert trade.entry_time == idx[11]
    assert trade.entry_price == 100.0
    # Riesgo 1% de $10k = $100; stop a 10 pts * $2 = $20/contrato -> 5 contratos
    assert trade.contracts == 5
    assert trade.exit_time == idx[20]
    assert trade.exit_reason == "target"
    assert trade.exit_price == 110.0
    assert trade.pnl_net == 100.0  # 10 pts * $2 * 5, sin comisiones

    assert result.equity_curve.iloc[-1] == 10_100.0


def test_open_position_is_flattened_at_session_end(flat_df):
    contract = ContractSpec("MNQ", tick_size=0.25, point_value=2.0, commission_per_side=0.0)
    df = flat_df.copy()  # nada toca stop ni target: debe cerrar por fin de sesión

    strategy = OneShotLong(contract, df.index[10], stop=90.0, rr=5.0)
    result = BacktestEngine(_config(contract), contract, strategy).run(df)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "session_flatten"
    assert trade.exit_time == df.index[-1]  # última barra del dataset
    assert result.equity_curve.iloc[-1] == 10_000.0  # entró y salió a 100.0
