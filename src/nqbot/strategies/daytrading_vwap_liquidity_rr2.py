"""Estrategia intradía: daytrading_vwap_liquidity_rr2.

Day trading puro sobre MNQ/NQ en sesión regular (RTH), RR fijo 2:1.
Base: price action + VWAP + EMAs + liquidez + volumen + estructura intradía.
Sin conceptos ICT; solo niveles observables y reglas medibles.

Setup LONG (short = espejo exacto):
  Régimen
    R1. close > EMA200 (lado correcto del mercado).
    R2. EMA13 > EMA25 > EMA55 y EMA55 con pendiente mínima configurable
        (EMAs planas o mezcladas = no operar).
    R3. close > VWAP de sesión, pero a menos de `max_vwap_distance_points`
        (operar cerca del valor, no perseguir precio extendido).
  Estructura intradía
    R4. El rango inicial (`opening_range_minutes`) ya cerró: sin señales
        mientras se forma. El precio debe estar por encima de su punto medio
        (del lado comprador de la liquidez de apertura).
  Gatillo
    R5. Pullback a la zona de valor (VWAP o EMA25) en las últimas
        `pullback_lookback` barras.
    R6. Barra de rechazo alcista: cierra alcista, sobre la EMA13 y en el
        tramo superior de su rango (`rejection_close_pct`).
    R7. Volumen relativo >= `rel_volume_threshold` (participación real).
  Riesgo
    R8. Stop técnico: debajo del mínimo del pullback y del último swing low
        INTRADÍA confirmado (swings de sesiones anteriores no cuentan),
        menos `stop_buffer_ticks`.
    R9. La distancia al stop debe caer en [min_stop_points, max_stop_points]:
        stop demasiado chico = ruido; demasiado grande = setup inválido.
    R10. Take profit = `rr` (default 2.0) veces la distancia al stop, siempre,
        calculado por el motor sobre el precio de fill real.

Además: sin señales en los primeros `skip_open_minutes`; los horarios de
entrada/cutoff/flatten y los límites diarios (trades, pérdida, rachas) los
imponen SessionConfig y el RiskManager — esta clase solo emite señales.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from ..backtesting.models import LONG, SHORT, Signal
from ..indicators import (
    ema,
    last_confirmed_level,
    relative_volume,
    session_vwap,
    swing_flags,
)
from .base import Strategy


class DaytradingVwapLiquidityRR2(Strategy):
    name = "daytrading_vwap_liquidity_rr2"

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {
            "rr": 2.0,                       # TP = 2x riesgo, regla central
            "ema_fast": 13,
            "ema_mid": 25,
            "ema_slow": 55,
            "ema_trend": 200,
            "vol_window": 20,
            "rel_volume_threshold": 1.10,
            "pullback_lookback": 8,
            "swing_k": 3,
            "opening_range_minutes": 30,
            "skip_open_minutes": 5,
            "rejection_close_pct": 0.60,
            "max_vwap_distance_points": 60.0,
            "min_stop_points": 8.0,
            "max_stop_points": 60.0,
            "slope_lookback": 10,
            "min_slope_points": 2.0,
            "stop_buffer_ticks": 4,
        }

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        out = df.copy()
        o, h, l, c = out["open"], out["high"], out["low"], out["close"]
        session = out.index.normalize()

        # ---------------- indicadores base
        out["ema_fast"] = ema(c, p["ema_fast"])
        out["ema_mid"] = ema(c, p["ema_mid"])
        out["ema_slow"] = ema(c, p["ema_slow"])
        out["ema_trend"] = ema(c, p["ema_trend"])
        out["vwap"] = session_vwap(out)
        out["rel_volume"] = relative_volume(out["volume"], p["vol_window"])

        # ---------------- reloj de sesión (relativo a la primera barra del día)
        ts = pd.Series(out.index, index=out.index)
        session_open = ts.groupby(session).transform("min")
        elapsed_min = (ts - session_open).dt.total_seconds() / 60.0
        tradeable = (elapsed_min >= p["skip_open_minutes"]) & (
            elapsed_min >= p["opening_range_minutes"]
        )

        # ---------------- rango inicial (liquidez de apertura)
        in_or = elapsed_min < p["opening_range_minutes"]
        out["or_high"] = h.where(in_or).groupby(session).cummax().groupby(session).ffill()
        out["or_low"] = l.where(in_or).groupby(session).cummin().groupby(session).ffill()
        out["or_mid"] = (out["or_high"] + out["or_low"]) / 2.0

        # ---------------- swings intradía confirmados (sin lookahead)
        k = p["swing_k"]
        sh_flags, sl_flags = swing_flags(h, l, k)
        sess_code = pd.Series(pd.factorize(session)[0], index=out.index, dtype="float64")
        swing_low = last_confirmed_level(l, sl_flags, k)
        swing_high = last_confirmed_level(h, sh_flags, k)
        # solo cuentan los swings formados en la sesión ACTUAL
        out["intraday_swing_low"] = swing_low.where(
            last_confirmed_level(sess_code, sl_flags, k) == sess_code
        )
        out["intraday_swing_high"] = swing_high.where(
            last_confirmed_level(sess_code, sh_flags, k) == sess_code
        )

        # ---------------- R1-R2: régimen y pendiente (EMAs planas = fuera)
        slope = out["ema_slow"].diff(p["slope_lookback"])
        trend_long = (
            (c > out["ema_trend"])
            & (out["ema_fast"] > out["ema_mid"])
            & (out["ema_mid"] > out["ema_slow"])
            & (slope >= p["min_slope_points"])
        )
        trend_short = (
            (c < out["ema_trend"])
            & (out["ema_fast"] < out["ema_mid"])
            & (out["ema_mid"] < out["ema_slow"])
            & (slope <= -p["min_slope_points"])
        )

        # ---------------- R3: lado del VWAP y distancia máxima al valor
        max_d = p["max_vwap_distance_points"]
        vwap_ok_long = (c > out["vwap"]) & (c - out["vwap"] <= max_d)
        vwap_ok_short = (c < out["vwap"]) & (out["vwap"] - c <= max_d)

        # ---------------- R5: pullback a la zona de valor
        n = p["pullback_lookback"]
        pulled_long = ((l <= out["ema_mid"]) | (l <= out["vwap"])).rolling(n, min_periods=1).max().astype(bool)
        pulled_short = ((h >= out["ema_mid"]) | (h >= out["vwap"])).rolling(n, min_periods=1).max().astype(bool)

        # ---------------- R6: barra de rechazo (price action)
        bar_range = (h - l).replace(0.0, np.nan)
        close_pos_long = ((c - l) / bar_range).fillna(0.0)   # 1.0 = cierre en el máximo
        close_pos_short = ((h - c) / bar_range).fillna(0.0)  # 1.0 = cierre en el mínimo
        reject_long = (c > o) & (c > out["ema_fast"]) & (close_pos_long >= p["rejection_close_pct"])
        reject_short = (c < o) & (c < out["ema_fast"]) & (close_pos_short >= p["rejection_close_pct"])

        # ---------------- R7: volumen
        vol_ok = out["rel_volume"] >= p["rel_volume_threshold"]

        # ---------------- R8: stop técnico intradía
        buffer = p["stop_buffer_ticks"] * self.contract.tick_size
        roll_low = l.rolling(n, min_periods=1).min()
        roll_high = h.rolling(n, min_periods=1).max()
        out["stop_ref_long"] = np.minimum(
            roll_low, out["intraday_swing_low"].fillna(np.inf)
        ) - buffer
        out["stop_ref_short"] = np.maximum(
            roll_high, out["intraday_swing_high"].fillna(-np.inf)
        ) + buffer

        # ---------------- R9: tamaño del stop dentro del rango permitido
        dist_long = c - out["stop_ref_long"]
        dist_short = out["stop_ref_short"] - c
        size_ok_long = (dist_long >= p["min_stop_points"]) & (dist_long <= p["max_stop_points"])
        size_ok_short = (dist_short >= p["min_stop_points"]) & (dist_short <= p["max_stop_points"])

        # ---------------- setup completo
        out["long_setup"] = (
            tradeable & trend_long & vwap_ok_long & (c > out["or_mid"])
            & pulled_long & reject_long & vol_ok & size_ok_long
        ).fillna(False)
        out["short_setup"] = (
            tradeable & trend_short & vwap_ok_short & (c < out["or_mid"])
            & pulled_short & reject_short & vol_ok & size_ok_short
        ).fillna(False)
        return out

    def signal_for_bar(self, ts: datetime, row: pd.Series) -> Signal | None:
        p = self.params
        if row["long_setup"]:
            stop = self.contract.round_to_tick(float(row["stop_ref_long"]))
            if stop < row["close"]:
                return Signal(ts, LONG, stop, p["rr"], "vwap_liq_rejection_long")
        elif row["short_setup"]:
            stop = self.contract.round_to_tick(float(row["stop_ref_short"]))
            if stop > row["close"]:
                return Signal(ts, SHORT, stop, p["rr"], "vwap_liq_rejection_short")
        return None
