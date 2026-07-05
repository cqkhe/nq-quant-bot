"""Tests del Market Regime Engine.

El test central es el de ESTABILIDAD DE PREFIJO: clasificar un dataset
truncado debe producir exactamente los mismos features y etiquetas que
clasificar el dataset completo, en el tramo común. Si algo mirara el
futuro (p.ej. terciles del dataset completo), ese test falla.
"""

import numpy as np
import pandas as pd
import pytest

from nqbot.regime import (
    FEATURE_COLUMNS,
    LABEL_COLUMNS,
    DirectionalBias,
    RegimeConfig,
    RegimeLabel,
    TradeAlignment,
    TrendRegime,
    classify_regimes,
    label_trades,
    trade_alignment,
)

FAST_CFG = RegimeConfig(
    atr_window=5, vwap_slope_window=5, ema_trend_period=50, ema_slope_window=10,
    structure_window=10, rel_volume_window=10,
    vol_lookback_sessions=3, vol_min_sessions=2,
)


def make_session(day: str, closes) -> pd.DataFrame:
    closes = np.asarray(closes, dtype=float)
    idx = pd.date_range(f"{day} 09:30", periods=len(closes), freq="1min")
    opens = np.concatenate([[closes[0]], closes[:-1]])
    return pd.DataFrame(
        {"open": opens, "high": np.maximum(opens, closes) + 0.5,
         "low": np.minimum(opens, closes) - 0.5, "close": closes, "volume": 1000.0},
        index=pd.DatetimeIndex(idx, name="datetime"),
    )


def random_walk_days(days: int, bars: int = 120, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames, price = [], 20_000.0
    for day in pd.bdate_range("2026-01-05", periods=days):
        closes = price + np.cumsum(rng.normal(0, 3.0, bars))
        frames.append(make_session(day.strftime("%Y-%m-%d"), closes))
        price = float(closes[-1])
    return pd.concat(frames)


# ---------------------------------------------------------------- anti-lookahead
def test_prefix_stability_no_lookahead():
    df = random_walk_days(days=5)
    full = classify_regimes(df, FAST_CFG)
    truncated = classify_regimes(df.iloc[:-137], FAST_CFG)  # corta a mitad de sesión

    cols = FEATURE_COLUMNS + LABEL_COLUMNS
    pd.testing.assert_frame_equal(
        full.iloc[: len(truncated)][cols], truncated[cols]
    )


def test_volatility_thresholds_never_use_current_session():
    """3 sesiones tranquilas + 1 ruidosa: la ruidosa debe salir 'alta' medida
    contra la historia PREVIA; la primera sesión no es clasificable."""
    quiet = 100 + np.tile([0.5, -0.5], 30)
    loud = 100 + np.tile([10.0, -10.0], 30)
    df = pd.concat([
        make_session("2026-01-05", quiet), make_session("2026-01-06", quiet),
        make_session("2026-01-07", quiet), make_session("2026-01-08", loud),
    ])
    labeled = classify_regimes(df, FAST_CFG)
    assert labeled["vol_regime"].iloc[10] is None            # día 1: sin historia
    assert labeled["vol_regime"].iloc[-1] == "alta"          # día ruidoso vs pasado quieto


# ---------------------------------------------------------------- features
def test_opening_range_and_expansion_ratio():
    closes = np.concatenate([100 + np.tile([2.0, -2.0], 15),   # OR: 30 barras, rango ~5
                             np.full(30, 101.0)])              # después: adentro del OR
    labeled = classify_regimes(make_session("2026-01-05", closes), FAST_CFG)
    assert pd.isna(labeled["or_size"].iloc[10])   # OR incompleto: no definido
    or_size = labeled["or_size"].iloc[-1]
    assert or_size == pytest.approx(labeled["range_so_far"].iloc[29], abs=1.0)
    assert labeled["expansion_regime"].iloc[-1] == "compresion"  # nunca salió del OR


def test_expansion_detected_when_day_leaves_opening_range():
    closes = np.concatenate([100 + np.tile([2.0, -2.0], 15),
                             np.linspace(102, 116, 30)])       # rompe a ~3x el OR
    labeled = classify_regimes(make_session("2026-01-05", closes), FAST_CFG)
    assert labeled["expansion_ratio"].iloc[-1] > 2.0
    assert labeled["expansion_regime"].iloc[-1] == "expansion"


# ---------------------------------------------------------------- etiquetas
def test_trend_labels_up_down_lateral():
    up = classify_regimes(make_session("2026-01-05", 100 + 0.5 * np.arange(200)), FAST_CFG)
    assert up["trend_regime"].iloc[-1] == TrendRegime.TENDENCIA_ALCISTA.value

    down = classify_regimes(make_session("2026-01-05", 300 - 0.5 * np.arange(200)), FAST_CFG)
    assert down["trend_regime"].iloc[-1] == TrendRegime.TENDENCIA_BAJISTA.value

    flat = classify_regimes(make_session("2026-01-05", np.full(200, 100.0)), FAST_CFG)
    assert flat["trend_regime"].iloc[-1] == TrendRegime.LATERAL.value


def test_directional_bias_follows_session_direction():
    up = classify_regimes(make_session("2026-01-05", 100 + 0.5 * np.arange(120)), FAST_CFG)
    assert up["directional_bias"].iloc[-1] == DirectionalBias.ALCISTA.value


# ---------------------------------------------------------------- trades
def test_trade_alignment_mapping():
    assert trade_alignment(+1, "alcista") == TradeAlignment.A_FAVOR
    assert trade_alignment(-1, "alcista") == TradeAlignment.EN_CONTRA
    assert trade_alignment(-1, DirectionalBias.BAJISTA) == TradeAlignment.A_FAVOR
    assert trade_alignment(+1, "neutral") == TradeAlignment.NEUTRAL
    assert trade_alignment(+1, None) == TradeAlignment.NEUTRAL


def test_label_trades_joins_signal_bar_regime():
    labeled = classify_regimes(make_session("2026-01-05", 100 + 0.5 * np.arange(120)), FAST_CFG)
    trades = pd.DataFrame({
        "entry_time": [labeled.index[60] + pd.Timedelta(minutes=1)],
        "direction": [-1],   # short contra un día alcista
    })
    joined = label_trades(trades, labeled)
    assert joined["directional_bias"].iloc[0] == "alcista"
    assert joined["trade_vs_bias"].iloc[0] == "en_contra"


def test_regime_label_from_row_parses_enums():
    labeled = classify_regimes(make_session("2026-01-05", 100 + 0.5 * np.arange(120)), FAST_CFG)
    row = labeled.iloc[-1]
    label = RegimeLabel.from_row(labeled.index[-1], row)
    assert label.trend == TrendRegime.TENDENCIA_ALCISTA
    assert label.bias == DirectionalBias.ALCISTA
    assert label.volatility is None  # una sola sesión: sin historia de vol
