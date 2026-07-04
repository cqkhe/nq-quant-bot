"""Utilidades de sesión para futuros CME Globex (NQ/MNQ).

Conceptos clave:
  * El día de TRADING no es el día calendario: la sesión del martes abre el
    lunes a las 18:00 ET. `trade_session_key` asigna cada barra a su fecha
    de sesión real (barras >= globex_open pertenecen al día siguiente).
  * Las ventanas overnight cruzan medianoche; `time_in_range` compara
    horarios con wrap-around.

Ventanas (hora ET, configurables en SessionConfig):
  overnight:  globex_open (18:00) -> premarket_start (04:00)
  premarket:  premarket_start (04:00) -> rth_start (09:30)
  regular:    rth_start (09:30) -> rth_end (16:00)
  all:        globex_open (18:00) -> globex_close (17:00)
"""

from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd

from ..config.settings import SessionConfig


def time_in_range(t: time, start: time, end: time, inclusive_end: bool = False) -> bool:
    """¿`t` cae dentro de [start, end)? Soporta ventanas que cruzan medianoche."""
    if start <= end:
        return (start <= t <= end) if inclusive_end else (start <= t < end)
    # ventana con wrap (ej: 18:00 -> 04:00)
    return (t >= start or t <= end) if inclusive_end else (t >= start or t < end)


def trade_session_key(idx: pd.DatetimeIndex, cfg: SessionConfig) -> pd.DatetimeIndex:
    """Fecha de sesión de trading de cada barra.

    Barras con hora >= globex_open pertenecen a la sesión del día siguiente.
    Para datos solo-RTH es idéntico a la fecha calendario (sin cambio de
    comportamiento respecto de la fase 1).
    """
    dates = idx.normalize()
    after_open = np.fromiter((t >= cfg.globex_open for t in idx.time), dtype=bool, count=len(idx))
    return dates + pd.to_timedelta(after_open.astype("int64"), unit="D")


def filter_to_trade_session(df: pd.DataFrame, cfg: SessionConfig) -> pd.DataFrame:
    """Recorta el dataset a la ventana configurada en `trade_session`."""
    start, end = cfg.trade_window()
    mask = np.fromiter(
        (time_in_range(t, start, end) for t in df.index.time), dtype=bool, count=len(df)
    )
    return df[mask]


def window_minutes(start: time, end: time) -> int:
    """Duración de una ventana en minutos, con wrap-around."""
    s = start.hour * 60 + start.minute
    e = end.hour * 60 + end.minute
    return (e - s) % (24 * 60)


def expected_bars_per_session(cfg: SessionConfig, interval_minutes: int = 1) -> int:
    """Velas esperadas por sesión completa en la ventana activa (390 en RTH 1m)."""
    start, end = cfg.trade_window()
    return window_minutes(start, end) // max(1, interval_minutes)
