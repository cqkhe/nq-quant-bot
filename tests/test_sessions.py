from datetime import time

import pandas as pd

from nqbot.config.settings import SessionConfig
from nqbot.utils.sessions import (
    expected_bars_per_session,
    filter_to_trade_session,
    time_in_range,
    trade_session_key,
    window_minutes,
)


def test_time_in_range_normal_window():
    assert time_in_range(time(9, 30), time(9, 30), time(16, 0))
    assert time_in_range(time(15, 59), time(9, 30), time(16, 0))
    assert not time_in_range(time(16, 0), time(9, 30), time(16, 0))
    assert time_in_range(time(16, 0), time(9, 30), time(16, 0), inclusive_end=True)
    assert not time_in_range(time(4, 0), time(9, 30), time(16, 0))


def test_time_in_range_overnight_wrap():
    start, end = time(18, 0), time(4, 0)  # cruza medianoche
    assert time_in_range(time(23, 0), start, end)
    assert time_in_range(time(2, 0), start, end)
    assert time_in_range(time(18, 0), start, end)
    assert not time_in_range(time(12, 0), start, end)
    assert not time_in_range(time(4, 0), start, end)


def test_trade_session_key_assigns_globex_evening_to_next_day():
    cfg = SessionConfig()
    idx = pd.DatetimeIndex(
        ["2026-01-05 10:00", "2026-01-05 18:30", "2026-01-05 03:00"]  # lunes
    )
    keys = trade_session_key(idx, cfg)
    assert keys[0] == pd.Timestamp("2026-01-05")  # RTH del lunes
    assert keys[1] == pd.Timestamp("2026-01-06")  # 18:30 abre la sesión del martes
    assert keys[2] == pd.Timestamp("2026-01-05")  # madrugada: cola de la sesión del lunes


def test_filter_to_trade_session_regular():
    cfg = SessionConfig(trade_session="regular")
    idx = pd.DatetimeIndex(
        ["2026-01-05 04:30", "2026-01-05 09:30", "2026-01-05 15:59",
         "2026-01-05 16:00", "2026-01-05 19:00"]
    )
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    out = filter_to_trade_session(df, cfg)
    assert list(out.index.time) == [time(9, 30), time(15, 59)]


def test_expected_bars_per_session_by_window():
    assert expected_bars_per_session(SessionConfig(trade_session="regular")) == 390
    assert expected_bars_per_session(SessionConfig(trade_session="premarket")) == 330
    assert expected_bars_per_session(SessionConfig(trade_session="overnight")) == 600
    assert expected_bars_per_session(SessionConfig(trade_session="all")) == 1380


def test_window_minutes_wraps_midnight():
    assert window_minutes(time(18, 0), time(4, 0)) == 600
    assert window_minutes(time(9, 30), time(16, 0)) == 390
