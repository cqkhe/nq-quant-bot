import pandas as pd
import pytest

from nqbot.data.loader import DataLoadError, load_ohlcv_csv, parse_ohlcv_csv

CSV_MESSY = """datetime,open,high,low,close,volume
2026-01-05 09:32:00,101,102,100,101,10
2026-01-05 09:30:00,100,101,99,100,10
2026-01-05 09:31:00,100.5,101.5,99.5,101,12
2026-01-05 09:31:00,100.5,101.5,99.5,101,12
2026-01-05 09:33:00,,103,101,102,8
"""


def test_sorts_dedups_and_drops_bad_rows(tmp_path):
    f = tmp_path / "messy.csv"
    f.write_text(CSV_MESSY)
    df = load_ohlcv_csv(f)
    # 5 filas de entrada: 1 duplicada + 1 con OHLC faltante -> quedan 3
    assert len(df) == 3
    assert df.index.is_monotonic_increasing
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_column_aliases(tmp_path):
    f = tmp_path / "alias.csv"
    f.write_text("Time,O,H,L,C,Vol\n2026-01-05 09:30,1,2,0.5,1.5,10\n")
    df = load_ohlcv_csv(f)
    assert df.iloc[0]["close"] == 1.5
    assert df.iloc[0]["volume"] == 10


def test_missing_volume_raises(tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text("datetime,open,high,low,close\n2026-01-05 09:30,1,2,0.5,1\n")
    with pytest.raises(DataLoadError):
        load_ohlcv_csv(f)


def test_missing_file_raises():
    with pytest.raises(DataLoadError):
        load_ohlcv_csv("no_existe.csv")


# ---------------------------------------------------------------- NinjaTrader
NT_CONTENT = (
    "20260628 220100;29280.5;29340.25;29280;29333.75;3258\n"
    "20260628 220200;29333.5;29395;29323.25;29394.5;3668\n"
)


def test_ninjatrader_format_autodetected_and_converted_to_et(tmp_path):
    f = tmp_path / "nt.txt"
    f.write_text(NT_CONTENT)
    df, meta = parse_ohlcv_csv(f)
    assert meta.had_timezone  # queda documentado que hubo conversión de tz
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    # 2026-06-28 22:01 UTC -> 18:01 ET (verano: EDT, UTC-4) = reapertura Globex del domingo
    assert df.index[0] == pd.Timestamp("2026-06-28 18:01:00")
    assert df.iloc[0]["open"] == 29280.5
    assert df.iloc[1]["volume"] == 3668


def test_ninjatrader_winter_timestamps_use_est(tmp_path):
    f = tmp_path / "nt_winter.txt"
    f.write_text("20260115 143000;100;101;99;100.5;500\n")
    df, _ = parse_ohlcv_csv(f)
    # 2026-01-15 14:30 UTC -> 09:30 ET (invierno: EST, UTC-5)
    assert df.index[0] == pd.Timestamp("2026-01-15 09:30:00")


def test_ninjatrader_loads_end_to_end(tmp_path):
    f = tmp_path / "nt.txt"
    f.write_text(NT_CONTENT)
    df = load_ohlcv_csv(f)  # parse + saneo, como lo consume el motor
    assert len(df) == 2
    assert df.index.is_monotonic_increasing


def test_csv_with_headers_still_uses_generic_parser(tmp_path):
    # una fila con ';' en un CSV normal no debe confundirse con NinjaTrader
    f = tmp_path / "normal.csv"
    f.write_text("datetime,open,high,low,close,volume\n2026-01-05 09:30,1,2,0.5,1.5,10\n")
    df, meta = parse_ohlcv_csv(f)
    assert not meta.had_timezone
    assert df.index[0] == pd.Timestamp("2026-01-05 09:30:00")
