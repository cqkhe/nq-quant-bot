#!/usr/bin/env python
"""Comparación controlada de estrategias/variantes sobre un mismo dataset.

Corre cada estrategia con el pipeline estándar (mismos datos, misma config de
riesgo/ejecución/sesión) y compara las métricas lado a lado. Genera:

    reports/strategy_variants_comparison.csv
    reports/strategy_variants_summary.txt

Notas metodológicas (también incluidas en el summary):
  * Es una RE-SIMULACIÓN, no un filtrado de los trades originales: al liberar
    el "una posición a la vez", una variante puede tomar trades que la
    original no tomó.
  * Si los filtros de una variante se derivaron del mismo dataset, su mejora
    in-sample es esperable por construcción. Validar fuera de muestra.

Uso:
    python scripts/compare_strategies.py --data data/processed/ARCHIVO.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
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
DEFAULT_STRATEGIES = [
    BASE,
    "daytrading_vwap_liquidity_rr2_no_midday",
    "daytrading_vwap_liquidity_rr2_longs_only",
    "daytrading_vwap_liquidity_rr2_morning_only",
    "daytrading_vwap_liquidity_rr2_no_midday_longs_only",
]


def run_one(name: str, df: pd.DataFrame, config: Config, contract, logger) -> dict:
    strategy = create_strategy(name, config.strategy_params.get(name), contract)
    result = BacktestEngine(config, contract, strategy, logger).run(df)
    m = compute_metrics(result)
    exits = m.get("exits_by_reason", {})
    hours = Counter(t.entry_time.hour for t in result.trades)

    row = {
        "estrategia": name,
        "trades": m["n_trades"],
        "pnl_net": round(m["total_net_pnl"], 2),
        "profit_factor": round(m["profit_factor"], 3) if m["n_trades"] else None,
        "winrate_pct": round(m["winrate_pct"], 2) if m["n_trades"] else None,
        "expectancy_r": round(m["expectancy_r"], 3) if m["n_trades"] else None,
        "max_drawdown_usd": round(m["max_drawdown"], 2),
        "max_drawdown_pct": round(m["max_drawdown_pct"], 2),
        "racha_perdedora_max": m.get("max_consecutive_losses", 0),
        "n_long": m.get("n_long", 0),
        "n_short": m.get("n_short", 0),
        "salidas_stop": exits.get("stop", 0) + exits.get("stop_gap", 0),
        "salidas_target": exits.get("target", 0) + exits.get("target_gap", 0),
        "salidas_flatten": exits.get("session_flatten", 0),
    }
    for hour in range(9, 16):
        row[f"trades_{hour:02d}h"] = hours.get(hour, 0)
    return row


def build_summary(table: pd.DataFrame, data_file: str, period: str, n_sessions: int) -> str:
    base = table.iloc[0]
    lines = [
        "=" * 78,
        "  COMPARACIÓN DE VARIANTES — misma data, misma config de riesgo/ejecución",
        f"  Dataset:  {data_file}",
        f"  Período:  {period}  ({n_sessions} sesiones RTH)",
        "=" * 78,
        "",
        f"  {'estrategia':<52} {'trades':>6} {'PnL':>10} {'PF':>6} {'WR%':>6} {'expR':>7} {'DD$':>9} {'racha':>5}",
        "  " + "-" * 106,
    ]
    for _, r in table.iterrows():
        lines.append(
            f"  {r['estrategia']:<52} {r['trades']:>6} {r['pnl_net']:>10.2f} "
            f"{r['profit_factor'] if r['profit_factor'] is not None else '-':>6} "
            f"{r['winrate_pct'] if r['winrate_pct'] is not None else '-':>6} "
            f"{r['expectancy_r'] if r['expectancy_r'] is not None else '-':>7} "
            f"{r['max_drawdown_usd']:>9.2f} {r['racha_perdedora_max']:>5}"
        )
    lines += ["", "-" * 78, "  DELTAS vs ORIGINAL", "-" * 78]
    for _, r in table.iloc[1:].iterrows():
        d_trades = r["trades"] - base["trades"]
        d_pnl = r["pnl_net"] - base["pnl_net"]
        d_expr = (r["expectancy_r"] or 0) - (base["expectancy_r"] or 0)
        d_dd = r["max_drawdown_usd"] - base["max_drawdown_usd"]
        d_racha = r["racha_perdedora_max"] - base["racha_perdedora_max"]
        lines.append(
            f"  {r['estrategia']}\n"
            f"      trades {d_trades:+d} ({d_trades / base['trades'] * 100:+.0f}%) | "
            f"PnL {d_pnl:+.2f} | expR {d_expr:+.3f} | DD {d_dd:+.2f} | racha {d_racha:+d}"
        )
    lines += [
        "",
        "-" * 78,
        "  CÓMO LEER ESTO (robustez vs. menos trades)",
        "-" * 78,
        "  * Un filtro aporta robustez si SUBE la expectancia por trade (expR) y",
        "    BAJA el drawdown y la racha perdedora, no solo si sube el PnL.",
        "  * Un filtro que solo reduce trades manteniendo expR similar no agrega",
        "    edge: recorta actividad (y la muestra estadística).",
        "  * ADVERTENCIA IN-SAMPLE: estos filtros se derivaron del análisis de",
        "    ESTE MISMO dataset. Su mejora aquí es esperable por construcción.",
        "    Ninguna variante debe adoptarse sin validarla en datos nuevos",
        "    (otros meses / otro régimen de mercado).",
        "=" * 78,
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="CSV OHLCV procesado (data/processed/...)")
    ap.add_argument("--symbol", default="MNQ")
    ap.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES),
                    help="Lista separada por comas; la primera es la base de comparación")
    ap.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    ap.add_argument("--out-dir", default=str(ROOT / "reports"))
    args = ap.parse_args()

    logger = setup_logger(log_dir=ROOT / "logs", level=logging.WARNING)  # consola silenciosa
    config = Config.from_yaml(args.config)
    contract = config.contract(args.symbol)

    df = load_ohlcv_csv(args.data, logger)
    df = filter_to_trade_session(df, config.session)
    period = f"{df.index[0]} -> {df.index[-1]}"
    n_sessions = df.index.normalize().nunique()
    print(f"Dataset: {len(df):,} barras RTH | {period} | {n_sessions} sesiones\n")

    names = [s.strip() for s in args.strategies.split(",") if s.strip()]
    rows = []
    for name in names:
        print(f"  corriendo {name} ...")
        rows.append(run_one(name, df, config, contract, logger))

    table = pd.DataFrame(rows)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "strategy_variants_comparison.csv"
    txt_path = out_dir / "strategy_variants_summary.txt"
    table.to_csv(csv_path, index=False)

    summary = build_summary(table, args.data, period, n_sessions)
    txt_path.write_text(summary, encoding="utf-8")
    print()
    print(summary)
    print(f"\nArchivos: {csv_path} | {txt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
