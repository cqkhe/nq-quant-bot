"""Data Loader — carga de históricos OHLCV desde CSV.

Dos niveles, a propósito:

  * `parse_ohlcv_csv`  -> parsea el CSV SIN limpiar (solo normaliza columnas
    y timestamps). Es lo que consume la auditoría de calidad: debe ver los
    duplicados, nulos e incoherencias tal como vienen del proveedor.
  * `load_ohlcv_csv`   -> parse + saneo (validators.validate_ohlcv). Es lo
    que consume el motor. Contrato estable desde la fase 1.

Tolerante con el formato de origen (alias de columnas, epoch o texto,
'date' + 'time' separados, timestamps con offset de timezone, exports de
NinjaTrader sin encabezado) pero estricto con la salida: columnas
open/high/low/close/volume en float e índice DatetimeIndex naive en hora
del exchange (ET).

Formato NinjaTrader (autodetectado): sin encabezados, separado por ';',
timestamps 'YYYYMMDD HHMMSS' en UTC:
    20260628 220100;29280.5;29340.25;29280;29333.75;3258
Se convierte UTC -> America/New_York y se deja naive, igual que el resto.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .validators import validate_ohlcv

# alias -> nombre canónico (comparación en minúsculas, sin espacios)
_COLUMN_ALIASES: dict[str, str] = {
    "open": "open", "o": "open",
    "high": "high", "h": "high",
    "low": "low", "l": "low",
    "close": "close", "c": "close", "last": "close",
    "volume": "volume", "vol": "volume", "v": "volume",
}
_DATETIME_CANDIDATES = ("datetime", "timestamp", "date_time", "time", "date")

# Fila NinjaTrader: 'YYYYMMDD HHMMSS;o;h;l;c;v' (sin encabezado)
_NINJATRADER_ROW = re.compile(r"^\d{8} \d{6};")


def _sniff_ninjatrader(path: Path) -> bool:
    """¿La primera línea coincide con el export sin encabezado de NinjaTrader?"""
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
        first = fh.readline().strip()
    return bool(_NINJATRADER_ROW.match(first)) and first.count(";") == 5


class DataLoadError(Exception):
    """El CSV no se pudo interpretar como OHLCV."""


@dataclass(frozen=True)
class ParseMeta:
    """Metadatos del parseo, insumo de la auditoría de calidad."""

    source: str
    rows_in_file: int
    invalid_timestamps: int = 0
    had_timezone: bool = False  # el archivo traía offsets tz -> se convirtió a ET


def _to_datetime(series: pd.Series) -> pd.Series:
    """Parsea texto o epoch (segundos/milisegundos) a datetime."""
    if pd.api.types.is_numeric_dtype(series):
        unit = "ms" if series.dropna().abs().max() > 1e11 else "s"
        return pd.to_datetime(series, unit=unit, errors="coerce")
    return pd.to_datetime(series, errors="coerce", format="mixed")


def _normalize_timezone(ts: pd.Series, tz: str) -> tuple[pd.Series, bool]:
    """Si los timestamps traen timezone, convierte a `tz` y deja naive."""
    if isinstance(ts.dtype, pd.DatetimeTZDtype):
        return ts.dt.tz_convert(tz).dt.tz_localize(None), True
    if ts.dtype == object:
        # offsets mixtos (ej: -05:00 y -04:00 por DST) quedan como object:
        # re-parsear vía UTC y convertir al huso del exchange
        converted = pd.to_datetime(ts, errors="coerce", utc=True)
        return converted.dt.tz_convert(tz).dt.tz_localize(None), True
    return ts, False


def parse_ohlcv_csv(
    path: str | Path,
    logger: logging.Logger | None = None,
    timezone: str = "America/New_York",
) -> tuple[pd.DataFrame, ParseMeta]:
    """Parsea un CSV OHLCV sin sanearlo (duplicados/nulos quedan a la vista)."""
    log = logger or logging.getLogger("nqbot")
    path = Path(path)
    if not path.exists():
        raise DataLoadError(f"No existe el archivo de datos: {path}")

    if _sniff_ninjatrader(path):
        # Export de NinjaTrader: sin encabezado, ';', 'YYYYMMDD HHMMSS' en UTC
        log.info("Datos: formato NinjaTrader detectado (sin encabezado, sep=';', UTC)")
        renamed = pd.read_csv(
            path, sep=";", header=None,
            names=["datetime_raw", "open", "high", "low", "close", "volume"],
        )
        rows_in_file = len(renamed)
        ts = pd.to_datetime(renamed["datetime_raw"], format="%Y%m%d %H%M%S", errors="coerce")
        ts = ts.dt.tz_localize("UTC")  # NinjaTrader exporta en UTC
    else:
        raw = pd.read_csv(path)
        rows_in_file = len(raw)
        raw.columns = [str(c).strip().lower() for c in raw.columns]

        # 1) Resolver la columna temporal
        if "date" in raw.columns and "time" in raw.columns:
            ts = pd.to_datetime(
                raw["date"].astype(str).str.strip() + " " + raw["time"].astype(str).str.strip(),
                errors="coerce", format="mixed",
            )
        else:
            dt_col = next((c for c in _DATETIME_CANDIDATES if c in raw.columns), None)
            if dt_col is None:
                raise DataLoadError(
                    f"No se encontró columna temporal ({_DATETIME_CANDIDATES}). "
                    f"Columnas presentes: {list(raw.columns)}"
                )
            ts = _to_datetime(raw[dt_col])

        # 2) Renombrar OHLCV por alias
        renamed = raw.rename(columns=_COLUMN_ALIASES)

    ts, had_tz = _normalize_timezone(ts, timezone)
    if had_tz:
        log.warning("Datos: timestamps con timezone -> convertidos a %s (naive)", timezone)

    missing = [c for c in ("open", "high", "low", "close", "volume") if c not in renamed.columns]
    if missing:
        raise DataLoadError(
            f"Faltan columnas OHLCV: {missing}. Columnas presentes: {list(renamed.columns)}"
        )

    df = renamed[["open", "high", "low", "close", "volume"]].copy()
    df.index = pd.DatetimeIndex(ts, name="datetime")

    bad_ts = df.index.isna()
    invalid_timestamps = int(bad_ts.sum())
    if invalid_timestamps:
        log.warning("Datos: %d filas con timestamp inválido descartadas", invalid_timestamps)
        df = df[~bad_ts]

    df = df.apply(pd.to_numeric, errors="coerce")

    meta = ParseMeta(
        source=str(path),
        rows_in_file=rows_in_file,
        invalid_timestamps=invalid_timestamps,
        had_timezone=had_tz,
    )
    return df, meta


def load_ohlcv_csv(path: str | Path, logger: logging.Logger | None = None) -> pd.DataFrame:
    """Parsea + sanea. Lo que consume el motor de backtesting."""
    log = logger or logging.getLogger("nqbot")
    df, _meta = parse_ohlcv_csv(path, log)
    df, warnings = validate_ohlcv(df)
    for w in warnings:
        log.warning("Datos: %s", w)

    log.info(
        "Datos cargados: %s | %d barras | %s -> %s",
        Path(path).name, len(df), df.index[0], df.index[-1],
    )
    return df
