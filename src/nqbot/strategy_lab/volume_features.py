"""Features de volumen OHLCV para investigacion.

Estas utilidades usan solo volumen de velas y calculan estadisticas rolling con
``shift(1)`` para evitar lookahead. No representan order flow, delta bid/ask ni
volumen por precio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_volume_mean(volume: pd.Series, window: int) -> pd.Series:
    """Media movil de volumen usando solo barras anteriores."""

    _validate_window(window)
    shifted = _volume_series(volume).shift(1)
    return shifted.rolling(window=window, min_periods=window).mean()


def rolling_volume_std(volume: pd.Series, window: int) -> pd.Series:
    """Desviacion estandar movil de volumen usando solo barras anteriores."""

    _validate_window(window)
    shifted = _volume_series(volume).shift(1)
    return shifted.rolling(window=window, min_periods=window).std(ddof=0)


def relative_volume(volume: pd.Series, window: int) -> pd.Series:
    """Volumen actual dividido por la media movil previa."""

    vol = _volume_series(volume)
    mean = rolling_volume_mean(vol, window)
    mean = mean.mask(mean == 0.0)
    return (vol / mean).replace([np.inf, -np.inf], np.nan)


def volume_zscore(volume: pd.Series, window: int) -> pd.Series:
    """Z-score de volumen con media/std calculadas sin incluir la barra actual."""

    vol = _volume_series(volume)
    mean = rolling_volume_mean(vol, window)
    std = rolling_volume_std(vol, window)
    std = std.mask(std == 0.0)
    return ((vol - mean) / std).replace([np.inf, -np.inf], np.nan)


def classify_volume_zscore(zscore: pd.Series) -> pd.Series:
    """Clasifica z-score de volumen en buckets conservadores."""

    z = pd.to_numeric(zscore, errors="coerce")
    labels = pd.Series("normal", index=zscore.index, dtype="object")
    labels[z.isna()] = "unknown"
    labels[z < -1.0] = "low"
    labels[z > 1.5] = "high"
    labels[z > 2.0] = "extreme"
    labels[z > 2.5] = "climax"
    return labels


def classify_volume(volume: pd.Series, window: int) -> pd.Series:
    """Clasifica volumen OHLCV usando z-score sin lookahead."""

    return classify_volume_zscore(volume_zscore(volume, window))


def is_volume_dry_up(zscore: pd.Series, threshold: float = -1.0) -> pd.Series:
    """Detecta volumen seco segun z-score."""

    return pd.to_numeric(zscore, errors="coerce").le(threshold).fillna(False)


def is_volume_spike(zscore: pd.Series, threshold: float = 1.5) -> pd.Series:
    """Detecta spike de volumen segun z-score."""

    return pd.to_numeric(zscore, errors="coerce").ge(threshold).fillna(False)


def is_volume_climax(zscore: pd.Series, threshold: float = 2.5) -> pd.Series:
    """Detecta posible climax de volumen segun z-score."""

    return pd.to_numeric(zscore, errors="coerce").ge(threshold).fillna(False)


def _volume_series(volume: pd.Series) -> pd.Series:
    return pd.to_numeric(volume, errors="coerce").astype("float64")


def _validate_window(window: int) -> None:
    if window <= 1:
        raise ValueError("window debe ser > 1")


__all__ = [
    "classify_volume",
    "classify_volume_zscore",
    "is_volume_climax",
    "is_volume_dry_up",
    "is_volume_spike",
    "relative_volume",
    "rolling_volume_mean",
    "rolling_volume_std",
    "volume_zscore",
]
