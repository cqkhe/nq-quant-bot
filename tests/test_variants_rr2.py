"""Tests de las variantes experimentales: los filtros de lado/horario deben
recortar señales de la estrategia original sin alterar su lógica de setup."""

from datetime import datetime

import pandas as pd
import pytest

from nqbot.config.settings import ContractSpec
from nqbot.strategies.registry import available_strategies, create_strategy

MNQ = ContractSpec(symbol="MNQ", tick_size=0.25, point_value=2.0, commission_per_side=0.79)

ORIGINAL = "daytrading_vwap_liquidity_rr2"
NO_MIDDAY = "daytrading_vwap_liquidity_rr2_no_midday"
LONGS_ONLY = "daytrading_vwap_liquidity_rr2_longs_only"
MORNING_ONLY = "daytrading_vwap_liquidity_rr2_morning_only"
COMBINED = "daytrading_vwap_liquidity_rr2_no_midday_longs_only"
VARIANTS = [NO_MIDDAY, LONGS_ONLY, MORNING_ONLY, COMBINED]


def long_row() -> pd.Series:
    return pd.Series({"long_setup": True, "short_setup": False,
                      "stop_ref_long": 20990.0, "close": 21000.0})


def short_row() -> pd.Series:
    return pd.Series({"long_setup": False, "short_setup": True,
                      "stop_ref_short": 21010.0, "close": 21000.0})


def at(hh: int, mm: int) -> datetime:
    return datetime(2026, 1, 5, hh, mm)


def make(name: str):
    return create_strategy(name, None, MNQ)


def test_variants_registered_and_inherit_rr2():
    for name in VARIANTS:
        assert name in available_strategies()
        assert make(name).params["rr"] == 2.0  # heredan el RR 2:1 de la original


def test_original_strategy_unchanged_by_variants():
    original = make(ORIGINAL)
    assert original.signal_for_bar(at(11, 30), long_row()) is not None   # sin filtro horario
    assert original.signal_for_bar(at(10, 30), short_row()) is not None  # shorts permitidos


def test_no_midday_blocks_11_to_1259():
    s = make(NO_MIDDAY)
    assert s.signal_for_bar(at(10, 59), long_row()) is not None
    assert s.signal_for_bar(at(11, 0), long_row()) is None
    assert s.signal_for_bar(at(12, 59), long_row()) is None
    assert s.signal_for_bar(at(13, 0), long_row()) is not None


def test_longs_only_blocks_shorts():
    s = make(LONGS_ONLY)
    assert s.signal_for_bar(at(10, 30), long_row()) is not None
    assert s.signal_for_bar(at(10, 30), short_row()) is None


def test_morning_only_allows_just_10h():
    s = make(MORNING_ONLY)
    assert s.signal_for_bar(at(9, 59), long_row()) is None
    assert s.signal_for_bar(at(10, 0), long_row()) is not None
    assert s.signal_for_bar(at(10, 59), long_row()) is not None
    assert s.signal_for_bar(at(11, 0), long_row()) is None
    assert s.signal_for_bar(at(14, 0), long_row()) is None


def test_combined_variant_applies_both_filters():
    s = make(COMBINED)
    assert s.signal_for_bar(at(10, 30), long_row()) is not None
    assert s.signal_for_bar(at(10, 30), short_row()) is None   # sin shorts
    assert s.signal_for_bar(at(11, 30), long_row()) is None    # sin mediodía
    assert s.signal_for_bar(at(14, 0), long_row()) is not None


NEAR_VWAP = "daytrading_vwap_liquidity_rr2_no_midday_near_vwap"


def test_near_vwap_registered_and_only_changes_distance():
    s = make(NEAR_VWAP)
    assert NEAR_VWAP in available_strategies()
    assert s.params["rr"] == 2.0
    assert s.params["max_vwap_distance_points_near"] == 30.0
    # el único cambio efectivo: la cota de distancia que aplica prepare()
    assert s.params["max_vwap_distance_points"] == 30.0
    # hereda el bloqueo de mediodía de no_midday
    assert s.signal_for_bar(at(11, 30), long_row()) is None
    # el resto de los parámetros queda idéntico a no_midday
    base = make(NO_MIDDAY)
    for key, value in base.params.items():
        if key != "max_vwap_distance_points":
            assert s.params[key] == value


