import pandas as pd

from nqbot.backtesting.models import LONG
from nqbot.config.settings import ContractSpec
from nqbot.strategies.ohlcv_volume import (
    GaussianVolumeDryUpBreakout,
    GaussianVolumeReversal,
    RelativeVolumeBreakout,
    VolumeDryUpBreakout,
    VwapVolumeReclaim,
)
from nqbot.strategies.registry import available_strategies, create_strategy
from nqbot.strategy_lab import available_families, get_family


MNQ = ContractSpec(symbol="MNQ", tick_size=0.25, point_value=2.0, commission_per_side=0.79)

EXECUTABLE_VOLUME_FAMILIES = {
    "relative_volume_breakout",
    "volume_climax_reversal",
    "volume_dry_up_breakout",
    "opening_range_volume_breakout",
    "gaussian_volume_breakout",
    "gaussian_volume_reversal",
    "gaussian_volume_dry_up_breakout",
    "vwap_volume_reclaim",
}


def _strategy_params(**overrides):
    params = {
        "volume_window": 3,
        "breakout_lookback": 3,
        "opening_range_minutes": 3,
        "skip_open_minutes": 0,
        "dry_up_lookback": 3,
        "rel_volume_threshold": 1.5,
        "spike_threshold": 1.5,
        "dry_up_threshold": 0.8,
        "volume_zscore_threshold": 1.5,
        "dry_up_zscore_threshold": -1.0,
        "min_vwap_extension_points": 2.0,
        "min_stop_points": 0.25,
        "max_stop_points": 30.0,
        "stop_lookback": 3,
        "rr": 1.5,
    }
    params.update(overrides)
    return params


def _df(rows):
    idx = pd.date_range("2026-01-05 09:30", periods=len(rows), freq="1min")
    return pd.DataFrame(
        rows,
        columns=["open", "high", "low", "close", "volume"],
        index=pd.DatetimeIndex(idx, name="datetime"),
    )


def test_volume_strategy_registry_and_family_execution_flags():
    strategies = set(available_strategies())
    families = set(available_families(include_scaffolds=False))

    assert EXECUTABLE_VOLUME_FAMILIES.issubset(strategies)
    assert EXECUTABLE_VOLUME_FAMILIES.issubset(families)
    assert all(get_family(name).implemented for name in EXECUTABLE_VOLUME_FAMILIES)
    assert create_strategy("relative_volume_breakout", _strategy_params(), MNQ).name == (
        "relative_volume_breakout"
    )


def test_relative_volume_breakout_signal_uses_prior_range_only():
    rows = [
        (100.0, 101.0, 99.5, 100.5, 100.0),
        (100.5, 101.5, 100.0, 101.0, 100.0),
        (101.0, 102.0, 100.5, 101.5, 100.0),
        (101.5, 102.5, 101.0, 102.0, 100.0),
        (102.0, 103.0, 101.5, 102.5, 100.0),
        (102.5, 103.5, 102.0, 103.0, 100.0),
        (103.0, 110.0, 102.5, 105.0, 300.0),
    ]
    strategy = RelativeVolumeBreakout(_strategy_params(), MNQ)
    prepared = strategy.prepare(_df(rows))
    signal_row = prepared.iloc[-1]

    assert signal_row["breakout_high"] == 103.5
    assert signal_row["rel_volume"] == 3.0
    assert signal_row["long_setup"]
    signal = strategy.signal_for_bar(prepared.index[-1].to_pydatetime(), signal_row)
    assert signal is not None
    assert signal.direction == LONG

    changed = _df(rows)
    changed.iloc[-1, changed.columns.get_loc("high")] = 500.0
    changed_prepared = strategy.prepare(changed)
    assert changed_prepared.iloc[-1]["breakout_high"] == signal_row["breakout_high"]


def test_volume_dry_up_breakout_requires_past_dry_up_then_current_expansion():
    rows = [
        (100.0, 101.0, 99.5, 100.5, 100.0),
        (100.5, 101.5, 100.0, 101.0, 100.0),
        (101.0, 102.0, 100.5, 101.5, 100.0),
        (101.5, 102.5, 101.0, 102.0, 50.0),
        (102.0, 103.0, 101.5, 102.5, 80.0),
        (102.5, 104.0, 102.0, 103.0, 100.0),
        (103.0, 106.0, 102.5, 105.0, 220.0),
    ]
    strategy = VolumeDryUpBreakout(_strategy_params(), MNQ)
    prepared = strategy.prepare(_df(rows))
    signal_row = prepared.iloc[-1]

    assert prepared.iloc[3]["rel_volume"] == 0.5
    assert signal_row["dry_up_recent"]
    assert signal_row["rel_volume"] > 1.5
    assert signal_row["long_setup"]


def test_gaussian_dry_up_breakout_uses_past_zscore_dry_up():
    rows = [
        (100.0, 101.0, 99.5, 100.5, 90.0),
        (100.5, 101.5, 100.0, 101.0, 100.0),
        (101.0, 102.0, 100.5, 101.5, 110.0),
        (101.5, 102.5, 101.0, 102.0, 80.0),
        (102.0, 103.0, 101.5, 102.5, 100.0),
        (102.5, 104.0, 102.0, 103.0, 100.0),
        (103.0, 107.0, 102.5, 106.0, 180.0),
    ]
    strategy = GaussianVolumeDryUpBreakout(_strategy_params(), MNQ)
    prepared = strategy.prepare(_df(rows))

    assert prepared.iloc[3]["volume_zscore"] < -1.0
    assert prepared.iloc[-1]["gaussian_dry_up_recent"]
    assert prepared.iloc[-1]["volume_zscore"] > 1.5
    assert prepared.iloc[-1]["long_setup"]


def test_gaussian_volume_reversal_detects_climax_rejection_without_orderflow():
    rows = [
        (100.0, 101.0, 99.5, 100.5, 90.0),
        (100.5, 101.5, 100.0, 101.0, 100.0),
        (101.0, 102.0, 100.5, 101.5, 110.0),
        (101.5, 102.0, 100.0, 101.0, 100.0),
        (85.0, 92.0, 80.0, 91.0, 180.0),
    ]
    strategy = GaussianVolumeReversal(_strategy_params(), MNQ)
    prepared = strategy.prepare(_df(rows))
    signal_row = prepared.iloc[-1]

    assert signal_row["volume_zscore"] > 1.5
    assert signal_row["vwap"] - signal_row["close"] >= 2.0
    assert signal_row["long_setup"]
    signal = strategy.signal_for_bar(prepared.index[-1].to_pydatetime(), signal_row)
    assert signal is not None
    assert signal.direction == LONG


def test_vwap_volume_reclaim_requires_cross_back_through_vwap_with_volume():
    rows = [
        (100.0, 101.0, 99.5, 100.5, 100.0),
        (100.5, 101.0, 99.5, 100.0, 100.0),
        (100.0, 100.5, 98.0, 98.5, 100.0),
        (98.5, 99.0, 97.5, 98.0, 100.0),
        (98.0, 102.0, 97.5, 101.5, 300.0),
    ]
    strategy = VwapVolumeReclaim(_strategy_params(max_vwap_distance_points=10.0), MNQ)
    prepared = strategy.prepare(_df(rows))
    signal_row = prepared.iloc[-1]

    assert signal_row["prev_close"] < signal_row["prev_vwap"]
    assert signal_row["close"] > signal_row["vwap"]
    assert signal_row["rel_volume"] == 3.0
    assert signal_row["long_setup"]
