#!/usr/bin/env python
"""Análisis estadístico post-backtest sobre un reporte guardado.

Lee trades.csv y equity_curve.csv de una carpeta de reporte y genera en
<reporte>/analysis/ los desgloses estándar de performance:

    performance_by_month.csv        por mes calendario
    performance_by_week.csv         por semana ISO
    performance_by_day_of_week.csv  por día de la semana
    performance_by_hour.csv         por hora de entrada (ET)
    performance_by_side.csv         long vs short
    performance_by_exit_reason.csv  stop / target / session_flatten
    streaks.csv                     todas las rachas ganadoras/perdedoras
    r_distribution.csv              histograma de resultados en R (bins 0.25)
    drawdown_periods.csv            episodios de drawdown (pico->valle->recuperación)
    analysis_summary.txt            resumen legible con los hallazgos

Solo estadística descriptiva: NO modifica estrategia, motor ni parámetros.

Uso:
    python scripts/analyze_backtest.py --report reports/20260704_125049_MNQ_daytrading_vwap_liquidity_rr2
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DOW_NAMES = {0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 4: "viernes",
             5: "sábado", 6: "domingo"}
MIN_SAMPLE = 8  # por debajo de esto, un subgrupo no permite conclusiones


# ------------------------------------------------------------------ carga
def load_report(folder: Path) -> tuple[pd.DataFrame, pd.Series]:
    trades = pd.read_csv(folder / "trades.csv", parse_dates=["entry_time", "exit_time"])
    equity = pd.read_csv(folder / "equity_curve.csv", index_col=0, parse_dates=True)["equity"]
    return trades.sort_values(["exit_time", "entry_time"]).reset_index(drop=True), equity


# ------------------------------------------------------------------ helpers
def _bucket_stats(name_col: str, key: str, group: pd.DataFrame) -> dict:
    pnl = group["pnl_net"]
    wins, losses = pnl > 0, pnl < 0
    gp = float(pnl[wins].sum())
    gl = float(-pnl[losses].sum())
    return {
        name_col: key,
        "trades": len(group),
        "wins": int(wins.sum()),
        "losses": int(losses.sum()),
        "winrate_pct": round(wins.mean() * 100, 2),
        "pnl_net": round(pnl.sum(), 2),
        "pnl_promedio": round(pnl.mean(), 2),
        "r_promedio": round(group["r_multiple"].mean(), 3),
        "gross_profit": round(gp, 2),
        "gross_loss": round(gl, 2),
        "profit_factor": round(gp / gl, 2) if gl > 0 else float("inf"),
        "mejor_trade": round(pnl.max(), 2),
        "peor_trade": round(pnl.min(), 2),
    }


def group_table(trades: pd.DataFrame, keys: pd.Series, name_col: str) -> pd.DataFrame:
    rows = [_bucket_stats(name_col, key, g) for key, g in trades.groupby(keys, sort=True)]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ desgloses
def by_month(trades: pd.DataFrame) -> pd.DataFrame:
    table = group_table(trades, trades["entry_time"].dt.to_period("M").astype(str), "mes")
    table["pnl_acumulado"] = table["pnl_net"].cumsum().round(2)
    return table


def by_week(trades: pd.DataFrame) -> pd.DataFrame:
    iso = trades["entry_time"].dt.isocalendar()
    key = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    return group_table(trades, key, "semana")


def by_day_of_week(trades: pd.DataFrame) -> pd.DataFrame:
    table = group_table(trades, trades["entry_time"].dt.dayofweek, "dow")
    table.insert(1, "dia", table["dow"].map(DOW_NAMES))
    return table


def by_hour(trades: pd.DataFrame) -> pd.DataFrame:
    key = trades["entry_time"].dt.hour.map(lambda h: f"{h:02d}:00-{h:02d}:59")
    return group_table(trades, key, "hora_entrada")


def by_side(trades: pd.DataFrame) -> pd.DataFrame:
    return group_table(trades, trades["direction"].map({1: "long", -1: "short"}), "lado")


def by_exit_reason(trades: pd.DataFrame) -> pd.DataFrame:
    table = group_table(trades, trades["exit_reason"], "motivo_salida")
    table["pct_trades"] = (table["trades"] / len(trades) * 100).round(1)
    return table


def streaks_table(trades: pd.DataFrame) -> pd.DataFrame:
    win = trades["pnl_net"] > 0
    streak_id = (win != win.shift()).cumsum()
    rows = []
    for _, g in trades.groupby(streak_id):
        rows.append({
            "tipo": "ganadora" if g["pnl_net"].iloc[0] > 0 else "perdedora",
            "largo": len(g),
            "desde": g["entry_time"].iloc[0],
            "hasta": g["exit_time"].iloc[-1],
            "pnl_total": round(g["pnl_net"].sum(), 2),
            "r_total": round(g["r_multiple"].sum(), 2),
        })
    return pd.DataFrame(rows)


def r_distribution(trades: pd.DataFrame) -> pd.DataFrame:
    r = trades["r_multiple"]
    lo = np.floor(r.min() * 4) / 4
    hi = np.ceil(r.max() * 4) / 4 + 0.25
    bins = np.arange(lo, hi + 1e-9, 0.25)
    counts = pd.cut(r, bins=bins, right=False).value_counts().sort_index()
    table = pd.DataFrame({
        "r_desde": [iv.left for iv in counts.index],
        "r_hasta": [iv.right for iv in counts.index],
        "trades": counts.values,
    })
    table = table[table["trades"] > 0].reset_index(drop=True)
    table["pct"] = (table["trades"] / len(r) * 100).round(2)
    table["pct_acumulado"] = table["pct"].cumsum().round(2)
    return table


def drawdown_periods(equity: pd.Series, top: int = 15) -> pd.DataFrame:
    running_max = equity.cummax()
    dd = equity - running_max
    at_peak = dd >= 0
    segment_id = at_peak.cumsum()
    idx = equity.index
    rows = []
    for _, seg in dd[~at_peak].groupby(segment_id[~at_peak]):
        start_pos = idx.get_loc(seg.index[0])
        end_pos = idx.get_loc(seg.index[-1])
        peak_time = idx[start_pos - 1] if start_pos > 0 else seg.index[0]
        recovery_time = idx[end_pos + 1] if end_pos + 1 < len(idx) else None
        trough_time = seg.idxmin()
        depth = float(seg.min())
        rows.append({
            "inicio_pico": peak_time,
            "valle": trough_time,
            "recuperacion": recovery_time if recovery_time is not None else "sin recuperar",
            "profundidad_usd": round(-depth, 2),
            "profundidad_pct": round(-depth / float(running_max.loc[trough_time]) * 100, 3),
            "dias_hasta_valle": (trough_time - peak_time).days,
            "dias_totales": ((recovery_time if recovery_time is not None else idx[-1]) - peak_time).days,
            "recuperado": recovery_time is not None,
        })
    table = pd.DataFrame(rows).sort_values("profundidad_usd", ascending=False).head(top)
    return table.reset_index(drop=True)


# ------------------------------------------------------------------ resumen
def build_summary(trades: pd.DataFrame, equity: pd.Series, tables: dict[str, pd.DataFrame]) -> str:
    pnl = trades["pnl_net"]
    wins = pnl[pnl > 0]
    total = float(pnl.sum())
    gp = float(wins.sum())
    lines = ["=" * 70, "  ANÁLISIS POST-BACKTEST (estadística descriptiva, sin optimización)",
             f"  Trades: {len(trades)} | PnL neto: ${total:,.2f} | "
             f"Winrate: {(pnl > 0).mean() * 100:.1f}% | R promedio: {trades['r_multiple'].mean():.2f}",
             f"  Equity: ${equity.iloc[0]:,.2f} -> ${equity.iloc[-1]:,.2f} | "
             f"Drawdown máx: ${-(equity - equity.cummax()).min():,.2f}",
             "=" * 70, ""]

    def sec(title: str) -> None:
        lines.extend(["-" * 70, f"  {title}", "-" * 70])

    # --- meses
    m = tables["month"].sort_values("pnl_net")
    sec("MESES")
    best, worst = m.iloc[-1], m.iloc[0]
    for _, row in m.sort_values("mes").iterrows():
        lines.append(f"  {row['mes']}: {row['pnl_net']:+9.2f} USD | {row['trades']:2d} trades | "
                     f"winrate {row['winrate_pct']:5.1f}% | PF {row['profit_factor']}")
    lines.append(f"  Mejor mes: {best['mes']} ({best['pnl_net']:+.2f}) | "
                 f"Peor mes: {worst['mes']} ({worst['pnl_net']:+.2f})")
    lines.append(f"  Meses positivos: {(m['pnl_net'] > 0).sum()} de {len(m)}")
    lines.append("")

    # --- long vs short
    sec("LONG vs SHORT")
    for _, row in tables["side"].iterrows():
        lines.append(f"  {row['lado']:<6}: {row['trades']:3d} trades | PnL {row['pnl_net']:+9.2f} | "
                     f"winrate {row['winrate_pct']:5.1f}% | PF {row['profit_factor']} | "
                     f"R prom {row['r_promedio']:+.3f}")
    lines.append("")

    # --- horarios
    sec("HORA DE ENTRADA (ET)")
    for _, row in tables["hour"].iterrows():
        flag = "" if row["trades"] >= MIN_SAMPLE else "  [muestra chica]"
        lines.append(f"  {row['hora_entrada']}: {row['trades']:3d} trades | PnL {row['pnl_net']:+9.2f} | "
                     f"winrate {row['winrate_pct']:5.1f}% | R prom {row['r_promedio']:+.3f}{flag}")
    lines.append(f"  (subgrupos con < {MIN_SAMPLE} trades no permiten conclusiones)")
    lines.append("")

    # --- motivo de salida
    sec("MOTIVO DE SALIDA")
    for _, row in tables["exit"].iterrows():
        lines.append(f"  {row['motivo_salida']:<16}: {row['trades']:3d} ({row['pct_trades']:4.1f}%) | "
                     f"PnL {row['pnl_net']:+9.2f} | R prom {row['r_promedio']:+.3f}")
    flatten = tables["exit"][tables["exit"]["motivo_salida"] == "session_flatten"]
    if not flatten.empty:
        f = flatten.iloc[0]
        lines.append(f"  -> session_flatten aporta {f['pnl_net']:+.2f} USD en {f['trades']} trades "
                     f"({f['pnl_net'] / total * 100 if total else 0:.1f}% del PnL neto)")
    lines.append("")

    # --- rachas
    st = tables["streaks"]
    sec("RACHAS")
    worst_streak = st[st["tipo"] == "perdedora"].sort_values("largo").iloc[-1] if (st["tipo"] == "perdedora").any() else None
    best_streak = st[st["tipo"] == "ganadora"].sort_values("largo").iloc[-1] if (st["tipo"] == "ganadora").any() else None
    if best_streak is not None:
        lines.append(f"  Mayor racha ganadora: {best_streak['largo']} trades ({best_streak['pnl_total']:+.2f} USD)")
    if worst_streak is not None:
        lines.append(f"  Mayor racha perdedora: {worst_streak['largo']} trades ({worst_streak['pnl_total']:+.2f} USD) "
                     f"entre {worst_streak['desde']:%Y-%m-%d} y {worst_streak['hasta']:%Y-%m-%d}")
    lines.append("")

    # --- concentración (dependencia de pocos ganadores)
    sec("CONCENTRACIÓN DE RESULTADOS")
    top3 = float(wins.nlargest(3).sum())
    top5 = float(wins.nlargest(5).sum())
    lines.append(f"  Top 3 ganadores: {top3:+.2f} USD ({top3 / gp * 100:.1f}% del gross profit)")
    lines.append(f"  Top 5 ganadores: {top5:+.2f} USD ({top5 / gp * 100:.1f}% del gross profit)")
    lines.append(f"  PnL neto sin los 3 mejores trades: {total - top3:+.2f} USD")
    lines.append(f"  PnL neto sin los 5 mejores trades: {total - top5:+.2f} USD")
    lines.append("")

    # --- drawdowns
    dd = tables["drawdowns"].head(3)
    sec("DRAWDOWNS PRINCIPALES")
    for _, row in dd.iterrows():
        lines.append(f"  -{row['profundidad_usd']:.2f} USD ({row['profundidad_pct']:.2f}%) | "
                     f"pico {row['inicio_pico']} -> valle {row['valle']} | "
                     f"{row['dias_totales']} días{'' if row['recuperado'] else ' (SIN RECUPERAR)'}")
    lines.append("")
    lines.append("Nota: 89 trades es una muestra moderada; los subgrupos (hora, semana)")
    lines.append("son chicos. Este análisis describe QUÉ pasó, no justifica re-tunear.")
    return "\n".join(lines)


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", required=True, help="Carpeta del reporte de backtest")
    args = ap.parse_args()

    folder = Path(args.report)
    if not (folder / "trades.csv").exists():
        print(f"ERROR: no existe {folder / 'trades.csv'}")
        return 2

    trades, equity = load_report(folder)
    out = folder / "analysis"
    out.mkdir(exist_ok=True)

    tables = {
        "month": by_month(trades),
        "week": by_week(trades),
        "dow": by_day_of_week(trades),
        "hour": by_hour(trades),
        "side": by_side(trades),
        "exit": by_exit_reason(trades),
        "streaks": streaks_table(trades),
        "r_dist": r_distribution(trades),
        "drawdowns": drawdown_periods(equity),
    }
    filenames = {
        "month": "performance_by_month.csv",
        "week": "performance_by_week.csv",
        "dow": "performance_by_day_of_week.csv",
        "hour": "performance_by_hour.csv",
        "side": "performance_by_side.csv",
        "exit": "performance_by_exit_reason.csv",
        "streaks": "streaks.csv",
        "r_dist": "r_distribution.csv",
        "drawdowns": "drawdown_periods.csv",
    }
    for key, fname in filenames.items():
        tables[key].to_csv(out / fname, index=False)

    summary = build_summary(trades, equity, tables)
    (out / "analysis_summary.txt").write_text(summary, encoding="utf-8")
    print(summary)
    print(f"\nArchivos generados en: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
