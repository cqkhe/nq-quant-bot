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
