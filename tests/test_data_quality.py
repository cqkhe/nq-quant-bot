"""Tests del auditor de calidad: datasets válidos e inválidos fabricados a mano."""

from datetime import date, time as dtime

import numpy as np
import pandas as pd
import pytest

from nqbot.config.settings import CalendarConfig, DataQualityConfig, SessionConfig
from nqbot.data.quality import (
    SEV_ERROR,
    SEV_WARNING,
    DataQualityChecker,
    DataQualityError,
    assert_fit_for_backtest,
)

SESSION = SessionConfig()  # trade_session=regular
DQ = DataQualityConfig()


def make_clean_rth(days: int = 2, start: str = "2026-01-05", start_time: str = "09:30") -> pd.DataFrame:
    """Sesiones RTH 1m completas (390 barras), precios coherentes y sin saltos."""
    hh, mm = (int(x) for x in start_time.split(":"))
    frames = []
    price = 21000.0
    for day in pd.bdate_range(start, periods=days):
        idx = pd.date_range(day + pd.Timedelta(hours=hh, minutes=mm), periods=390, freq="1min")
        close = price + np.linspace(0, 5, 390)
        frames.append(
            pd.DataFrame(
                {"open": close, "high": close + 1.0, "low": close - 1.0,
                 "close": close, "volume": 1000.0},
                index=pd.DatetimeIndex(idx, name="datetime"),
            )
        )
        price += 5.0
    return pd.concat(frames)


def check(df: pd.DataFrame, calendar: CalendarConfig | None = None):
    return DataQualityChecker(SESSION, DQ, calendar=calendar).check(df)


def codes(report, severity: str) -> set[str]:
    return {i.code for i in report.issues if i.severity == severity}


# ---------------------------------------------------------------- datos válidos
def test_clean_data_is_fit_for_backtest():
    report = check(make_clean_rth())
    assert not report.has_errors
    assert report.verdict == "APTO PARA BACKTEST"
    assert report.issues == []
    assert_fit_for_backtest(report)  # no lanza


# ---------------------------------------------------------------- duplicados
def test_few_duplicates_warn_but_do_not_block():
    df = make_clean_rth()
    df = pd.concat([df, df.iloc[:3]]).sort_index()  # 3/783 = 0.38% < 1%
    report = check(df)
    assert "duplicados" in codes(report, SEV_WARNING)
    assert not report.has_errors


# ---------------------------------------------------------------- velas faltantes
def test_excessive_missing_bars_block_backtest():
    df = make_clean_rth().drop(make_clean_rth().index[100:160])  # 60/780 = 7.7% > 5%
    report = check(df)
    assert "velas_faltantes" in codes(report, SEV_ERROR)
    with pytest.raises(DataQualityError):
        assert_fit_for_backtest(report)


def test_partial_final_session_is_not_missing_data():
    """Media jornada de feriado (o export a mitad de rueda) al FINAL del dataset:
    la última sesión solo espera velas hasta su última barra observada."""
    import datetime as dt

    df = make_clean_rth(days=2)
    last_day = df.index.normalize()[-1]
    truncated = df[(df.index.normalize() != last_day) | (df.index.time < dt.time(13, 0))]
    report = check(truncated)  # día 2 termina 12:59 (media rueda)
    assert "velas_faltantes" not in {i.code for i in report.issues}
    assert not report.has_errors


def test_few_missing_bars_only_warn():
    df = make_clean_rth().drop(make_clean_rth().index[100:110])  # 10/780 = 1.3% < 5%
    report = check(df)
    assert "velas_faltantes" in codes(report, SEV_WARNING)
    assert not report.has_errors


# ---------------------------------------------------------------- nulos
def test_excessive_nulls_block_backtest():
    df = make_clean_rth()
    df.iloc[10:30, df.columns.get_loc("open")] = np.nan  # 20/780 = 2.6% > 1%
    report = check(df)
    assert "nulos" in codes(report, SEV_ERROR)


def test_few_nulls_only_warn():
    df = make_clean_rth()
    df.iloc[10:15, df.columns.get_loc("open")] = np.nan  # 5/780 = 0.6% < 1%
    report = check(df)
    assert "nulos" in codes(report, SEV_WARNING)
    assert not report.has_errors


# ---------------------------------------------------------------- precios incoherentes
def test_impossible_ohlc_blocks_backtest():
    df = make_clean_rth()
    df.iloc[5:15, df.columns.get_loc("high")] = 100.0  # high << low: 10/780 = 1.3% > 0.5%
    report = check(df)
    assert "precios_incoherentes" in codes(report, SEV_ERROR)


# ---------------------------------------------------------------- volumen cero
def test_excessive_zero_volume_blocks_backtest():
    df = make_clean_rth()
    df.iloc[0:50, df.columns.get_loc("volume")] = 0.0  # 50/780 = 6.4% > 5%
    report = check(df)
    assert "volumen_cero" in codes(report, SEV_ERROR)


def test_some_zero_volume_only_warns():
    df = make_clean_rth()
    df.iloc[0:10, df.columns.get_loc("volume")] = 0.0  # 1.3% < 5%
    report = check(df)
    assert "volumen_cero" in codes(report, SEV_WARNING)
    assert not report.has_errors


