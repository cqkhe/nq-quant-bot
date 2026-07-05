"""Clasificador de régimen: convierte features causales en etiquetas.

Reglas simples, explicables y configurables (RegimeConfig). Ninguna etiqueta
usa información futura:

  * Volatilidad: ATR previo de la barra vs cuantiles del ATR mediano de las
    últimas N sesiones COMPLETADAS (shift de una sesión). Adaptativo a la
    escala del precio y 100% causal — jamás terciles del dataset completo,
    porque eso usaría la distribución futura.
  * Tendencia: posición vs EMA200 y VWAP + pendiente de EMA200.
  * Expansión: rango acumulado del día vs rango inicial (ratio).
  * Sesgo direccional: cierre vs VWAP y vs apertura del día.

Etiqueta None/NaN = "no clasificable todavía" (warmup, OR incompleto,
historia insuficiente): un consumidor honesto la trata como desconocida,
no la rellena.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import compute_regime_features
from .models import (
    LABEL_COLUMNS,
    DirectionalBias,
    ExpansionRegime,
    RegimeConfig,
    TradeAlignment,
    TrendRegime,
    VolatilityRegime,
)


def classify_regimes(df: pd.DataFrame, config: RegimeConfig | None = None) -> pd.DataFrame:
    """Features + etiquetas de régimen por barra. Devuelve un DataFrame nuevo."""
    cfg = config or RegimeConfig()
    out = compute_regime_features(df, cfg)
    out["vol_regime"] = _volatility_labels(out, cfg)
    out["trend_regime"] = _trend_labels(out)
    out["expansion_regime"] = _expansion_labels(out, cfg)
    out["directional_bias"] = _bias_labels(out)
    return out


# ------------------------------------------------------------------ etiquetas
def _volatility_labels(feats: pd.DataFrame, cfg: RegimeConfig) -> pd.Series:
    session = feats.index.normalize()
    atr_median_by_session = feats["atr_prev"].groupby(session).median()
    rolling = atr_median_by_session.rolling(
        cfg.vol_lookback_sessions, min_periods=cfg.vol_min_sessions
    )
    # shift(1): la sesión en curso NUNCA participa de su propio umbral
    q_low = rolling.quantile(cfg.vol_low_quantile).shift(1)
    q_high = rolling.quantile(cfg.vol_high_quantile).shift(1)

    low_thr = pd.Series(q_low.reindex(session).to_numpy(), index=feats.index)
    high_thr = pd.Series(q_high.reindex(session).to_numpy(), index=feats.index)
    atr = feats["atr_prev"]

    evaluable = atr.notna() & low_thr.notna() & high_thr.notna()
    labels = np.select(
        [evaluable & (atr <= low_thr), evaluable & (atr >= high_thr), evaluable],
        [VolatilityRegime.BAJA.value, VolatilityRegime.ALTA.value,
         VolatilityRegime.MEDIA.value],
        default=None,
    )
    return pd.Series(labels, index=feats.index, dtype="object")


def _trend_labels(feats: pd.DataFrame) -> pd.Series:
    c = feats["close"]
    evaluable = feats["ema200_slope"].notna() & feats["vwap"].notna()
    up = evaluable & (c > feats["ema200"]) & (feats["ema200_slope"] > 0) & (c > feats["vwap"])
    down = evaluable & (c < feats["ema200"]) & (feats["ema200_slope"] < 0) & (c < feats["vwap"])
    labels = np.select(
        [up, down, evaluable],
        [TrendRegime.TENDENCIA_ALCISTA.value, TrendRegime.TENDENCIA_BAJISTA.value,
         TrendRegime.LATERAL.value],
        default=None,
    )
    return pd.Series(labels, index=feats.index, dtype="object")


def _expansion_labels(feats: pd.DataFrame, cfg: RegimeConfig) -> pd.Series:
    ratio = feats["expansion_ratio"]
    evaluable = ratio.notna()
    labels = np.select(
        [evaluable & (ratio <= cfg.compression_max_ratio),
         evaluable & (ratio >= cfg.expansion_min_ratio),
         evaluable],
        [ExpansionRegime.COMPRESION.value, ExpansionRegime.EXPANSION.value,
         ExpansionRegime.NEUTRAL.value],
        default=None,
    )
    return pd.Series(labels, index=feats.index, dtype="object")


def _bias_labels(feats: pd.DataFrame) -> pd.Series:
    c = feats["close"]
    evaluable = feats["vwap"].notna() & feats["day_open"].notna()
    up = evaluable & (c > feats["vwap"]) & (c > feats["day_open"])
    down = evaluable & (c < feats["vwap"]) & (c < feats["day_open"])
    labels = np.select(
        [up, down, evaluable],
        [DirectionalBias.ALCISTA.value, DirectionalBias.BAJISTA.value,
         DirectionalBias.NEUTRAL.value],
        default=None,
    )
    return pd.Series(labels, index=feats.index, dtype="object")


# ------------------------------------------------------------------ trades
def trade_alignment(direction: int, bias: DirectionalBias | str | None) -> TradeAlignment:
    """¿El trade va a favor o contra el sesgo direccional del régimen?

    `direction`: +1 long, -1 short. Sesgo None o neutral -> NEUTRAL.
    """
    if bias is None or (isinstance(bias, float) and pd.isna(bias)):
        return TradeAlignment.NEUTRAL
    bias_value = bias.value if isinstance(bias, DirectionalBias) else str(bias)
    if bias_value == DirectionalBias.NEUTRAL.value:
        return TradeAlignment.NEUTRAL
    is_bullish_bias = bias_value == DirectionalBias.ALCISTA.value
    if (direction > 0) == is_bullish_bias:
        return TradeAlignment.A_FAVOR
    return TradeAlignment.EN_CONTRA


def label_trades(trades: pd.DataFrame, labeled_bars: pd.DataFrame) -> pd.DataFrame:
    """Une cada trade con el régimen vigente en su barra de señal.

    `trades` requiere columnas entry_time y direction; la barra de señal es
    entry_time - 1 min (la señal se genera al cierre de la barra anterior al
    fill). Agrega las 4 etiquetas + trade_vs_bias.
    """
    out = trades.copy()
    signal_times = pd.to_datetime(out["entry_time"]) - pd.Timedelta(minutes=1)
    joined = labeled_bars[LABEL_COLUMNS].reindex(signal_times)
    joined.index = out.index
    out = pd.concat([out, joined], axis=1)
    out["trade_vs_bias"] = [
        trade_alignment(direction, bias).value
        for direction, bias in zip(out["direction"], out["directional_bias"])
    ]
    return out
