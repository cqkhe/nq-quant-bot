"""Modelos del Market Regime Engine (Quant Brain, Fase 3).

Enums de régimen, configuración de umbrales y snapshots por barra/trade.
Los umbrales por defecto son redondos y conservadores: NO están optimizados
contra ningún backtest (regla anti-curve-fitting del proyecto).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import pandas as pd


class VolatilityRegime(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"


class TrendRegime(str, Enum):
    LATERAL = "lateral"
    TENDENCIA_ALCISTA = "tendencia_alcista"
    TENDENCIA_BAJISTA = "tendencia_bajista"


class ExpansionRegime(str, Enum):
    COMPRESION = "compresion"
    NEUTRAL = "neutral"
    EXPANSION = "expansion"


class DirectionalBias(str, Enum):
    ALCISTA = "alcista"
    BAJISTA = "bajista"
    NEUTRAL = "neutral"


class TradeAlignment(str, Enum):
    A_FAVOR = "a_favor"
    EN_CONTRA = "en_contra"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class RegimeConfig:
    """Umbrales y ventanas del motor de régimen.

    La volatilidad se clasifica contra la historia PROPIA del instrumento:
    cuantiles del ATR mediano de las últimas `vol_lookback_sessions` sesiones
    COMPLETADAS (shift de una sesión: la sesión en curso nunca participa de
    su propio umbral). Eso mantiene la clasificación causal y adaptativa a
    la escala del precio.
    """

    atr_window: int = 20                 # barras del ATR previo
    vwap_slope_window: int = 10          # barras para pendiente de VWAP
    ema_trend_period: int = 200
    ema_slope_window: int = 30           # barras para pendiente de EMA200
    opening_range_minutes: int = 30
    structure_window: int = 15           # ventana HH/LL
    rel_volume_window: int = 20
    # volatilidad relativa a la historia reciente (causal)
    vol_lookback_sessions: int = 20
    vol_min_sessions: int = 10           # mínimo de sesiones previas para etiquetar
    vol_low_quantile: float = 0.33
    vol_high_quantile: float = 0.67
    # expansión del día vs rango inicial
    compression_max_ratio: float = 1.2   # rango acumulado <= 1.2x OR -> compresión
    expansion_min_ratio: float = 2.0     # rango acumulado >= 2.0x OR -> expansión


# Columnas que el motor agrega al DataFrame (contrato público)
FEATURE_COLUMNS = [
    "atr_prev", "range_so_far", "or_high", "or_low", "or_size",
    "expansion_ratio", "vwap", "vwap_slope", "ema200", "ema200_slope",
    "dist_vwap", "dist_ema200", "above_vwap", "above_ema200",
    "rel_volume", "making_hh", "making_ll",
]
LABEL_COLUMNS = ["vol_regime", "trend_regime", "expansion_regime", "directional_bias"]


@dataclass(frozen=True)
class RegimeFeatures:
    """Snapshot de features causales en una barra concreta."""

    time: datetime
    atr_prev: float | None
    range_so_far: float | None
    or_size: float | None
    expansion_ratio: float | None
    vwap_slope: float | None
    ema200_slope: float | None
    dist_vwap: float | None
    dist_ema200: float | None
    above_vwap: bool | None
    above_ema200: bool | None
    rel_volume: float | None
    making_hh: bool | None
    making_ll: bool | None

    @classmethod
    def from_row(cls, time: datetime, row: pd.Series) -> "RegimeFeatures":
        def get(col):
            value = row.get(col)
            return None if pd.isna(value) else value

        return cls(
            time=time,
            atr_prev=get("atr_prev"), range_so_far=get("range_so_far"),
            or_size=get("or_size"), expansion_ratio=get("expansion_ratio"),
            vwap_slope=get("vwap_slope"), ema200_slope=get("ema200_slope"),
            dist_vwap=get("dist_vwap"), dist_ema200=get("dist_ema200"),
            above_vwap=get("above_vwap"), above_ema200=get("above_ema200"),
            rel_volume=get("rel_volume"),
            making_hh=get("making_hh"), making_ll=get("making_ll"),
        )


@dataclass(frozen=True)
class RegimeLabel:
    """Etiquetas de régimen en una barra concreta (None = no clasificable
    todavía: warmup, OR incompleto o historia insuficiente)."""

    time: datetime
    volatility: VolatilityRegime | None
    trend: TrendRegime | None
    expansion: ExpansionRegime | None
    bias: DirectionalBias | None

    @classmethod
    def from_row(cls, time: datetime, row: pd.Series) -> "RegimeLabel":
        def parse(col, enum_cls):
            value = row.get(col)
            return None if value is None or pd.isna(value) else enum_cls(value)

        return cls(
            time=time,
            volatility=parse("vol_regime", VolatilityRegime),
            trend=parse("trend_regime", TrendRegime),
            expansion=parse("expansion_regime", ExpansionRegime),
            bias=parse("directional_bias", DirectionalBias),
        )
