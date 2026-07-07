"""OHLCV volume research strategies.

These strategies use only 1m OHLCV bars. Volume features are imported from the
Strategy Lab module and are calculated with past-only rolling statistics. They
do not use bid/ask, delta, footprint, DOM, market depth, or real order flow.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from ..backtesting.models import LONG, SHORT, Signal
from ..indicators import ema, session_vwap
from ..strategy_lab.volume_features import (
    classify_volume_zscore,
    is_volume_dry_up,
    relative_volume,
    volume_zscore,
)
from .base import Strategy


class OhlcvVolumeStrategy(Strategy):
    """Base class for conservative OHLCV volume hypotheses."""

    name = "abstract_ohlcv_volume"
    mode = "abstract"
    param_overrides: dict[str, Any] = {}

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        base = {
            "rr": 1.5,
            "ema_fast": 13,
            "ema_mid": 25,
            "ema_slow": 55,
            "volume_window": 20,
            "rel_volume_threshold": 1.5,
            "spike_threshold": 2.0,
            "dry_up_threshold": 0.8,
            "volume_zscore_threshold": 2.0,
            "dry_up_zscore_threshold": -0.8,
            "dry_up_lookback": 8,
            "breakout_lookback": 20,
            "opening_range_minutes": 15,
            "skip_open_minutes": 5,
            "reclaim_lookback": 3,
            "rejection_close_pct": 0.60,
            "max_vwap_distance_points": 60.0,
            "min_vwap_extension_points": 5.0,
            "min_stop_points": 4.0,
            "max_stop_points": 60.0,
            "stop_lookback": 8,
            "stop_buffer_ticks": 4,
            "breakout_buffer_ticks": 0,
        }
        return {**base, **cls.param_overrides}

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        out = df.copy()
        o, h, l, c = out["open"], out["high"], out["low"], out["close"]
        session = out.index.normalize()

        out["ema_fast"] = ema(c, p["ema_fast"])
        out["ema_mid"] = ema(c, p["ema_mid"])
        out["ema_slow"] = ema(c, p["ema_slow"])
        out["vwap"] = session_vwap(out)
        out["rel_volume"] = relative_volume(out["volume"], int(p["volume_window"]))
        out["volume_zscore"] = volume_zscore(out["volume"], int(p["volume_window"]))
        out["volume_bucket"] = classify_volume_zscore(out["volume_zscore"])

        ts = pd.Series(out.index, index=out.index)
        session_open = ts.groupby(session).transform("min")
        elapsed_min = (ts - session_open).dt.total_seconds() / 60.0
        out["elapsed_min"] = elapsed_min
        tradeable = elapsed_min >= max(p["skip_open_minutes"], p["opening_range_minutes"])

        in_or = elapsed_min < p["opening_range_minutes"]
        out["or_high"] = h.where(in_or).groupby(session).cummax().groupby(session).ffill()
        out["or_low"] = l.where(in_or).groupby(session).cummin().groupby(session).ffill()

        out["breakout_high"] = _session_shifted_rolling(h, session, p["breakout_lookback"], "max")
        out["breakout_low"] = _session_shifted_rolling(l, session, p["breakout_lookback"], "min")
        out["prev_close"] = c.groupby(session).shift(1)
        out["prev_vwap"] = out["vwap"].groupby(session).shift(1)

        dry_rel = (out["rel_volume"] <= p["dry_up_threshold"]).fillna(False)
        dry_z = is_volume_dry_up(out["volume_zscore"], p["dry_up_zscore_threshold"])
        out["dry_up_recent"] = _past_bool_window(dry_rel, session, p["dry_up_lookback"])
        out["gaussian_dry_up_recent"] = _past_bool_window(dry_z, session, p["dry_up_lookback"])

        stop_buffer = p["stop_buffer_ticks"] * self.contract.tick_size
        out["stop_ref_long"] = (
            l.groupby(session)
            .transform(lambda s: s.rolling(p["stop_lookback"], min_periods=1).min())
            - stop_buffer
        )
        out["stop_ref_short"] = (
            h.groupby(session)
            .transform(lambda s: s.rolling(p["stop_lookback"], min_periods=1).max())
            + stop_buffer
        )

        bar_range = (h - l).replace(0.0, np.nan)
        close_pos_long = ((c - l) / bar_range).fillna(0.0)
        close_pos_short = ((h - c) / bar_range).fillna(0.0)
        bullish_rejection = (c > o) & (close_pos_long >= p["rejection_close_pct"])
        bearish_rejection = (c < o) & (close_pos_short >= p["rejection_close_pct"])

        rel_ok = out["rel_volume"] >= p["rel_volume_threshold"]
        rel_spike = out["rel_volume"] >= p["spike_threshold"]
        z_ok = out["volume_zscore"] >= p["volume_zscore_threshold"]

        breakout_buffer = p["breakout_buffer_ticks"] * self.contract.tick_size
        prior_breakout_long = c > (out["breakout_high"] + breakout_buffer)
        prior_breakout_short = c < (out["breakout_low"] - breakout_buffer)
        or_breakout_long = c > (out["or_high"] + breakout_buffer)
        or_breakout_short = c < (out["or_low"] - breakout_buffer)
        vwap_distance = (c - out["vwap"]).abs()

        mode = self.mode
        if mode == "relative_volume_breakout":
            long_setup = tradeable & prior_breakout_long & rel_ok
            short_setup = tradeable & prior_breakout_short & rel_ok
        elif mode == "opening_range_volume_breakout":
            long_setup = tradeable & or_breakout_long & rel_ok
            short_setup = tradeable & or_breakout_short & rel_ok
        elif mode == "gaussian_volume_breakout":
            long_setup = tradeable & prior_breakout_long & z_ok
            short_setup = tradeable & prior_breakout_short & z_ok
        elif mode == "volume_dry_up_breakout":
            long_setup = tradeable & out["dry_up_recent"] & prior_breakout_long & rel_ok
            short_setup = tradeable & out["dry_up_recent"] & prior_breakout_short & rel_ok
        elif mode == "gaussian_volume_dry_up_breakout":
            long_setup = tradeable & out["gaussian_dry_up_recent"] & prior_breakout_long & z_ok
            short_setup = tradeable & out["gaussian_dry_up_recent"] & prior_breakout_short & z_ok
        elif mode == "vwap_volume_reclaim":
            near_vwap = vwap_distance <= p["max_vwap_distance_points"]
            long_setup = (
                tradeable
                & (out["prev_close"] < out["prev_vwap"])
                & (c > out["vwap"])
                & near_vwap
                & rel_ok
            )
            short_setup = (
                tradeable
                & (out["prev_close"] > out["prev_vwap"])
                & (c < out["vwap"])
                & near_vwap
                & rel_ok
            )
        elif mode == "volume_climax_reversal":
            long_setup, short_setup = self._reversal_setups(
                c, out["vwap"], tradeable, rel_spike, bullish_rejection, bearish_rejection
            )
        elif mode == "gaussian_volume_reversal":
            long_setup, short_setup = self._reversal_setups(
                c, out["vwap"], tradeable, z_ok, bullish_rejection, bearish_rejection
            )
        else:  # pragma: no cover - subclasses set concrete modes
            long_setup = pd.Series(False, index=out.index)
            short_setup = pd.Series(False, index=out.index)

        dist_long = c - out["stop_ref_long"]
        dist_short = out["stop_ref_short"] - c
        size_ok_long = (dist_long >= p["min_stop_points"]) & (dist_long <= p["max_stop_points"])
        size_ok_short = (dist_short >= p["min_stop_points"]) & (dist_short <= p["max_stop_points"])

        out["long_setup"] = (long_setup & size_ok_long).fillna(False)
        out["short_setup"] = (short_setup & size_ok_short).fillna(False)
        return out

    def signal_for_bar(self, ts: datetime, row: pd.Series) -> Signal | None:
        if row["long_setup"]:
            stop = self.contract.round_to_tick(float(row["stop_ref_long"]))
            if stop < row["close"]:
                return Signal(ts, LONG, stop, self.params["rr"], f"{self.name}_long")
        if row["short_setup"]:
            stop = self.contract.round_to_tick(float(row["stop_ref_short"]))
            if stop > row["close"]:
                return Signal(ts, SHORT, stop, self.params["rr"], f"{self.name}_short")
        return None

    def _reversal_setups(
        self,
        close: pd.Series,
        vwap: pd.Series,
        tradeable: pd.Series,
        volume_extreme: pd.Series,
        bullish_rejection: pd.Series,
        bearish_rejection: pd.Series,
    ) -> tuple[pd.Series, pd.Series]:
        min_extension = self.params["min_vwap_extension_points"]
        extended_below = (vwap - close) >= min_extension
        extended_above = (close - vwap) >= min_extension
        long_setup = tradeable & volume_extreme & extended_below & bullish_rejection
        short_setup = tradeable & volume_extreme & extended_above & bearish_rejection
        return long_setup, short_setup


class RelativeVolumeBreakout(OhlcvVolumeStrategy):
    name = "relative_volume_breakout"
    mode = "relative_volume_breakout"


class VolumeClimaxReversal(OhlcvVolumeStrategy):
    name = "volume_climax_reversal"
    mode = "volume_climax_reversal"
    param_overrides = {"rr": 1.5, "spike_threshold": 2.0, "rejection_close_pct": 0.60}


class VolumeDryUpBreakout(OhlcvVolumeStrategy):
    name = "volume_dry_up_breakout"
    mode = "volume_dry_up_breakout"
    param_overrides = {"dry_up_threshold": 0.8, "rel_volume_threshold": 1.5}


class OpeningRangeVolumeBreakout(OhlcvVolumeStrategy):
    name = "opening_range_volume_breakout"
    mode = "opening_range_volume_breakout"


class GaussianVolumeBreakout(OhlcvVolumeStrategy):
    name = "gaussian_volume_breakout"
    mode = "gaussian_volume_breakout"
    param_overrides = {"volume_zscore_threshold": 2.0}


class GaussianVolumeReversal(OhlcvVolumeStrategy):
    name = "gaussian_volume_reversal"
    mode = "gaussian_volume_reversal"
    param_overrides = {
        "rr": 1.5,
        "volume_zscore_threshold": 2.0,
        "rejection_close_pct": 0.60,
    }


class GaussianVolumeDryUpBreakout(OhlcvVolumeStrategy):
    name = "gaussian_volume_dry_up_breakout"
    mode = "gaussian_volume_dry_up_breakout"
    param_overrides = {
        "dry_up_zscore_threshold": -0.8,
        "volume_zscore_threshold": 2.0,
    }


class VwapVolumeReclaim(OhlcvVolumeStrategy):
    name = "vwap_volume_reclaim"
    mode = "vwap_volume_reclaim"
    param_overrides = {"max_vwap_distance_points": 40.0}


def _session_shifted_rolling(
    values: pd.Series,
    session: pd.Index,
    window: int,
    method: str,
) -> pd.Series:
    if window <= 1:
        raise ValueError("window debe ser > 1")
    grouped = values.groupby(session)
    if method == "max":
        return grouped.transform(lambda s: s.shift(1).rolling(window, min_periods=window).max())
    if method == "min":
        return grouped.transform(lambda s: s.shift(1).rolling(window, min_periods=window).min())
    raise ValueError(f"Metodo rolling desconocido: {method}")


def _past_bool_window(flags: pd.Series, session: pd.Index, window: int) -> pd.Series:
    if window <= 0:
        raise ValueError("window debe ser > 0")
    numeric = flags.astype(float)
    return (
        numeric.groupby(session)
        .transform(lambda s: s.shift(1).rolling(window, min_periods=1).max())
        .fillna(0.0)
        .astype(bool)
    )


__all__ = [
    "GaussianVolumeBreakout",
    "GaussianVolumeDryUpBreakout",
    "GaussianVolumeReversal",
    "OpeningRangeVolumeBreakout",
    "RelativeVolumeBreakout",
    "VolumeClimaxReversal",
    "VolumeDryUpBreakout",
    "VwapVolumeReclaim",
]
