"""Validación de calidad de datos OHLCV.

Política: reparar lo reparable (ordenar, deduplicar), descartar lo corrupto
(fila por fila) y dejar constancia de TODO en warnings. Nunca inventar datos.
"""

from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


class DataValidationError(Exception):
    """Los datos no sirven para backtesting y no se pueden reparar."""


def validate_ohlcv(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Valida y sanea un DataFrame OHLCV indexado por datetime.

    Returns:
        (df saneado, lista de warnings legibles).
    Raises:
        DataValidationError: si faltan columnas o no queda ninguna fila válida.
    """
    warnings: list[str] = []

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(f"Faltan columnas requeridas: {missing}")
    if df.empty:
        raise DataValidationError("El dataset está vacío")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise DataValidationError("El índice debe ser DatetimeIndex")

    if not df.index.is_monotonic_increasing:
        df = df.sort_index()
        warnings.append("Índice desordenado: se ordenó cronológicamente")

    dup_mask = df.index.duplicated(keep="first")
    if dup_mask.any():
        df = df[~dup_mask]
        warnings.append(f"Se descartaron {int(dup_mask.sum())} timestamps duplicados")

    nan_mask = df[["open", "high", "low", "close"]].isna().any(axis=1)
    if nan_mask.any():
        df = df[~nan_mask]
        warnings.append(f"Se descartaron {int(nan_mask.sum())} filas con OHLC faltante")

    if df["volume"].isna().any():
        n = int(df["volume"].isna().sum())
        df = df.copy()
        df["volume"] = df["volume"].fillna(0.0)
        warnings.append(f"{n} filas con volumen NaN -> se asumió 0")

    bad_ohlc = (
        (df["high"] < df["low"])
        | (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df[["open", "close"]].min(axis=1))
        | (df["volume"] < 0)
    )
    if bad_ohlc.any():
        df = df[~bad_ohlc]
        warnings.append(f"Se descartaron {int(bad_ohlc.sum())} filas con OHLC/volumen inconsistente")

    if df.empty:
        raise DataValidationError("No quedó ninguna fila válida después de la validación")

    return df, warnings
