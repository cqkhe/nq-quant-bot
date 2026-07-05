"""Features CAUSALES de régimen: solo información hasta la barra analizada.

Garantía anti-lookahead: cada valor en la barra t se calcula exclusivamente
con barras <= t (rolling, cumsum/cummax por sesión, diffs hacia atrás).
Propiedad verificable: clasificar un dataset truncado produce EXACTAMENTE
los mismos valores que clasificar el dataset completo, en el tramo común
(test de estabilidad de prefijo en tests/test_regime_engine.py).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicators import ema, relative_volume, session_vwap
from .models import RegimeConfig


def compute_regime_features(df: pd.DataFrame, config: RegimeConfig | None = None) -> pd.DataFrame:
    """Agrega las columnas de features de régimen a un OHLCV intradía.

    Espera un DataFrame con open/high/low/close/volume e índice datetime
    (una sesión = un día calendario, como produce el pipeline de datos).
    """
    cfg = config or RegimeConfig()
    out = df.copy()
    session = out.index.normalize()
    o, h, l, c = out["open"], out["high"], out["low"], out["close"]

    # ---- ATR previo (true range de las últimas N barras cerradas)
    prev_close = c.groupby(session).shift(1)
    true_range = pd.concat(
        [h - l, (h - prev_close).abs(), (l - prev_close).abs()], axis=1
    ).max(axis=1).fillna(h - l)
    out["atr_prev"] = true_range.rolling(cfg.atr_window, min_periods=cfg.atr_window).mean()

    # ---- rango acumulado del día hasta la barra actual
    out["range_so_far"] = h.groupby(session).cummax() - l.groupby(session).cummin()

    # ---- rango inicial (solo definido una vez COMPLETO; antes queda NaN)
    ts = pd.Series(out.index, index=out.index)
    session_open_ts = ts.groupby(session).transform("min")
    elapsed_min = (ts - session_open_ts).dt.total_seconds() / 60.0
    in_or = elapsed_min < cfg.opening_range_minutes
    or_complete = elapsed_min >= cfg.opening_range_minutes
    or_high = h.where(in_or).groupby(session).cummax().groupby(session).ffill()
    or_low = l.where(in_or).groupby(session).cummin().groupby(session).ffill()
    out["or_high"] = or_high.where(or_complete)
    out["or_low"] = or_low.where(or_complete)
    out["or_size"] = out["or_high"] - out["or_low"]
    out["expansion_ratio"] = out["range_so_far"] / out["or_size"].replace(0.0, np.nan)

    # ---- valor y tendencia de referencia
    out["vwap"] = session_vwap(out)
    out["vwap_slope"] = out["vwap"].diff(cfg.vwap_slope_window)
    out["ema200"] = ema(c, cfg.ema_trend_period)
    out["ema200_slope"] = out["ema200"].diff(cfg.ema_slope_window)
    out["dist_vwap"] = c - out["vwap"]
    out["dist_ema200"] = c - out["ema200"]
    out["above_vwap"] = c > out["vwap"]
    out["above_ema200"] = c > out["ema200"]

    # ---- participación
    out["rel_volume"] = relative_volume(out["volume"], cfg.rel_volume_window)

    # ---- estructura previa: la ventana actual de N barras vs la anterior
    w = cfg.structure_window
    rolling_high = h.rolling(w).max()
    rolling_low = l.rolling(w).min()
    out["making_hh"] = rolling_high > rolling_high.shift(w)
    out["making_ll"] = rolling_low < rolling_low.shift(w)

    # contexto de sesión para el sesgo direccional (causal: open del día)
    out["day_open"] = o.groupby(session).transform("first")
    return out