def test_near_vwap_blocks_setups_far_from_vwap():
    """En la sesión sintética el setup ocurre a ~38 pts del VWAP: no_midday
    lo toma, near_vwap (cota 30) debe descartarlo."""
    from test_daytrading_strategy import make_trending_session

    df = make_trending_session("2026-01-05")
    assert make(NO_MIDDAY).prepare(df)["long_setup"].any()
    assert not make(NEAR_VWAP).prepare(df)["long_setup"].any()


ATR_FILTER = "daytrading_vwap_liquidity_rr2_no_midday_atr_filter"


def test_atr_filter_registered_and_only_adds_threshold():
    s = make(ATR_FILTER)
    assert ATR_FILTER in available_strategies()
    assert s.params["rr"] == 2.0
    assert s.params["min_atr20_points"] == 8.0
    assert s.signal_for_bar(at(11, 30), long_row()) is None  # hereda no_midday
    base = make(NO_MIDDAY)
    for key, value in base.params.items():
        assert s.params[key] == value  # no cambia ningún parámetro heredado


H002_VARIANT = "daytrading_vwap_liquidity_rr2_no_midday_atr_filter_dynamic_exit_h002"


def _trade_state(minutes: float, mfe_r: float):
    from datetime import datetime

    from nqbot.backtesting.models import TradeState

    return TradeState(
        direction=1, contracts=1, entry_time=datetime(2026, 1, 5, 10, 0),
        entry_price=21000.0, stop_price=20990.0, target_price=21020.0,
        initial_risk_dollars=20.0, bars_held=int(minutes), minutes_held=minutes,
        current_close=21000.0, current_r=0.0, mfe_r=mfe_r, mae_r=0.3,
    )


def test_h002_variant_registered_and_inherits_everything():
    s = make(H002_VARIANT)
    assert H002_VARIANT in available_strategies()
    base = make("daytrading_vwap_liquidity_rr2_no_midday_atr_filter")
    for key, value in base.params.items():
        assert s.params[key] == value          # entrada/RR/ATR/midday intactos
    assert s.params["h002_max_minutes"] == 30.0
    assert s.params["h002_min_mfe_r"] == 0.5


def test_h002_frozen_rule_fires_exactly_when_specified():
    from nqbot.backtesting.models import EarlyExitReason

    s = make(H002_VARIANT)
    row = long_row()  # irrelevante para la regla
    # estancado a los 30 min -> sale
    signal = s.should_exit_early(at(10, 30), row, _trade_state(30.0, 0.4))
    assert signal is not None
    assert signal.reason == EarlyExitReason.NO_PROGRESS
    assert signal.detail == "no_progress_30m_05r"
    # a los 29 min todavía no
    assert s.should_exit_early(at(10, 29), row, _trade_state(29.0, 0.4)) is None
    # con MFE >= 0.5R nunca (aunque pasen los 30 min)
    assert s.should_exit_early(at(11, 0), row, _trade_state(60.0, 0.5)) is None
    # la base NO tiene salida dinámica
    assert make("daytrading_vwap_liquidity_rr2_no_midday_atr_filter").should_exit_early(
        at(10, 30), row, _trade_state(30.0, 0.4)) is None


def test_atr_filter_blocks_dead_tape_and_is_neutral_at_zero():
    """La sesión sintética tiene ATR-20 ~0.75 pts (cinta muerta): con el
    umbral default el setup se filtra; con umbral 0 la variante es idéntica
    a no_midday. El ATR se calcula solo con barras pasadas."""
    from nqbot.strategies.registry import create_strategy
    from test_daytrading_strategy import make_trending_session

    df = make_trending_session("2026-01-05")
    assert make(NO_MIDDAY).prepare(df)["long_setup"].any()

    filtered = make(ATR_FILTER).prepare(df)
    assert "atr20" in filtered.columns
    assert not filtered["long_setup"].any()  # ATR ~0.75 < 8.0 -> sin setups

    off = create_strategy(ATR_FILTER, {"min_atr20_points": 0.0}, MNQ)
    assert off.prepare(df)["long_setup"].equals(make(NO_MIDDAY).prepare(df)["long_setup"])
