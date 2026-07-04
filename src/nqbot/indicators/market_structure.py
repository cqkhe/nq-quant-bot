"""Estructura de mercado: swings fractales confirmados, sin lookahead.

Un swing high en la barra i requiere que su máximo domine k barras a cada
lado; eso recién se sabe en la barra i+k. `last_confirmed_level` desplaza el
nivel k barras hacia adelante para que la estrategia solo vea swings que un
trader real ya habría podido confirmar en ese momento.
"""

from __future__ import annotations

import pandas as pd


def swing_flags(high: pd.Series, low: pd.Series, k: int = 3) -> tuple[pd.Series, pd.Series]:
    """Marca swing highs/lows fractales (ventana centrada de 2k+1 barras)."""
    if k < 1:
        raise ValueError(f"k inválido para swings: {k}")
    window = 2 * k + 1
    is_high = high == high.rolling(window, center=True).max()
    is_low = low == low.rolling(window, center=True).min()
    return is_high.fillna(False), is_low.fillna(False)


def last_confirmed_level(values: pd.Series, flags: pd.Series, k: int) -> pd.Series:
    """Último nivel de swing CONFIRMADO disponible en cada barra.

    El valor del swing en i se publica en i+k (cuando se confirma) y se
    mantiene con forward-fill hasta que aparezca uno nuevo. Antes del primer
    swing confirmado el nivel es NaN.
    """
    return values.where(flags).shift(k).ffill()
