"""Renderizado y persistencia de reportes de backtest.

Cada corrida genera una carpeta reports/<timestamp>_<símbolo>_<estrategia>/ con:
  summary.txt        resumen legible (lo mismo que se imprime en consola)
  trades.csv         todas las operaciones con su detalle completo
  equity_curve.csv   equity mark-to-market por barra
  equity_curve.png   curva de capital + drawdown
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .models import BacktestResult


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.2f}{suffix}"
    return f"{value}{suffix}"


def format_summary(result: BacktestResult, m: dict[str, Any]) -> str:
    lines = [
        "=" * 62,
        f"  BACKTEST  {result.symbol}  |  {result.strategy_name}",
        f"  {result.start:%Y-%m-%d %H:%M} -> {result.end:%Y-%m-%d %H:%M}  ({m['n_sessions']} sesiones)",
        "=" * 62,
        f"  Capital inicial      $ {_fmt(m['initial_capital'])}",
        f"  Equity final         $ {_fmt(m['final_equity'])}",
        f"  PnL neto             $ {_fmt(m['total_net_pnl'])}  ({_fmt(m['total_return_pct'], ' %')})",
        f"  Drawdown máximo      $ {_fmt(m['max_drawdown'])}  ({_fmt(m['max_drawdown_pct'], ' %')})",
        f"  Sharpe (diario an.)  {_fmt(m['sharpe'])}",
        "-" * 62,
        f"  Operaciones          {m['n_trades']}",
    ]
    if m["n_trades"] > 0:
        pf = m["profit_factor"]
        lines += [
            f"  Long / Short         {m['n_long']} / {m['n_short']}",
            f"  Winrate              {_fmt(m['winrate_pct'], ' %')}",
            f"  Profit factor        {'inf' if pf == float('inf') else _fmt(pf)}",
            f"  Expectancia          $ {_fmt(m['expectancy_usd'])}  ({_fmt(m['expectancy_r'])} R)",
            f"  RR promedio ejecutado {_fmt(m['avg_planned_rr'])}  (target vs stop reales)",
            f"  Ganancia media       $ {_fmt(m['avg_win'])}   Pérdida media  $ {_fmt(m['avg_loss'])}",
            f"  Mejor / peor trade   $ {_fmt(m['best_trade'])}  /  $ {_fmt(m['worst_trade'])}",
            f"  Rachas (W/L)         {m['max_consecutive_wins']} / {m['max_consecutive_losses']}",
            f"  Comisiones totales   $ {_fmt(m['total_commission'])}",
            f"  Barras promedio      {_fmt(m['avg_bars_held'])}",
            f"  Salidas por motivo   {m['exits_by_reason']}",
        ]
    if result.skipped_signals:
        lines += ["-" * 62, f"  Señales descartadas  {result.skipped_signals}"]
    lines += ["-" * 62, f"  Parámetros           {result.params}", "=" * 62]
    return "\n".join(lines)


def save_report(
    result: BacktestResult,
    metrics: dict[str, Any],
    out_dir: str | Path = "reports",
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = Path(out_dir) / f"{stamp}_{result.symbol}_{result.strategy_name}"
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "summary.txt").write_text(format_summary(result, metrics), encoding="utf-8")

    if result.trades:
        pd.DataFrame([asdict(t) for t in result.trades]).to_csv(folder / "trades.csv", index=False)
    result.equity_curve.to_csv(folder / "equity_curve.csv")
    _plot_equity(result, folder / "equity_curve.png")
    return folder


def _plot_equity(result: BacktestResult, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")  # sin display: solo archivo
    import matplotlib.pyplot as plt

    eq = result.equity_curve
    dd = eq - eq.cummax()

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True, height_ratios=[3, 1],
        gridspec_kw={"hspace": 0.08},
    )
    ax1.plot(eq.index, eq.values, linewidth=1.1)
    ax1.axhline(result.initial_capital, linestyle="--", linewidth=0.8, alpha=0.6)
    ax1.set_ylabel("Equity (USD)")
    ax1.set_title(f"{result.symbol} — {result.strategy_name}")
    ax1.grid(alpha=0.25)

    ax2.fill_between(dd.index, dd.values, 0, alpha=0.45)
    ax2.set_ylabel("Drawdown (USD)")
    ax2.grid(alpha=0.25)

    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
