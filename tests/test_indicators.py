import numpy as np
import pandas as pd
import pytest

from nqbot.indicators import (
    ema,
    last_confirmed_level,
    relative_volume,
    session_vwap,
    swing_flags,
)


def test_ema_matches_pandas_reference():
    s = pd.Series(np.linspace(100, 200, 50))
    assert np.allclose(ema(s, 13), s.ewm(span=13, adjust=False).mean())


def test_session_vwap_resets_each_session():
    idx = pd.DatetimeIndex(
        ["2026-01-05 09:30", "2026-01-05 09:31", "2026-01-05 09:32", "2026-01-06 09:30"]
    )
    df = pd.DataFrame(
        {
            "open": [99, 103, 101, 200],
            "high": [102, 106, 104, 201],
            "low": [98, 102, 100, 199],
            "close": [100, 104, 102, 200],
            "volume": [10, 20, 10, 5],
        },
        index=idx,
    )
    v = session_vwap(df)
    assert v.iloc[0] == pytest.approx(100.0)                      # tp = 100
    assert v.iloc[1] == pytest.approx((100 * 10 + 104 * 20) / 30)  # acumulado
    assert v.iloc[3] == pytest.approx(200.0)                      # nueva sesión: reset


def test_swing_confirmation_has_no_lookahead():
    highs = pd.Series([1, 2, 3, 4, 5, 10, 4, 3, 2, 1], dtype=float)
    k = 2
    is_high, _ = swing_flags(highs, highs, k=k)
    assert is_high.iloc[5]  # pico fractal en i=5

    lvl = last_confirmed_level(highs, is_high, k=k)
    # El swing de i=5 recién se conoce en i=5+k=7: antes no hay nivel
    assert lvl.iloc[:7].isna().all()
    assert (lvl.iloc[7:] == 10).all()


def test_relative_volume_trailing_window():
    vol = pd.Series([3.0, 3.0, 3.0, 6.0])
    rv = relative_volume(vol, window=3)
    assert rv.iloc[:2].isna().all()          # sin historia suficiente
    assert rv.iloc[2] == pytest.approx(1.0)
    assert rv.iloc[3] == pytest.approx(6.0 / 4.0)  # media(3,3,6)=4
