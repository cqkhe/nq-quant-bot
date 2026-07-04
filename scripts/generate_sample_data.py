#!/usr/bin/env python
"""Genera datos OHLCV 1-minuto SINTÉTICOS estilo MNQ para validar el motor.

ADVERTENCIA: estos datos NO son de mercado real. Sirven para probar la
mecánica del sistema (fills, riesgo, métricas), no para evaluar si una
estrategia tiene edge. Para investigación real usar datos históricos de un
proveedor (Databento, Polygon, CME DataMine, el broker, etc.).

Uso:
    python scripts/generate_sample_data.py --days 60 --out data/MNQ_1m_sample.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

TICK = 0.25
RTH_MINUTES = 390  # 09:30 -> 15:59 ET


def _round_tick(a: np.ndarray) -> np.ndarray:
    return np.round(a / TICK) * TICK


def generate_session(
    rng: np.random.Generator, start_price: float, day: pd.Timestamp
) -> tuple[pd.DataFrame, float]:
    n = RTH_MINUTES
    x = np.linspace(0.0, 1.0, n)
    u_shape = 0.8 + 0.9 * (np.abs(x - 0.5) * 2.0) ** 1.5  # actividad alta en open/close

    daily_bias = rng.normal(0.0, 0.0045)  # deriva del día (~0.45% std)
    drift = daily_bias / n
    sigma = 0.00030 * u_shape
    shock = rng.standard_normal(n) * sigma

    # AR(1) suave para que existan tendencias intradía operables
    rets = np.empty(n)
    prev = 0.0
    for i in range(n):
        prev = drift + shock[i] + 0.25 * prev
        rets[i] = prev

    closes = start_price * np.cumprod(1.0 + rets)
    opens = np.empty(n)
    opens[0] = start_price * (1.0 + rng.normal(0.0, 0.0008))  # gap overnight
    opens[1:] = closes[:-1]

    wicks = np.abs(rng.standard_normal((2, n))) * sigma * closes * 0.6
    highs = np.maximum(opens, closes) + wicks[0]
    lows = np.minimum(opens, closes) - wicks[1]

    volume = np.maximum(
        1,
        (1200.0 * u_shape * (1.0 + 60.0 * np.abs(rets)) * rng.lognormal(0.0, 0.35, n)).astype(int),
    )

    opens, closes = _round_tick(opens), _round_tick(closes)
    highs = np.maximum(_round_tick(highs), np.maximum(opens, closes))
    lows = np.minimum(_round_tick(lows), np.minimum(opens, closes))

    idx = pd.date_range(day + pd.Timedelta(hours=9, minutes=30), periods=n, freq="1min")
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volume},
        index=pd.DatetimeIndex(idx, name="datetime"),
    )
    return df, float(closes[-1])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=60, help="Cantidad de sesiones RTH")
    ap.add_argument("--start", default="2026-01-05", help="Primera sesión (YYYY-MM-DD)")
    ap.add_argument("--price", type=float, default=21000.0, help="Precio inicial")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/MNQ_1m_sample.csv")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    price = args.price
    sessions = []
    for day in pd.bdate_range(args.start, periods=args.days):
        df, price = generate_session(rng, price, day)
        sessions.append(df)

    out = pd.concat(sessions)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path)

    print(f"[SINTETICO] {len(out):,} barras | {out.index[0]} -> {out.index[-1]}")
    print(f"Precio final: {out['close'].iloc[-1]:,.2f} | Archivo: {path}")
    print("ADVERTENCIA: datos sinteticos, solo para validar la mecanica del motor.")


if __name__ == "__main__":
    main()
