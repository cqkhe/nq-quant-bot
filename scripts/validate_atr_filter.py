#!/usr/bin/env python
"""Validación de la variante atr_filter contra su base no_midday.

Corre ambas estrategias sobre los datasets indicados y compara métricas
completas, performance mensual y horaria, long/short y los trades que el
filtro de ATR elimina. Genera:

    reports/atr_filter_variant_comparison.csv
    reports/atr_filter_variant_summary.txt

CAUSALIDAD: el ATR-20 se calcula como media de true range de las últimas 20
barras HASTA la barra de señal (rolling, sin ninguna información futura);
el fill ocurre en el open del minuto siguiente. El filtro usa únicamente
información disponible antes de la entrada.

ADVERTENCIA: la hipótesis salió de estos mismos datasets (el diagnóstico de
régimen usó A y B). Esta corrida mide comportamiento, no valida: la
validación real requiere datos no usados (2024 o jul-2026+).

Uso:
    # comportamiento por defecto: los dos datasets de diseño (A y B)
    python scripts/validate_atr_filter.py

    # dataset específico (p.ej. validación out-of-sample real con 2024):
    python scripts/validate_atr_filter.py --data data/processed/ARCHIVO_clean.csv
    # -> reports/atr_filter_validation_<nombre>.csv / _summary.txt

Con --data, el script detecta si el rango se solapa con el período de diseño
de la hipótesis (2025-01 -> 2026-06) y aplica el criterio PRE-REGISTRADO del
decision log: (1) expR(atr_filter) > expR(no_midday), (2) los trades
eliminados por ATR deben ser netos negativos en el período nuevo,
(3) >= 30 trades de la candidata.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
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
CANDIDATE = "daytrading_vwap_liquidity_rr2_no_midday_atr_filter"

DATASETS = [
    ("A_oos_2025", "data/processed/MNQ_2025_01_2025_11_oos_clean.csv"),
    ("B_completo", "data/processed/MNQ_2025_01_2026_06_1m_ninjatrader_combined_clean.csv"),
]

# Período del que salió la hipótesis del filtro ATR (diagnóstico de régimen
# sobre los datasets A y B). Datos que se solapen con esto NO son OOS.
DESIGN_START = pd.Timestamp("2025-01-01")
DESIGN_END = pd.Timestamp("2026-06-18")
MIN_CANDIDATE_TRADES = 30


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


def monthly(trades):
    if trades.empty:
        return pd.DataFrame(columns=["pnl", "expr", "n"])
    key = trades["entry_time"].dt.to_period("M").astype(str).to_numpy()
    g = trades.groupby(key)
    return pd.DataFrame({"pnl": g["pnl_net"].sum().round(2),
                         "expr": g["r_multiple"].mean().round(3), "n": g.size()})


def hourly_lines(b_trades, c_trades):
    out = [f"  {'hora':<6} {'PnL base':>10} {'PnL atr':>10} {'n b':>4} {'n c':>4}"]
    hb = b_trades.groupby(b_trades["entry_time"].dt.hour)["pnl_net"].agg(["sum", "size"])
    hc = c_trades.groupby(c_trades["entry_time"].dt.hour)["pnl_net"].agg(["sum", "size"])
    for hour in sorted(set(hb.index) | set(hc.index)):
        b_sum, b_n = (hb.loc[hour] if hour in hb.index else (0.0, 0))
        c_sum, c_n = (hc.loc[hour] if hour in hc.index else (0.0, 0))
        out.append(f"  {hour:02d}h    {b_sum:>10.2f} {c_sum:>10.2f} {int(b_n):>4} {int(c_n):>4}")
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", help="CSV procesado a validar (si se omite, usa los datasets de diseño A y B)")
    ap.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    ap.add_argument("--symbol", default="MNQ")
    args = ap.parse_args()

    logger = setup_logger(log_dir=ROOT / "logs", level=logging.WARNING)
    config = Config.from_yaml(args.config)
    contract = config.contract(args.symbol)

    if args.data:
        stem = Path(args.data).stem
        datasets = [(stem, args.data)]
        out_csv_name = f"atr_filter_validation_{stem}.csv"
        out_txt_name = f"atr_filter_validation_{stem}_summary.txt"
    else:
        datasets = DATASETS
        out_csv_name = "atr_filter_variant_comparison.csv"
        out_txt_name = "atr_filter_variant_summary.txt"

    all_rows, sections, verdict_data = [], [], {}
    for tag, rel_path in datasets:
        path = ROOT / rel_path
        if not path.exists():
            print(f"AVISO: no existe {rel_path}, se omite")
            continue
        df = filter_to_trade_session(load_ohlcv_csv(path, logger), config.session)
        print(f"[{tag}] corriendo ambas estrategias ...")
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

        b_keys, c_keys = set(b_trades["entry_time"]), set(c_trades["entry_time"])
        removed = b_trades[~b_trades["entry_time"].isin(c_keys)]
        added = c_trades[~c_trades["entry_time"].isin(b_keys)]
        mm = monthly(b_trades).join(monthly(c_trades), how="outer",
                                    lsuffix="_base", rsuffix="_atr").fillna(0)
        months_better = int((mm["pnl_atr"] > mm["pnl_base"]).sum())

        overlaps_design = bool(df.index[0] <= DESIGN_END and df.index[-1] >= DESIGN_START)
        verdict_data[tag] = {
            "b": rows[0], "c": rows[1],
            "removed_n": len(removed),
            "removed_pnl": round(float(removed["pnl_net"].sum()), 2) if len(removed) else 0.0,
            "removed_expr": round(float(removed["r_multiple"].mean()), 3) if len(removed) else None,
            "added_n": len(added),
            "added_pnl": round(float(added["pnl_net"].sum()), 2) if len(added) else 0.0,
            "months_better": months_better, "months_total": len(mm),
            "overlaps_design": overlaps_design,
        }

        S = ["", "=" * 76, f"  DATASET {tag}: {rel_path}",
             f"  {df.index[0]} -> {df.index[-1]} ({df.index.normalize().nunique()} sesiones)",
             ("  *** RANGO SOLAPADO con el período de diseño (2025-01 -> 2026-06): NO es OOS"
              if overlaps_design else
              "  Rango FUERA del período de diseño: corrida válida como out-of-sample"),
             "=" * 76,
             f"  {'métrica':<22} {'no_midday':>12} {'atr_filter':>12} {'delta':>10}"]
        labels = [("trades", "trades"), ("pnl_net", "PnL neto"),
                  ("profit_factor", "profit factor"), ("winrate_pct", "winrate %"),
                  ("expectancy_r", "expectancia R"), ("max_drawdown_usd", "drawdown $"),
                  ("racha_perdedora_max", "racha perdedora"), ("targets", "targets"),
                  ("stops", "stops"), ("session_flatten", "session_flatten"),
                  ("n_long", "long"), ("n_short", "short")]
        for col, label in labels:
            S.append(f"  {label:<22} {str(rows[0][col]):>12} {str(rows[1][col]):>12} "
                     f"{str(rows[2][col]):>10}")
        d = verdict_data[tag]
        S += ["", f"  Trades eliminados por ATR bajo: {d['removed_n']} "
                  f"(PnL que tenían: {d['removed_pnl']:+,.2f}, expR {d['removed_expr']})",
              f"  Trades nuevos por re-secuenciación: {d['added_n']} ({d['added_pnl']:+,.2f})",
              "", "  Performance por hora (PnL):"] + hourly_lines(b_trades, c_trades)
        S += ["", "  Performance por mes:",
              f"  {'mes':<10} {'PnL base':>10} {'PnL atr':>10} {'expR b':>8} {'expR a':>8} {'n b':>4} {'n a':>4}"]
        for mes, r in mm.iterrows():
            S.append(f"  {mes:<10} {r['pnl_base']:>10.2f} {r['pnl_atr']:>10.2f} "
                     f"{r['expr_base']:>8.3f} {r['expr_atr']:>8.3f} "
                     f"{int(r['n_base']):>4} {int(r['n_atr']):>4}")
        S.append(f"  -> atr_filter mejora el PnL en {months_better} de {len(mm)} meses")
        sections.extend(S)

    table = pd.DataFrame(all_rows)
    out_csv = ROOT / "reports" / out_csv_name
    table.to_csv(out_csv, index=False)

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
            f"    Eliminados por ATR: {d['removed_n']} con PnL {d['removed_pnl']:+,.2f} "
            f"(expR {d['removed_expr']}) | nuevos: {d['added_n']} ({d['added_pnl']:+,.2f})",
            f"    Consistencia mensual: mejora en {d['months_better']} de {d['months_total']} meses",
        ]
        # criterio pre-registrado (decision log) — aplica de verdad solo en OOS
        c1 = (c["expectancy_r"] or 0) > (b["expectancy_r"] or 0)
        c2 = d["removed_pnl"] < 0
        c3 = c["trades"] >= MIN_CANDIDATE_TRADES
        V += [
            f"    [{'CUMPLE' if c1 else 'NO CUMPLE'}] expR candidata > no_midday",
            f"    [{'CUMPLE' if c2 else 'NO CUMPLE'}] eliminados por ATR netos negativos "
            f"(el mecanismo replica)",
            f"    [{'OK' if c3 else 'PROVISIONAL'}] muestra candidata: {c['trades']} trades "
            f"(mínimo {MIN_CANDIDATE_TRADES})",
        ]
        if d["overlaps_design"]:
            V.append("    CONCLUSIÓN: resultado DESCRIPTIVO (datos solapados con el diseño; no es OOS)")
        elif c1 and c2 and c3:
            V.append("    CONCLUSIÓN: atr_filter MEJORA contra no_midday y CUMPLE el criterio "
                     "pre-registrado -> candidata a promoción (registrar en el decision log)")
        elif not (c1 and c2):
            V.append("    CONCLUSIÓN: atr_filter NO cumple el criterio pre-registrado en datos "
                     "nuevos -> corresponde descartarla (registrar en el decision log)")
        else:
            V.append("    CONCLUSIÓN: provisional — juntar más historia antes de decidir")
        V.append("")
    V += [
        "-" * 76,
        "  CAUSALIDAD: el ATR-20 es rolling sobre las 20 barras PREVIAS a la señal;",
        "  no usa ninguna información posterior a la entrada. Filtro operable.",
        "",
        "  CRITERIOS DE NO-ADOPCIÓN (pre-acordados):",
        "  * No adoptar si mejora solo por recortar demasiado la muestra.",
        "  * No adoptar si empeora mucho el PnL aunque mejore el drawdown.",
        "  * No adoptar si solo funciona en un período y falla en el otro.",
        "",
        "  ADVERTENCIA: la hipótesis salió de estos mismos datasets (diagnóstico",
        "  de régimen sobre A y B). Validación real pendiente: 2024 o jul-2026+.",
        "=" * 76,
    ]
    summary = "\n".join(sections + V)
    out_txt = ROOT / "reports" / out_txt_name
    out_txt.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"\nArchivos: {out_csv} | {out_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
