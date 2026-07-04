"""Paquete de backtesting.

Los modelos se exportan directo (no dependen de nada interno). El engine,
las métricas y el reporte se cargan lazy (PEP 562) para evitar imports
circulares: strategies/risk/execution importan `backtesting.models`, y el
engine importa a su vez strategies/risk/execution — si este __init__ cargara
el engine con avidez, importar primero cualquiera de esos paquetes rompería.
"""

from .models import BacktestResult, PendingEntry, Position, Signal, Trade

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "PendingEntry",
    "Position",
    "Signal",
    "Trade",
    "compute_metrics",
    "format_summary",
    "save_report",
]

_LAZY = {
    "BacktestEngine": ("nqbot.backtesting.engine", "BacktestEngine"),
    "compute_metrics": ("nqbot.backtesting.metrics", "compute_metrics"),
    "format_summary": ("nqbot.backtesting.report", "format_summary"),
    "save_report": ("nqbot.backtesting.report", "save_report"),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        module_name, attr = _LAZY[name]
        return getattr(importlib.import_module(module_name), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