# ---------------------------------------------------------------- gaps de sesión
def test_intra_session_gap_is_reported_with_timestamps():
    base = make_clean_rth()
    df = base.drop(base.index[60:70])  # hueco contiguo de 10 min a las 10:30
    report = check(df)
    gap_msgs = [i.message for i in report.issues if i.code == "gaps_sesion"]
    assert gap_msgs and "10:29" in gap_msgs[0]  # el gap arranca tras la barra 10:29
    assert not report.has_errors  # 10 velas: por debajo del umbral global


# ---------------------------------------------------------------- fin de semana / timezone
def test_weekend_bars_block_backtest():
    df = make_clean_rth()
    saturday = pd.date_range("2026-01-10 09:30", periods=60, freq="1min")  # sábado
    extra = pd.DataFrame(
        {"open": 21000.0, "high": 21001.0, "low": 20999.0, "close": 21000.0, "volume": 1000.0},
        index=pd.DatetimeIndex(saturday, name="datetime"),
    )
    report = check(pd.concat([df, extra]).sort_index())
    assert "fin_de_semana" in codes(report, SEV_ERROR)


def test_utc_looking_data_blocks_backtest():
    # Sesiones "RTH" que arrancan 14:30: patrón típico de datos en UTC (ET+5)
    report = check(make_clean_rth(days=2, start_time="14:30"))
    assert "timezone" in codes(report, SEV_ERROR)


def test_no_bars_in_configured_session_blocks_backtest():
    premarket_only = make_clean_rth(days=1, start_time="04:00").iloc[:329]  # termina 09:28
    report = check(premarket_only)
    assert "sesion_sin_datos" in codes(report, SEV_ERROR)


# ---------------------------------------------------------------- calendario CME
def test_sunday_bar_does_not_create_expected_rth_session():
    """Un print espurio de domingo en horario RTH no debe crear una 'sesión
    fantasma' que espere 390 velas, ni bloquear el dataset."""
    df = make_clean_rth(days=3)  # lun 05, mar 06, mié 07
    ghost = pd.DataFrame(
        {"open": [21000.0], "high": [21001.0], "low": [20999.0],
         "close": [21000.0], "volume": [500.0]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-01-04 11:00")], name="datetime"),  # domingo
    )
    report = check(pd.concat([ghost, df]))
    assert "velas_faltantes" not in {i.code for i in report.issues}
    assert "fin_de_semana" in codes(report, SEV_WARNING)  # 1 barra: warning, no error
    assert not report.has_errors
    assert "2026-01-04" in str(report.stats["Sesiones ignoradas (fin de semana)"])


def test_configured_holiday_not_counted_as_missing():
    df = make_clean_rth(days=3)  # lun, mar, mié
    holiday = pd.Timestamp("2026-01-06").normalize()
    # el "feriado" (martes, en el medio) solo trae 50 barras de datos espurios
    mask = (df.index.normalize() != holiday) | (df.index.time < dtime(10, 20))
    truncated = df[mask]

    sin_calendario = check(truncated)
    assert "velas_faltantes" in codes(sin_calendario, SEV_ERROR)  # 340/1170 = 29%

    con_calendario = check(truncated, CalendarConfig(no_session=frozenset({date(2026, 1, 6)})))
    assert "velas_faltantes" not in {i.code for i in con_calendario.issues}
    assert not con_calendario.has_errors
    assert "2026-01-06" in str(con_calendario.stats["Sesiones ignoradas (feriado)"])
    assert "feriado_con_datos" in codes(con_calendario, SEV_WARNING)


def test_configured_partial_session_not_counted_as_missing():
    df = make_clean_rth(days=3)
    early_close_day = pd.Timestamp("2026-01-06").normalize()
    # cierre anticipado 13:00 en el MEDIO del dataset (la regla de "última
    # sesión parcial por export" no aplica acá)
    mask = (df.index.normalize() != early_close_day) | (df.index.time < dtime(13, 0))
    truncated = df[mask]

    sin_calendario = check(truncated)
    assert "velas_faltantes" in codes(sin_calendario, SEV_ERROR)  # 180/1170 = 15%

    calendar = CalendarConfig(partial_session={date(2026, 1, 6): dtime(13, 0)})
    con_calendario = check(truncated, calendar)
    assert "velas_faltantes" not in {i.code for i in con_calendario.issues}
    assert not con_calendario.has_errors
    assert "2026-01-06" in str(con_calendario.stats["Sesiones parciales aceptadas"])


def test_real_intraday_gap_still_flagged_even_with_calendar():
    df = make_clean_rth(days=2)
    gap_df = df.drop(df.index[30:43])  # hueco real de 13 min el día 1 (sesión normal)
    calendar = CalendarConfig(partial_session={date(2026, 1, 6): dtime(13, 0)})
    report = check(gap_df, calendar)
    assert "gaps_sesion" in codes(report, SEV_WARNING)
    assert report.stats["Gaps reales detectados"] >= 1
