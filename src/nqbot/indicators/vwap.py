"""VWAP anclado por sesión.

Se resetea al inicio de cada sesión (agrupando por fecha del índice), que es
como lo usa un trader intradía de futuros. Usa precio típico (H+L+C)/3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP acumulado dentro de cada sesión. Requiere high/low/close/volume."""
    session = df.index.normalize()
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = (typical * df["volume"]).groupby(session).cumsum()
    vv = df["volume"].groupby(session).cumsum()
    vwap = pv / vv.replace(0.0, np.nan)  # sin volumen acumulado -> sin VWAP definido
    return vwap.rename("vwap")
