"""Medias móviles."""

from __future__ import annotations

import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    """EMA estándar (adjust=False: recursiva, como la calculan las plataformas)."""
    if period < 1:
        raise ValueError(f"Período de EMA inválido: {period}")
    return series.ewm(span=period, adjust=False).mean()
