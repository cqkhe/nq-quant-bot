#!/usr/bin/env python
"""Validación out-of-sample: original vs candidata no_midday, head-to-head.

Protocolo pre-registrado en docs/strategy_decision_log.md:
  la candidata se promueve solo si, sobre datos que NO participaron en su
  diseño (el filtro salió del período dic-2025 -> jun-2026):
    1. expR(no_midday) > expR(original)
    2. drawdown máximo no peor
    3. muestra orientativa >= 30 trades de la candidata

Este script corre ambas estrategias con la config vigente, SIN tocar lógica
ni parámetros, y emite el veredicto contra ese criterio. Si el rango del
archivo se solapa con el período in-sample lo advierte: esa corrida no vale
como validación.

Uso:
    python scripts/validate_no_midday.py --data data/processed/ARCHIVO_clean.csv

Genera:
    reports/out_of_sample_validation.csv
    reports/out_of_sample_validation_summary.txt
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nqbot.backtesting.engine import BacktestEngine          # noqa: E402
from nqbot.backtesting.metrics import compute_metrics        # noqa: E402
from nqbot.config.settings import Config                     # noqa: E402
from nqbot.data.loader import load_ohlcv_csv                 # noqa: E402
from nqbot.strategies.registry import create_strategy        # noqa: E402
from nqbot.utils.logger import setup_logger                  # noqa: E402
from nqbot.utils.sessions import filter_to_trade_session     # noqa: E402

BASE = "daytrading_vwap_liquidity_rr2"
CANDIDATE = "daytrading_vwap_liquidity_rr2_no_midday"
MIDDAY_HOURS = (11, 12)

# Período usado para DISEÑAR el filtro: si los datos se solapan con esto,
# la corrida no cuenta como validación out-of-sample.
IN_SAMPLE_START = pd.Timestamp("2025-12-29")
IN_SAMPLE_END = pd.Timestamp("2026-06-18")

MIN_CANDIDATE_TRADES = 30  # por debajo, el veredicto es provisional


def run_strategy(name: str, df: pd.DataFrame, config: Config, contract, logger):
    strategy = create_strategy(name, config.strategy_params.get(name), contract)
    result = BacktestEngine(config, contract, strategy, logger).run(df)
    trades = pd.DataFrame([asdict(t) for t in result.trades])
    if not trades.empty:
        trades["entry_time"] = pd.to_datetime(trades["entry_time"])
    return result, trades


def metrics_row(name: str, result, m: dict) -> dict:
    exits = m.get("exits_by_reason", {})
    return {
        "estrategia": name,
        "trades": m["n_trades"],
        "pnl_net": round(m["total_net_pnl"], 2),
        "profit_factor": round(m["profit_factor"], 3) if m["n_trades"] else None,
        "winrate_pct": round(m["winrate_pct"], 2) if m["n_trades"] else None,
        "expectancy_r": round(m["expectancy_r"], 3) if m["n_trades"] else None,
        "max_drawdown_usd": round(m["max_drawdown"], 2),
        "max_drawdown_pct": round(m["max_drawdown_pct"], 2),
        "racha_perdedora_max": m.get("max_consecutive_losses", 0),
        "salidas_target": exits.get("target", 0) + exits.get("target_gap", 0),
        "salidas_stop": exits.get("stop", 0) + exits.get("stop_gap", 0),
        "salidas_flatten": exits.get("session_flatten", 0),
    }


def monthly_table(o_trades: pd.DataFrame, v_trades: pd.DataFrame) -> pd.DataFrame:
    def stats(trades: pd.DataFrame) -> pd.DataFrame:
        if trades.empty:
            return pd.DataFrame(columns=["pnl", "expr", "n"])
        month = trades["entry_time"].dt.to_period("M").astype(str).to_numpy()
        grouped = trades.groupby(month)
        return pd.DataFrame({
            "pnl": grouped["pnl_net"].sum().round(2),
            "expr": grouped["r_multiple"].mean().round(3),
            "n": grouped.size(),
        })

    o, v = stats(o_trades), stats(v_trades)
    table = o.join(v, how="outer", lsuffix="_orig", rsuffix="_nomid").fillna(0)
    table.index.name = "mes"
    return table


def decompose(o_trades: pd.DataFrame, v_trades: pd.DataFrame) -> list[str]:
    if o_trades.empty or v_trades.empty:
        return ["  (sin trades suficientes para descomponer)"]
    o_key, v_key = set(o_trades["entry_time"]), set(v_trades["entry_time"])
    midday = o_trades[o_trades["entry_time"].dt.hour.isin(MIDDAY_HOURS)
                      & ~o_trades["entry_time"].isin(v_key)]
    new = v_trades[~v_trades["entry_time"].isin(o_key)]
    dropped = o_trades[~o_trades["entry_time"].isin(v_key)
                       & ~o_trades["entry_time"].dt.hour.isin(MIDDAY_HOURS)]
    common_o = o_trades[o_trades["entry_time"].isin(v_key)]["pnl_net"].sum()
    common_v = v_trades[v_trades["entry_time"].isin(o_key)]["pnl_net"].sum()
    return [
        f"  Mediodía evitado:   {len(midday):3d} trades (PnL {midday['pnl_net'].sum():+,.2f}) "
        f"-> aporta {-midday['pnl_net'].sum():+,.2f}",
        f"  Trades nuevos:      {len(new):3d} trades -> aporta {new['pnl_net'].sum():+,.2f}",
        f"  Trades perdidos:    {len(dropped):3d} trades -> aporta {-dropped['pnl_net'].sum():+,.2f}",
        f"  Sizing en comunes:  {common_v - common_o:+,.2f}",
    ]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="CSV procesado (data/processed/...)")
    ap.add_argument("--symbol", default="MNQ")
    ap.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    ap.add_argument("--out-name", default="out_of_sample_validation",
                    help="Nombre base de los reportes en reports/ (sin extensión)")
    args = ap.parse_args()

    logger = setup_logger(log_dir=ROOT / "logs", level=logging.WARNING)
    config = Config.from_yaml(args.config)
    contract = config.contract(args.symbol)
    df = load_ohlcv_csv(args.data, logger)
    df = filter_to_trade_session(df, config.session)

    overlaps_in_sample = df.index[0] <= IN_SAMPLE_END and df.index[-1] >= IN_SAMPLE_START

    print(f"corriendo {BASE} y {CANDIDATE} ...")
    o_result, o_trades = run_strategy(BASE, df, config, contract, logger)
    v_result, v_trades = run_strategy(CANDIDATE, df, config, contract, logger)
    o_m, v_m = compute_metrics(o_result), compute_metrics(v_result)

    rows = [metrics_row(BASE, o_result, o_m), metrics_row(CANDIDATE, v_result, v_m)]
    delta = {"estrategia": "delta (candidata - original)"}
    for col in rows[0]:
        if col != "estrategia":
            a, b = rows[0][col], rows[1][col]
            delta[col] = round(b - a, 3) if a is not None and b is not None else None
    rows.append(delta)
    table = pd.DataFrame(rows)

    out_csv = ROOT / "reports" / f"{args.out_name}.csv"
    table.to_csv(out_csv, index=False)

    # ---------------- veredicto pre-registrado
    checks: list[tuple[str, bool]] = []
    if v_m["n_trades"] and o_m["n_trades"]:
        checks.append(("expR candidata > original",
                       v_m["expectancy_r"] > o_m["expectancy_r"]))
        checks.append(("drawdown candidata <= original",
                       v_m["max_drawdown"] <= o_m["max_drawdown"]))
    sample_ok = v_m["n_trades"] >= MIN_CANDIDATE_TRADES

    L = [
        "=" * 74,
        "  VALIDACIÓN OUT-OF-SAMPLE — original vs candidata no_midday",
        f"  Dataset: {args.data}",
        f"  Período: {df.index[0]} -> {df.index[-1]} "
        f"({df.index.normalize().nunique()} sesiones RTH)",
        "=" * 74,
    ]
    if overlaps_in_sample:
        L += [
            "",
            "  *** ADVERTENCIA: este rango SE SOLAPA con el período in-sample",
            f"  *** (dic-2025 -> jun-2026) usado para diseñar el filtro.",
            "  *** Esta corrida NO cuenta como validación out-of-sample.",
        ]
    L += ["", f"  {'métrica':<24} {'original':>12} {'no_midday':>12} {'delta':>10}"]
    labels = [
        ("trades", "trades"), ("pnl_net", "PnL neto"), ("profit_factor", "profit factor"),
        ("winrate_pct", "winrate %"), ("expectancy_r", "expectancia R"),
        ("max_drawdown_usd", "drawdown $"), ("max_drawdown_pct", "drawdown %"),
        ("racha_perdedora_max", "racha perdedora"), ("salidas_target", "targets"),
        ("salidas_stop", "stops"), ("salidas_flatten", "session_flatten"),
    ]
    for col, label in labels:
        o_v, v_v, d_v = rows[0][col], rows[1][col], rows[2][col]
        L.append(f"  {label:<24} {str(o_v):>12} {str(v_v):>12} {str(d_v):>10}")

    L += ["", "-" * 74, "  CONSISTENCIA POR MES", "-" * 74]
    mt = monthly_table(o_trades, v_trades)
    if not mt.empty:
        L.append(f"  {'mes':<10} {'PnL orig':>10} {'PnL nomid':>10} "
                 f"{'expR o':>8} {'expR v':>8} {'n o':>4} {'n v':>4}")
        for mes, r in mt.iterrows():
            L.append(f"  {mes:<10} {r['pnl_orig']:>10.2f} {r['pnl_nomid']:>10.2f} "
                     f"{r['expr_orig']:>8.3f} {r['expr_nomid']:>8.3f} "
                     f"{int(r['n_orig']):>4} {int(r['n_nomid']):>4}")
        improves = [str(m) for m, r in mt.iterrows() if r["pnl_nomid"] > r["pnl_orig"]]
        worsens = [str(m) for m, r in mt.iterrows() if r["pnl_nomid"] < r["pnl_orig"]]
        ties = len(mt) - len(improves) - len(worsens)
        L.append(f"  -> mejora el PnL en {len(improves)} de {len(mt)} meses: "
                 f"{', '.join(improves) if improves else '(ninguno)'}")
        L.append(f"  -> empeora en {len(worsens)}: "
                 f"{', '.join(worsens) if worsens else '(ninguno)'}"
                 + (f" | empata en {ties}" if ties else ""))

    L += ["", "-" * 74, "  DESCOMPOSICIÓN DEL DELTA DE PnL", "-" * 74]
    L += decompose(o_trades, v_trades)

    L += ["", "-" * 74, "  VEREDICTO (criterio pre-registrado en docs/strategy_decision_log.md)", "-" * 74]
    for label, passed in checks:
        L.append(f"  [{'CUMPLE' if passed else 'NO CUMPLE'}] {label}")
    if not checks:
        L.append("  [SIN DATOS] alguna estrategia no generó trades")
    L.append(f"  [{'OK' if sample_ok else 'PROVISIONAL'}] muestra de la candidata: "
             f"{v_m['n_trades']} trades (mínimo orientativo {MIN_CANDIDATE_TRADES})")
    if overlaps_in_sample:
        L.append("  [INVÁLIDO] los datos se solapan con el período in-sample")
    elif checks and all(p for _, p in checks) and sample_ok:
        L.append("  => La candidata CUMPLE el criterio: candidata a promoción "
                 "(registrar en el decision log).")
    elif checks and not all(p for _, p in checks):
        L.append("  => La candidata NO cumple el criterio pre-registrado: "
                 "corresponde descartarla (registrar en el decision log).")
    else:
        L.append("  => Veredicto provisional: juntar más historia antes de decidir.")
    L.append("=" * 74)

    summary = "\n".join(L)
    out_txt = ROOT / "reports" / f"{args.out_name}_summary.txt"
    out_txt.write_text(summary, encoding="utf-8")
    print()
    print(summary)
    print(f"\nArchivos: {out_csv} | {out_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
