"""Familias predefinidas del Strategy Lab."""

from __future__ import annotations

from .models import ParameterGrid, StrategyFamily


_FAMILIES: dict[str, StrategyFamily] = {
    "rr2_atr_filter": StrategyFamily(
        name="rr2_atr_filter",
        base_strategy="daytrading_vwap_liquidity_rr2_no_midday_atr_filter",
        description=(
            "Busqueda limitada sobre parametros existentes de la familia "
            "VWAP liquidity RR2 no_midday atr_filter."
        ),
        parameter_grid=ParameterGrid({
            "min_atr20_points": [6.0, 8.0, 10.0],
            "rel_volume_threshold": [1.05, 1.10],
            "max_vwap_distance_points": [40.0, 60.0],
            "min_slope_points": [1.5, 2.0],
        }),
        fixed_params={"blocked_entry_windows": [["11:00", "13:00"]]},
    ),
    "base_vwap_ema": StrategyFamily(
        name="base_vwap_ema",
        base_strategy="base_vwap_ema",
        description="Busqueda pequena y conservadora sobre la estrategia base.",
        parameter_grid=ParameterGrid({
            "rel_volume_threshold": [1.00, 1.05, 1.10],
            "pullback_lookback": [8, 10],
            "rr": [1.5, 2.0],
        }),
    ),
}

_ALIASES = {
    "daytrading_vwap_liquidity_rr2_no_midday_atr_filter": "rr2_atr_filter",
}


def available_families() -> list[str]:
    return sorted(_FAMILIES)


def get_family(name: str) -> StrategyFamily:
    key = _ALIASES.get(name, name)
    try:
        return _FAMILIES[key]
    except KeyError as exc:
        raise ValueError(
            f"Familia desconocida: {name!r}. Disponibles: {', '.join(available_families())}"
        ) from exc


__all__ = ["available_families", "get_family"]
