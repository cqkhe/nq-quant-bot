#!/usr/bin/env python
"""Validación de la variante near_vwap contra su base no_midday.

Corre ambas estrategias sobre los datasets indicados y compara métricas
completas, performance mensual, long/short y los trades que la nueva regla
filtra. Genera:

    reports/near_vwap_variant_comparison.csv
    reports/near_vwap_variant_summary.txt

ADVERTENCIA METODOLÓGICA (impresa también en el summary): la hipótesis
near_vwap se derivó del diagnóstico sobre 2025-01→2025-11, y el dataset
completo contiene además el período de diseño de no_midday. NINGUNO de estos
datasets es out-of-sample limpio para esta variante: esta corrida mide si el
filtro se comporta con sentido, no lo valida. La validación real requiere
datos no usados (2024 o jul-2026+).

Uso:
    python scripts/validate_near_vwap.py
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

BASE = "daytrading_vwap_liquidity_rr2_no_midday"
CANDIDATE = "daytrading_vwap_liquidity_rr2_no_midday_near_vwap"

DATASETS = [
    ("A_oos_2025", "data/processed/MNQ_2025_01_2025_11_oos_clean.csv"),
    ("B_completo", "data/processed/MNQ_2025_01_2026_06_1m_ninjatrader_combined_clean.csv"),
]


def run_strategy(name, df, config, contract, logger):
    strategy = create_strategy(name, config.strategy_params.get(name), contract)
    result = BacktestEngine(config, contract, strategy, logger).run(df)
    trades = pd.DataFrame([asdict(t) for t in result.trades])
    if not trades.empty:
        trades["entry_time"] = pd.to_datetime(trades["entry_time"])
    return result, trades


def metrics_row(dataset, name, m):
    exits = m.get("exits_by_reason", {})
    return {
        "dataset": dataset,
        "estrategia": name,
        "trades": m["n_trades"],
        "pnl_net": round(m["total_net_pnl"], 2),
        "profit_factor": round(m["profit_factor"], 3) if m["n_trades"] else None,
        "winrate_pct": round(m["winrate_pct"], 2) if m["n_trades"] else None,
        "expectancy_r": round(m["expectancy_r"], 3) if m["n_trades"] else None,
        "max_drawdown_usd": round(m["max_drawdown"], 2),
        "max_drawdown_pct": round(m["max_drawdown_pct"], 2),
        "racha_perdedora_max": m.get("max_consecutive_losses", 0),
        "targets": exits.get("target", 0) + exits.get("target_gap", 0),
        "stops": exits.get("stop", 0) + exits.get("stop_gap", 0),
        "session_flatten": exits.get("session_flatten", 0),
        "n_long": m.get("n_long", 0),
        "n_short": m.get("n_short", 0),
    }


def monthly(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["pnl", "expr", "n"])
    key = trades["entry_time"].dt.to_period("M").astype(str).to_numpy()
    g = trades.groupby(key)
    return pd.DataFrame({"pnl": g["pnl_net"].sum().round(2),
                         "expr": g["r_multiple"].mean().round(3), "n": g.size()})


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    ap.add_argument("--symbol", default="MNQ")
    args = ap.parse_args()

    logger = setup_logger(log_dir=ROOT / "logs", level=logging.WARNING)
    config = Config.from_yaml(args.config)
    contract = config.contract(args.symbol)

    all_rows: list[dict] = []
    sections: list[str] = []
    verdict_data: dict[str, dict] = {}

    for tag, rel_path in DATASETS:
        path = ROOT / rel_path
        if not path.exists():
            print(f"AVISO: no existe {rel_path}, se omite")
            continue
        df = filter_to_trade_session(load_ohlcv_csv(path, logger), config.session)
        print(f"[{tag}] {df.index[0]} -> {df.index[-1]} | corriendo ambas estrategias ...")

        b_result, b_trades = run_strategy(BASE, df, config, contract, logger)
        c_result, c_trades = run_strategy(CANDIDATE, df, config, contract, logger)
        b_m, c_m = compute_metrics(b_result), compute_metrics(c_result)

        rows = [metrics_row(tag, BASE, b_m), metrics_row(tag, CANDIDATE, c_m)]
        delta = {"dataset": tag, "estrategia": "delta"}
        for col in rows[0]:
            if col not in ("dataset", "estrategia"):
                a, b = rows[0][col], rows[1][col]
                delta[col] = round(b - a, 3) if a is not None and b is not None else None
        rows.append(delta)
        all_rows.extend(rows)

        # trades filtrados por la nueva regla (y nuevos por re-secuenciación)
        b_keys, c_keys = set(b_trades["entry_time"]), set(c_trades["entry_time"])
        removed = b_trades[~b_trades["entry_time"].isin(c_keys)]
        added = c_trades[~c_trades["entry_time"].isin(b_keys)]

        mb, mc = monthly(b_trades), monthly(c_trades)
        mm = mb.join(mc, how="outer", lsuffix="_base", rsuffix="_near").fillna(0)
        months_better = int((mm["pnl_near"] > mm["pnl_base"]).sum())

        verdict_data[tag] = {
            "b": rows[0], "c": rows[1],
            "removed_n": len(removed),
            "removed_pnl": round(float(removed["pnl_net"].sum()), 2) if len(removed) else 0.0,
            "removed_expr": round(float(removed["r_multiple"].mean()), 3) if len(removed) else None,
            "added_n": len(added),
            "added_pnl": round(float(added["pnl_net"].sum()), 2) if len(added) else 0.0,
            "months_better": months_better,
            "months_total": len(mm),
        }

        S = ["", "=" * 76, f"  DATASET {tag}: {rel_path}",
             f"  {df.index[0]} -> {df.index[-1]} ({df.index.normalize().nunique()} sesiones)",
             "=" * 76,
             f"  {'métrica':<22} {'no_midday':>12} {'near_vwap':>12} {'delta':>10}"]
        labels = [("trades", "trades"), ("pnl_net", "PnL neto"),
                  ("profit_factor", "profit factor"), ("winrate_pct", "winrate %"),
                  ("expectancy_r", "expectancia R"), ("max_drawdown_usd", "drawdown $"),
                  ("racha_perdedora_max", "racha perdedora"), ("targets", "targets"),
                  ("stops", "stops"), ("session_flatten", "session_flatten"),
                  ("n_long", "long"), ("n_short", "short")]
        for col, label in labels:
            S.append(f"  {label:<22} {str(rows[0][col]):>12} {str(rows[1][col]):>12} "
                     f"{str(rows[2][col]):>10}")
        S += ["", f"  Trades de no_midday eliminados por la regla near_vwap: "
                  f"{len(removed)} (PnL que tenían: {verdict_data[tag]['removed_pnl']:+,.2f}, "
                  f"expR {verdict_data[tag]['removed_expr']})",
              f"  Trades nuevos por re-secuenciación del slot: {len(added)} "
              f"(PnL {verdict_data[tag]['added_pnl']:+,.2f})",
              "", "  Performance por mes (PnL / expR / n):"]
        S.append(f"  {'mes':<10} {'PnL base':>10} {'PnL near':>10} {'expR b':>8} "
                 f"{'expR n':>8} {'n b':>4} {'n n':>4}")
        for mes, r in mm.iterrows():
            S.append(f"  {mes:<10} {r['pnl_base']:>10.2f} {r['pnl_near']:>10.2f} "
                     f"{r['expr_base']:>8.3f} {r['expr_near']:>8.3f} "
                     f"{int(r['n_base']):>4} {int(r['n_near']):>4}")
        S.append(f"  -> near_vwap mejora el PnL en {months_better} de {len(mm)} meses")
        sections.extend(S)

    table = pd.DataFrame(all_rows)
    out_csv = ROOT / "reports" / "near_vwap_variant_comparison.csv"
    table.to_csv(out_csv, index=False)

    # ---------------- veredicto
    V = ["", "=" * 76, "  VEREDICTO (preguntas del experimento)", "=" * 76]
    for tag, d in verdict_data.items():
        b, c = d["b"], d["c"]
        V += [
            f"  [{tag}]",
            f"    ¿Mejora PnL?            {'sí' if c['pnl_net'] > b['pnl_net'] else 'no'} "
            f"({b['pnl_net']:+,.2f} -> {c['pnl_net']:+,.2f})",
            f"    ¿Mejora profit factor?  {'sí' if (c['profit_factor'] or 0) > (b['profit_factor'] or 0) else 'no'} "
            f"({b['profit_factor']} -> {c['profit_factor']})",
            f"    ¿Mejora expectancia R?  {'sí' if (c['expectancy_r'] or 0) > (b['expectancy_r'] or 0) else 'no'} "
            f"({b['expectancy_r']} -> {c['expectancy_r']})",
            f"    ¿Reduce drawdown?       {'sí' if c['max_drawdown_usd'] < b['max_drawdown_usd'] else 'no'} "
            f"({b['max_drawdown_usd']:,.2f} -> {c['max_drawdown_usd']:,.2f})",
            f"    Muestra: {b['trades']} -> {c['trades']} trades "
            f"({(c['trades'] - b['trades']) / b['trades'] * 100:+.0f}%)",
            f"    Trades eliminados: {d['removed_n']} con PnL {d['removed_pnl']:+,.2f} "
            f"(expR {d['removed_expr']}) | nuevos: {d['added_n']} ({d['added_pnl']:+,.2f})",
            f"    Consistencia mensual: mejora en {d['months_better']} de {d['months_total']} meses",
            "",
        ]
    V += [
        "-" * 76,
        "  LECTURA (estructural vs recorte de trades):",
        "  * Estructural si: expR y PF suben, DD baja, los trades eliminados eran",
        "    claramente negativos, y la mejora aparece en AMBOS datasets y en la",
        "    mayoría de los meses.",
        "  * Solo recorte si: el PnL cae junto con la muestra o el expR no mejora.",
        "",
        "  ADVERTENCIA: ninguno de estos datasets es out-of-sample limpio para",
        "  near_vwap (la hipótesis salió del dataset A; el B contiene el período",
        "  de diseño de no_midday). Validación real pendiente: 2024 o jul-2026+.",
        "=" * 76,
    ]
    summary = "\n".join(sections + V)
    out_txt = ROOT / "reports" / "near_vwap_variant_summary.txt"
    out_txt.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"\nArchivos: {out_csv} | {out_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
