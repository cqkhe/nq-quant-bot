"""Fixtures compartidas. pytest agrega src/ al path vía pyproject.toml."""

from datetime import datetime

import pandas as pd
import pytest

from nqbot.backtesting.models import Trade
from nqbot.config.settings import ContractSpec


@pytest.fixture
def mnq() -> ContractSpec:
    return ContractSpec(symbol="MNQ", tick_size=0.25, point_value=2.0, commission_per_side=1.0)


@pytest.fixture
def make_trade():
    """Trade mínimo válido para tests de riesgo/métricas (solo importa el PnL)."""

    def _make(pnl_net: float, r_multiple: float = 0.0) -> Trade:
        return Trade(
            symbol="MNQ", direction=1, contracts=1,
            entry_time=datetime(2026, 1, 5, 10, 0), entry_price=100.0,
            exit_time=datetime(2026, 1, 5, 10, 30), exit_price=100.0,
            stop_price=99.0, target_price=102.0, exit_reason="stop",
            pnl_gross=pnl_net, commission=0.0, pnl_net=pnl_net,
            initial_risk_dollars=100.0, r_multiple=r_multiple, bars_held=5, reason="test",
        )

    return _make


@pytest.fixture
def flat_df():
    """60 barras 1m planas en 100.0 para tests del motor."""
    idx = pd.date_range("2026-01-05 09:30", periods=60, freq="1min")
    return pd.DataFrame(
        {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1000.0},
        index=pd.DatetimeIndex(idx, name="datetime"),
    )
