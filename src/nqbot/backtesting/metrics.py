"""Metrics Reporter — estadísticas de performance de un BacktestResult.

Notas metodológicas:
  * Expectancia: media del PnL neto por trade (en USD y en múltiplos de R).
  * Profit factor: ganancia bruta / pérdida bruta (inf si no hubo pérdidas).
  * Drawdown: sobre la curva de equity mark-to-market barra a barra.
  * Sharpe: sobre retornos diarios (equity al cierre de cada sesión),
    anualizado por sqrt(252). Requiere >= 2 sesiones y varianza > 0.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .models import BacktestResult

TRADING_DAYS_PER_YEAR = 252


def _max_streak(flags: np.ndarray) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def compute_metrics(result: BacktestResult) -> dict[str, Any]:
    eq = result.equity_curve
    m: dict[str, Any] = {
        "n_trades": len(result.trades),
        "initial_capital": result.initial_capital,
        "final_equity": float(eq.iloc[-1]),
    }
    m["total_net_pnl"] = m["final_equity"] - m["initial_capital"]
    m["total_return_pct"] = m["total_net_pnl"] / m["initial_capital"] * 100.0

    # ---- drawdown sobre la curva mark-to-market
    running_max = eq.cummax()
    dd = eq - running_max
    m["max_drawdown"] = float(-dd.min())
    m["max_drawdown_pct"] = float(-(dd / running_max).min() * 100.0)

    # ---- retornos diarios -> Sharpe
    daily_equity = eq.groupby(eq.index.normalize()).last()
    m["n_sessions"] = len(daily_equity)
    daily_returns = daily_equity.pct_change().dropna()
    if len(daily_returns) >= 2 and daily_returns.std() > 0:
        m["sharpe"] = float(
            daily_returns.mean() / daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
        )
    else:
        m["sharpe"] = None

    if not result.trades:
        return m

    # ---- métricas por trade
    pnls = np.array([t.pnl_net for t in result.trades])
    rs = np.array([t.r_multiple for t in result.trades])
    wins, losses = pnls > 0, pnls < 0

    m["n_long"] = sum(1 for t in result.trades if t.direction > 0)
    m["n_short"] = m["n_trades"] - m["n_long"]

    # RR planificado real de cada trade ejecutado: (target - entry) / (entry - stop).
    # Debería igualar el rr configurado salvo el redondeo del target al tick.
    planned_rrs = []
    for t in result.trades:
        risk_pts = (t.entry_price - t.stop_price) * t.direction
        if risk_pts > 0:
            planned_rrs.append((t.target_price - t.entry_price) * t.direction / risk_pts)
    m["avg_planned_rr"] = float(np.mean(planned_rrs)) if planned_rrs else None

    m["winrate_pct"] = float(wins.mean() * 100.0)
    gross_profit = float(pnls[wins].sum()) if wins.any() else 0.0
    gross_loss = float(-pnls[losses].sum()) if losses.any() else 0.0
    m["gross_profit"] = gross_profit
    m["gross_loss"] = gross_loss
    m["profit_factor"] = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    m["expectancy_usd"] = float(pnls.mean())
    m["expectancy_r"] = float(rs.mean())
    m["avg_win"] = float(pnls[wins].mean()) if wins.any() else 0.0
    m["avg_loss"] = float(pnls[losses].mean()) if losses.any() else 0.0
    m["best_trade"] = float(pnls.max())
    m["worst_trade"] = float(pnls.min())
    m["total_commission"] = float(sum(t.commission for t in result.trades))
    m["max_consecutive_wins"] = _max_streak(wins)
    m["max_consecutive_losses"] = _max_streak(losses)
    m["avg_bars_held"] = float(np.mean([t.bars_held for t in result.trades]))

    reasons: dict[str, int] = {}
    for t in result.trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    m["exits_by_reason"] = reasons
    return m
