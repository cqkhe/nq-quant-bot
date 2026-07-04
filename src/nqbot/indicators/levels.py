"""Niveles de referencia de sesión (zonas de liquidez estáticas).

Por ahora: máximo/mínimo/cierre de la sesión ANTERIOR (PDH/PDL/PDC),
niveles donde típicamente descansa liquidez. La estrategia base los expone
como contexto; versiones futuras pueden exigir confluencia con ellos.
"""

from __future__ import annotations

import pandas as pd


def prior_session_levels(df: pd.DataFrame) -> pd.DataFrame:
    """PDH/PDL/PDC de la sesión anterior, propagados a cada barra intradía.

    La primera sesión del dataset queda NaN (no hay día previo).
    """
    session = df.index.normalize()
    daily = df.groupby(session).agg(pdh=("high", "max"), pdl=("low", "min"), pdc=("close", "last"))
    prior = daily.shift(1)
    return prior.reindex(session).set_index(df.index)
