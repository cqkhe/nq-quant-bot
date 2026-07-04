"""Variantes EXPERIMENTALES de daytrading_vwap_liquidity_rr2.

Origen: el análisis post-backtest de dic-2025→jun-2026 mostró que los longs
explican casi todo el PnL, que 10:00-10:59 concentra el beneficio y que
11:00-12:59 fue consistentemente negativo. Estas variantes aíslan cada uno
de esos filtros para medir si aportan robustez o solo reducen trades.

ADVERTENCIA METODOLÓGICA: los filtros se derivaron de ESE mismo dataset.
Cualquier mejora sobre esos datos es en parte esperable por construcción
(sesgo de selección). El veredicto real requiere datos fuera de muestra.

Diseño: cada variante hereda TODO el setup de la estrategia original y solo
filtra sus señales por lado y/u horario (sobre la hora de la barra de señal;
el fill ocurre en el open del minuto siguiente). La lógica base no se toca.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from ..backtesting.models import Signal
from ..config.settings import _parse_time
from .daytrading_vwap_liquidity_rr2 import DaytradingVwapLiquidityRR2


class FilteredDaytradingRR2(DaytradingVwapLiquidityRR2):
    """Base de variantes: filtros declarativos sobre las señales originales.

    Parámetros adicionales (defaults neutros = comportamiento original):
      allow_long / allow_short:  habilitan cada lado.
      blocked_entry_windows:     [["11:00","13:00"]] bloquea señales en 11:00-12:59.
      allowed_entry_windows:     si no está vacío, SOLO se aceptan señales
                                 dentro de alguna de estas ventanas.
    """

    name = "abstract_filtered_rr2"

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {
            **super().default_params(),
            "allow_long": True,
            "allow_short": True,
            "blocked_entry_windows": [],
            "allowed_entry_windows": [],
        }

    def __init__(self, params: dict[str, Any] | None, contract) -> None:
        super().__init__(params, contract)
        self._blocked = [
            (_parse_time(a), _parse_time(b)) for a, b in self.params["blocked_entry_windows"]
        ]
        self._allowed = [
            (_parse_time(a), _parse_time(b)) for a, b in self.params["allowed_entry_windows"]
        ]

    def signal_for_bar(self, ts: datetime, row: pd.Series) -> Signal | None:
        signal = super().signal_for_bar(ts, row)
        if signal is None:
            return None
        if signal.direction > 0 and not self.params["allow_long"]:
            return None
        if signal.direction < 0 and not self.params["allow_short"]:
            return None
        t = ts.time()
        if any(start <= t < end for start, end in self._blocked):
            return None
        if self._allowed and not any(start <= t < end for start, end in self._allowed):
            return None
        return signal


class NoMiddayRR2(FilteredDaytradingRR2):
    """Variante A: sin entradas nuevas entre 11:00 y 12:59 (chop de mediodía)."""

    name = "daytrading_vwap_liquidity_rr2_no_midday"

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {**super().default_params(), "blocked_entry_windows": [["11:00", "13:00"]]}


class LongsOnlyRR2(FilteredDaytradingRR2):
    """Variante B: solo operaciones LONG."""

    name = "daytrading_vwap_liquidity_rr2_longs_only"

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {**super().default_params(), "allow_short": False}


class MorningOnlyRR2(FilteredDaytradingRR2):
    """Variante C: solo entradas entre 10:00 y 10:59."""

    name = "daytrading_vwap_liquidity_rr2_morning_only"

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {**super().default_params(), "allowed_entry_windows": [["10:00", "11:00"]]}


class NoMiddayLongsOnlyRR2(FilteredDaytradingRR2):
    """Variante D: sin mediodía (11:00-12:59) y solo LONG."""

    name = "daytrading_vwap_liquidity_rr2_no_midday_longs_only"

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {
            **super().default_params(),
            "blocked_entry_windows": [["11:00", "13:00"]],
            "allow_short": False,
        }


class NoMiddayAtrFilterRR2(NoMiddayRR2):
    """Variante atr_filter: no_midday + filtro de cinta muerta por ATR previo.

    Origen: el diagnóstico de régimen mostró que el edge vive en días con
    volatilidad/tendencia y que el ÚNICO proxy causal cuyo ordenamiento
    replicó en ambos datasets fue el ATR-20 previo a la señal (tercil bajo
    = peor bucket en 2025 Y en el dataset completo, sin flip de signo).

    Cambio ÚNICO respecto de no_midday: si el ATR-20 (media de true range de
    las últimas 20 barras, calculado SOLO con información hasta la barra de
    señal) está por debajo de `min_atr20_points`, el setup se descarta.
    Umbral 8.0: redondo y conservador — el borde del tercil "malo" del
    diagnóstico fue ~10 pts; se elige deliberadamente por debajo para no
    sentarse en el óptimo in-sample. Misma lógica de entrada, mismo RR,
    mismos stops, mismos horarios, mismo risk manager.

    ADVERTENCIA: la hipótesis salió de los datasets 2025 y 2025-2026; su
    validación real requiere datos no usados (2024 o jul-2026+).
    """

    name = "daytrading_vwap_liquidity_rr2_no_midday_atr_filter"

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {**super().default_params(), "min_atr20_points": 8.0}

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        out = super().prepare(df)
        session = out.index.normalize()
        prev_close = out["close"].groupby(session).shift(1)
        true_range = pd.concat(
            [out["high"] - out["low"],
             (out["high"] - prev_close).abs(),
             (out["low"] - prev_close).abs()],
            axis=1,
        ).max(axis=1).fillna(out["high"] - out["low"])
        out["atr20"] = true_range.rolling(20, min_periods=20).mean()

        atr_ok = (out["atr20"] >= self.params["min_atr20_points"]).fillna(False)
        out["long_setup"] = out["long_setup"] & atr_ok
        out["short_setup"] = out["short_setup"] & atr_ok
        return out


class NoMiddayNearVwapRR2(NoMiddayRR2):
    """Variante near_vwap: no_midday + entrada CERCA del VWAP.

    Origen: el diagnóstico de edge sobre el OOS 2025 mostró pérdidas
    concentradas en entradas lejos del VWAP (>40 pts: expR -0.27) y ganancia
    en entradas cercanas (<24 pts: expR +0.21), con efecto monotónico. Una
    estrategia de pullback A VALOR que entra lejos del valor contradice su
    propia tesis; este filtro la obliga a cumplirla.

    Cambio ÚNICO respecto de no_midday: la distancia máxima al VWAP pasa de
    60 a `max_vwap_distance_points_near` (default 30.0 — umbral redondo y
    conservador, deliberadamente NO el borde óptimo del diagnóstico, para
    minimizar curve fitting). Misma lógica de entrada, mismo RR, mismos
    stops, mismos horarios, mismo risk manager.

    ADVERTENCIA: la hipótesis salió del dataset 2025; su validación real
    requiere datos no usados (2024 o jul-2026 en adelante).
    """

    name = "daytrading_vwap_liquidity_rr2_no_midday_near_vwap"

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {**super().default_params(), "max_vwap_distance_points_near": 30.0}

    def __init__(self, params: dict[str, Any] | None, contract) -> None:
        super().__init__(params, contract)
        # Único cambio: la cota existente de distancia al VWAP (que prepare()
        # ya aplica en vwap_ok_long/short) toma el valor "near".
        self.params["max_vwap_distance_points"] = self.params["max_vwap_distance_points_near"]
