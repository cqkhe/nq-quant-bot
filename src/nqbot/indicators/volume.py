"""Indicadores de volumen."""

from __future__ import annotations

import pandas as pd


def relative_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    """Volumen de la barra relativo a su media móvil trailing.

    > 1.0 significa volumen por encima del promedio reciente. Las primeras
    `window - 1` barras quedan NaN a propósito (sin historia suficiente).
    """
    avg = volume.rolling(window, min_periods=window).mean()
    return (volume / avg).rename("rel_volume")
