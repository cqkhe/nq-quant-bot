"""Estrategia base: pullback a valor (VWAP/EMA) con tendencia y volumen.

Objetivo: estrategia simple, medible y direccionalmente sensata para
VALIDAR el motor. No pretende tener edge definitivo; es la línea base
estadística sobre la que se iteran mejoras.

Setup LONG (short = espejo):
  1. Régimen:      close > EMA200, EMA13 > EMA25 > EMA55, close > VWAP sesión.
  2. Pullback:     en las últimas N barras el precio tocó EMA25 o VWAP.
  3. Reanudación:  la barra actual cierra alcista y por encima de la EMA13.
  4. Volumen:      volumen relativo >= umbral (participación real, no deriva).
  5. Stop técnico: mínimo de las últimas N barras - colchón de ticks.
  6. Target:       RR configurable sobre el riesgo real (desde el fill).

Contexto adicional expuesto (sin gatear señales todavía): swings confirmados
y PDH/PDL como zonas de liquidez, para futuras versiones con confluencia.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from ..backtesting.models import LONG, SHORT, Signal
from ..indicators import (
    ema,
    last_confirmed_level,
    prior_session_levels,
    relative_volume,
    session_vwap,
    swing_flags,
)
from .base import Strategy


class BaseVwapEmaStrategy(Strategy):
    name = "base_vwap_ema"

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {
            "ema_fast": 13,
            "ema_mid": 25,
            "ema_slow": 55,
            "ema_trend": 200,
            "vol_window": 20,
            "rel_volume_threshold": 1.05,
            "pullback_lookback": 10,
            "swing_k": 3,
            "rr": 2.0,
            "stop_buffer_ticks": 4,
        }

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        out = df.copy()
        close, low, high = out["close"], out["low"], out["high"]

        out["ema_fast"] = ema(close, p["ema_fast"])
        out["ema_mid"] = ema(close, p["ema_mid"])
        out["ema_slow"] = ema(close, p["ema_slow"])
        out["ema_trend"] = ema(close, p["ema_trend"])
        out["vwap"] = session_vwap(out)
        out["rel_volume"] = relative_volume(out["volume"], p["vol_window"])

        # Contexto de estructura/liquidez (confirmado, sin lookahead)
        k = p["swing_k"]
        sh, sl = swing_flags(high, low, k)
        out["swing_high_lvl"] = last_confirmed_level(high, sh, k)
        out["swing_low_lvl"] = last_confirmed_level(low, sl, k)
        out[["pdh", "pdl", "pdc"]] = prior_session_levels(out)

        n = p["pullback_lookback"]
        buffer = p["stop_buffer_ticks"] * self.contract.tick_size

        trend_long = (
            (close > out["ema_trend"])
            & (out["ema_fast"] > out["ema_mid"])
            & (out["ema_mid"] > out["ema_slow"])
            & (close > out["vwap"])
        )
        trend_short = (
            (close < out["ema_trend"])
            & (out["ema_fast"] < out["ema_mid"])
            & (out["ema_mid"] < out["ema_slow"])
            & (close < out["vwap"])
        )

        # ¿El precio visitó la zona de valor (EMA25 o VWAP) en las últimas N barras?
        pulled_long = ((low <= out["ema_mid"]) | (low <= out["vwap"])).rolling(n, min_periods=1).max().astype(bool)
        pulled_short = ((high >= out["ema_mid"]) | (high >= out["vwap"])).rolling(n, min_periods=1).max().astype(bool)

        resume_long = (close > out["ema_fast"]) & (close > out["open"])
        resume_short = (close < out["ema_fast"]) & (close < out["open"])

        vol_ok = out["rel_volume"] >= p["rel_volume_threshold"]

        out["long_setup"] = (trend_long & pulled_long & resume_long & vol_ok).fillna(False)
        out["short_setup"] = (trend_short & pulled_short & resume_short & vol_ok).fillna(False)

        # Stop técnico: extremo del pullback reciente + colchón
        out["stop_ref_long"] = low.rolling(n, min_periods=1).min() - buffer
        out["stop_ref_short"] = high.rolling(n, min_periods=1).max() + buffer
        return out

    def signal_for_bar(self, ts: datetime, row: pd.Series) -> Signal | None:
        p = self.params
        if row["long_setup"]:
            stop = self.contract.round_to_tick(float(row["stop_ref_long"]))
            if stop < row["close"]:
                return Signal(ts, LONG, stop, p["rr"], "pullback_valor_long")
        elif row["short_setup"]:
            stop = self.contract.round_to_tick(float(row["stop_ref_short"]))
            if stop > row["close"]:
                return Signal(ts, SHORT, stop, p["rr"], "pullback_valor_short")
        return None
