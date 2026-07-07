#!/usr/bin/env python
"""Validación de H002: base atr_filter vs variante dynamic_exit_h002.

Corre ambas sobre los tres datasets de diseño y mide, además de las métricas
estándar: los early_exits (n, PnL, R, MFE/MAE reconstruidos), el
CONTRAFACTUAL exacto (qué destino tuvo en la base cada trade que la variante
cortó — la medición limpia de "¿mata ganadores?"), performance mensual,
horaria y por régimen causal (Market Regime Engine), y el veredicto del
Decision Engine por dataset.

ADVERTENCIA (pre-registrada en la ficha H002): los tres datasets son de
DISEÑO — la regla salió del diagnóstico sobre 2025-2026 y 2024 fue declarado
re-chequeo de diseño en la ficha. El OOS oficial sigue siendo jul-2026+ o
2023: esta corrida documenta TESTED, no valida para promoción.

Uso:
    python scripts/validate_h002.py

Genera:
    reports/h002_dynamic_exit_comparison.csv
    reports/h002_dynamic_exit_summary.md
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
from nqbot.regime import classify_regimes, label_trades      # noqa: E402
from nqbot.research import ExperimentMetrics, evaluate       # noqa: E402
from nqbot.strategies.registry import create_strategy        # noqa: E402
from nqbot.utils.logger import setup_logger                  # noqa: E402
from nqbot.utils.sessions import filter_to_trade_session     # noqa: E402

BASE = "daytrading_vwap_liquidity_rr2_no_midday_atr_filter"
VARIANT = "daytrading_vwap_liquidity_rr2_no_midday_atr_filter_dynamic_exit_h002"

DATASETS = [
    ("2024", "data/processed/MNQ_2024_full_1m_ninjatrader_combined_clean.csv"),
    ("2025_ene_nov", "data/processed/MNQ_2025_01_2025_11_oos_clean.csv"),
    ("2025_2026_completo", "data/processed/MNQ_2025_01_2026_06_1m_ninjatrader_combined_clean.csv"),
]


def run_strategy(name, df, config, contract, logger):
    strategy = create_strategy(name, config.strategy_params.get(name), contract)
    result = BacktestEngine(config, contract, strategy, logger).run(df)
    trades = pd.DataFrame([asdict(t) for t in result.trades])
    if not trades.empty:
        trades["entry_time"] = pd.to_datetime(trades["entry_time"])
        trades["exit_time"] = pd.to_datetime(trades["exit_time"])
    return result, trades


def metrics_row(dataset, name, m, trades):
    exits = m.get("exits_by_reason", {})
    early = trades[trades["exit_reason"] == "early_exit"] if len(trades) else pd.DataFrame()
    return {
        "dataset": dataset, "estrategia": name,
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
        "early_exits": len(early),
        "early_exit_pnl": round(float(early["pnl_net"].sum()), 2) if len(early) else 0.0,
        "early_exit_r_prom": round(float(early["r_multiple"].mean()), 3) if len(early) else None,
    }


def early_exit_excursions(early: pd.DataFrame, df: pd.DataFrame) -> tuple[float, float]:
    """MFE/MAE promedio (en R) de los early_exits, reconstruidos de los 1m."""
    if early.empty:
        return float("nan"), float("nan")
    mfes, maes = [], []
    for t in early.itertuples(index=False):
        d = int(t.direction)
        r_pts = (t.entry_price - t.stop_price) * d
        seg = df.loc[t.entry_time: t.exit_time]
        if r_pts <= 0 or seg.empty:
            continue
        if d > 0:
            mfes.append(float((seg["high"] - t.entry_price).max() / r_pts))
            maes.append(float((t.entry_price - seg["low"]).max() / r_pts))
        else:
            mfes.append(float((t.entry_price - seg["low"]).max() / r_pts))
            maes.append(float((seg["high"] - t.entry_price).max() / r_pts))
    return (round(sum(mfes) / len(mfes), 3), round(sum(maes) / len(maes), 3)) if mfes else (float("nan"),) * 2


def regime_table(trades: pd.DataFrame, labeled: pd.DataFrame, column: str) -> pd.DataFrame:
    joined = label_trades(trades, labeled)
    grouped = joined.groupby(joined[column].fillna("no_clasificable"))
    return pd.DataFrame({
        "n": grouped.size(),
        "expR": grouped["r_multiple"].mean().round(3),
        "pnl": grouped["pnl_net"].sum().round(2),
    })


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    ap.add_argument("--symbol", default="MNQ")
    args = ap.parse_args()

    logger = setup_logger(log_dir=ROOT / "logs", level=logging.WARNING)
    config = Config.from_yaml(args.config)
    contract = config.contract(args.symbol)

    all_rows, S, verdicts = [], [], {}
    for tag, rel_path in DATASETS:
        path = ROOT / rel_path
        if not path.exists():
            print(f"AVISO: falta {rel_path}, se omite")
            continue
        df = filter_to_trade_session(load_ohlcv_csv(path, logger), config.session)
        print(f"[{tag}] corriendo base y variante H002 ...")
        b_result, b_trades = run_strategy(BASE, df, config, contract, logger)
        v_result, v_trades = run_strategy(VARIANT, df, config, contract, logger)
        b_m, v_m = compute_metrics(b_result), compute_metrics(v_result)

        rows = [metrics_row(tag, BASE, b_m, b_trades),
                metrics_row(tag, VARIANT, v_m, v_trades)]
        delta = {"dataset": tag, "estrategia": "delta"}
        for col in rows[0]:
            if col not in ("dataset", "estrategia"):
                a, b = rows[0][col], rows[1][col]
                delta[col] = round(b - a, 3) if a is not None and b is not None else None
        rows.append(delta)
        all_rows.extend(rows)

        # ---------------- contrafactual: destino en la BASE de los trades cortados
        early = v_trades[v_trades["exit_reason"] == "early_exit"]
        matched = b_trades[b_trades["entry_time"].isin(set(early["entry_time"]))]
        counterfactual = matched["exit_reason"].value_counts().to_dict()
        would_target = counterfactual.get("target", 0) + counterfactual.get("target_gap", 0)
        pct_would_target = would_target / len(matched) * 100 if len(matched) else 0.0
        # beneficio directo de la regla = lo que hicieron los early_exits MENOS lo
        # que hicieron esos MISMOS trades en la base (positivo = la regla ahorró)
        rule_benefit = float(
            early[early["entry_time"].isin(set(matched["entry_time"]))]["pnl_net"].sum()
        ) - float(matched["pnl_net"].sum())
        new_trades = v_trades[~v_trades["entry_time"].isin(set(b_trades["entry_time"]))]
        lost_trades = b_trades[~b_trades["entry_time"].isin(set(v_trades["entry_time"]))]
        mfe_prom, mae_prom = early_exit_excursions(early, df)

        # ---------------- tablas auxiliares
        month_v = v_trades.groupby(v_trades["entry_time"].dt.to_period("M").astype(str).to_numpy())
        month_b = b_trades.groupby(b_trades["entry_time"].dt.to_period("M").astype(str).to_numpy())
        monthly = pd.DataFrame({
            "pnl_base": month_b["pnl_net"].sum().round(2),
            "pnl_h002": month_v["pnl_net"].sum().round(2),
            "expr_base": month_b["r_multiple"].mean().round(3),
            "expr_h002": month_v["r_multiple"].mean().round(3),
        }).fillna(0)
        hourly = pd.DataFrame({
            "pnl_base": b_trades.groupby(b_trades["entry_time"].dt.hour)["pnl_net"].sum().round(2),
            "pnl_h002": v_trades.groupby(v_trades["entry_time"].dt.hour)["pnl_net"].sum().round(2),
        }).fillna(0)

        labeled = classify_regimes(df)
        reg_vol = regime_table(v_trades, labeled, "vol_regime").join(
            regime_table(b_trades, labeled, "vol_regime"), lsuffix="_h002", rsuffix="_base")
        reg_trend = regime_table(v_trades, labeled, "trend_regime").join(
            regime_table(b_trades, labeled, "trend_regime"), lsuffix="_h002", rsuffix="_base")

        # ---------------- Decision Engine (los 3 datasets son de DISEÑO)
        decision = evaluate(ExperimentMetrics(
            source=f"{tag} ({rel_path})", strategy=VARIANT,
            n_trades=v_m["n_trades"], pnl_net=v_m["total_net_pnl"],
            profit_factor=v_m.get("profit_factor"), expectancy_r=v_m.get("expectancy_r"),
            winrate_pct=v_m.get("winrate_pct"), max_drawdown_usd=v_m["max_drawdown"],
            max_drawdown_pct=v_m["max_drawdown_pct"],
            max_losing_streak=v_m.get("max_consecutive_losses"),
            pnl_without_top5=round(v_m["total_net_pnl"] - float(
                v_trades[v_trades["pnl_net"] > 0]["pnl_net"].nlargest(5).sum()), 2),
            is_out_of_sample=False, overlaps_design_period=True,
        ))
        verdicts[tag] = {"decision": decision, "pct_would_target": pct_would_target,
                         "rule_benefit": rule_benefit, "early_n": len(early),
                         "matched_n": len(matched)}

        # ---------------- sección markdown
        S += ["", "=" * 76, f"## Dataset {tag} — `{rel_path}`",
              f"{df.index[0]} → {df.index[-1]} ({df.index.normalize().nunique()} sesiones)", ""]
        cmp_df = pd.DataFrame(rows).drop(columns=["dataset"]).set_index("estrategia").T
        S += [cmp_df.to_markdown(), ""]
        S += [f"**Early exits:** {len(early)} | PnL {rows[1]['early_exit_pnl']:+,.2f} | "
              f"R promedio {rows[1]['early_exit_r_prom']} | MFE prom {mfe_prom}R | MAE prom {mae_prom}R", "",
              f"**Contrafactual (destino en la base de los {len(matched)} trades cortados):** "
              f"{counterfactual} → {pct_would_target:.1f}% habría llegado a target "
              f"(límite de la ficha: 20%)", "",
              f"**Beneficio directo de la regla en trades compartidos** (PnL de los "
              f"early_exits − PnL de esos mismos trades en la base): {rule_benefit:+,.2f} "
              f"(positivo = la regla ahorró)", "",
              f"**Trades nuevos por re-secuenciación:** {len(new_trades)} "
              f"(PnL {float(new_trades['pnl_net'].sum()):+,.2f}) | "
              f"**trades de la base perdidos:** {len(lost_trades)} "
              f"(PnL que tenían: {float(lost_trades['pnl_net'].sum()):+,.2f})", "",
              "### Por mes", "", monthly.to_markdown(), "",
              "### Por hora", "", hourly.to_markdown(), "",
              "### Por régimen causal (volatilidad)", "", reg_vol.to_markdown(), "",
              "### Por régimen causal (tendencia)", "", reg_trend.to_markdown(), "",
              f"### Decision Engine: **{decision.status.value}**", ""]
        S += [f"- {r}" for r in decision.reasons]

    table = pd.DataFrame(all_rows)
    out_csv = ROOT / "reports" / "h002_dynamic_exit_comparison.csv"
    table.to_csv(out_csv, index=False)

    header = [
        "# H002 — Resultado de la variante dynamic_exit (base: atr_filter)",
        "",
        "Regla congelada: early_exit si la posición lleva >= 30 min y MFE < +0.5R.",
        "Prueba de INVESTIGACIÓN sobre datasets de diseño: no valida promoción;",
        "el OOS pre-registrado (jul-2026+ o 2023) sigue pendiente.",
    ]
    out_md = ROOT / "reports" / "h002_dynamic_exit_summary.md"
    out_md.write_text("\n".join(header + S), encoding="utf-8")
    print("\n".join(header + S))
    print(f"\nArchivos: {out_csv} | {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
