#!/usr/bin/env python
"""Diagnóstico de RÉGIMEN para no_midday: ¿el edge vive solo en días con
expansión/tendencia?

Dos familias de features por trade:

  CAUSALES (conocidas en la barra de señal, sin lookahead — candidatas a
  filtro operable):
    * rango inicial (OR de 30 min)
    * ATR intradía previo (media de true range, 20 barras)
    * rango acumulado del día HASTA la señal y ratio de expansión
      (rango acumulado / rango inicial)
    * pendiente de VWAP y de EMA200 hasta la señal (vs dirección del trade)
    * precio vs VWAP y vs EMA200 (por diseño: siempre a favor)
    * distancia al VWAP en la señal
    * estructura previa: máximos/mínimos crecientes o decrecientes (ventanas
      de 15 barras) vs dirección del trade
    * volumen relativo en la señal

  DE DÍA COMPLETO (usan información posterior: SOLO diagnóstico de régimen):
    * volatilidad del día (terciles del rango total)
    * tipo de día por eficiencia direccional (lateral / mixto / tendencial)
    * trade a favor o contra la dirección final del día

Además: cruce distancia-al-VWAP x expansión causal, para testear si la
distancia solo es tóxica en días sin expansión (la hipótesis que explicaría
la evidencia mixta de near_vwap).

Genera:
    reports/regime_diagnosis_no_midday.csv     trades con todo el contexto
    reports/regime_diagnosis_by_condition.csv  métricas por condición/bucket
    reports/regime_diagnosis_summary.txt       respuestas y ranking causal

Solo diagnóstico: no modifica estrategia, parámetros ni motor.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nqbot.backtesting.engine import BacktestEngine          # noqa: E402
from nqbot.config.settings import Config                     # noqa: E402
from nqbot.data.loader import load_ohlcv_csv                 # noqa: E402
from nqbot.strategies.registry import create_strategy        # noqa: E402
from nqbot.utils.logger import setup_logger                  # noqa: E402
from nqbot.utils.sessions import filter_to_trade_session     # noqa: E402

STRATEGY = "daytrading_vwap_liquidity_rr2_no_midday"
DATASETS = [
    ("A_oos_2025", "data/processed/MNQ_2025_01_2025_11_oos_clean.csv"),
    ("B_completo", "data/processed/MNQ_2025_01_2026_06_1m_ninjatrader_combined_clean.csv"),
]
TERCILES = ("bajo", "medio", "alto")


def tercile(s: pd.Series, labels=TERCILES) -> pd.Series:
    try:
        return pd.qcut(s, 3, labels=labels)
    except ValueError:
        return pd.Series(["medio"] * len(s), index=s.index)


# ------------------------------------------------------------------ features
def causal_context(prepared: pd.DataFrame) -> pd.DataFrame:
    """Features de régimen calculadas SOLO con información hasta cada barra."""
    ctx = prepared.copy()
    session = ctx.index.normalize()
    h, l, c = ctx["high"], ctx["low"], ctx["close"]

    prev_close = c.groupby(session).shift(1)
    true_range = pd.concat(
        [h - l, (h - prev_close).abs(), (l - prev_close).abs()], axis=1
    ).max(axis=1).fillna(h - l)
    ctx["atr20"] = true_range.rolling(20, min_periods=20).mean()

    ctx["range_so_far"] = h.groupby(session).cummax() - l.groupby(session).cummin()
    ctx["or_size"] = ctx["or_high"] - ctx["or_low"]
    ctx["expansion_ratio"] = ctx["range_so_far"] / ctx["or_size"].replace(0, np.nan)

    ctx["dist_vwap"] = c - ctx["vwap"]
    ctx["vwap_slope"] = ctx["vwap"].diff(10)
    ctx["ema200_slope"] = ctx["ema_trend"].diff(30)

    # estructura previa: ventana actual de 15 barras vs la anterior
    w = 15
    cur_high, cur_low = h.rolling(w).max(), l.rolling(w).min()
    ctx["making_hh"] = cur_high > cur_high.shift(w)
    ctx["making_ll"] = cur_low < cur_low.shift(w)
    return ctx


def build_trades_context(trades: pd.DataFrame, ctx: pd.DataFrame,
                         df: pd.DataFrame) -> pd.DataFrame:
    t = trades.copy()
    signal_times = t["entry_time"] - pd.Timedelta(minutes=1)
    cols = ["or_size", "atr20", "range_so_far", "expansion_ratio", "dist_vwap",
            "vwap_slope", "ema200_slope", "making_hh", "making_ll",
            "rel_volume", "vwap", "ema_trend", "close"]
    joined = ctx[cols].reindex(signal_times)
    joined.index = t.index
    t = pd.concat([t, joined], axis=1)

    d = t["direction"]
    t["lado"] = d.map({1: "long", -1: "short"})

    # ---- causales relativas a la dirección
    t["dist_vwap_favor"] = t["dist_vwap"] * d
    t["pendiente_vwap"] = np.where(t["vwap_slope"] * d > 0, "a favor", "en contra")
    t["pendiente_ema200"] = np.where(t["ema200_slope"] * d > 0, "a favor", "en contra")
    t["sobre_vwap"] = np.where(t["dist_vwap"] * d > 0, "a favor", "en contra")
    t["sobre_ema200"] = np.where((t["close"] - t["ema_trend"]) * d > 0, "a favor", "en contra")
    hh, ll = t["making_hh"].astype(bool), t["making_ll"].astype(bool)
    estructura = np.select(
        [hh & ~ll, ll & ~hh], ["alcista", "bajista"], default="mixta"
    )
    t["estructura_previa"] = np.select(
        [(estructura == "alcista") & (d > 0), (estructura == "bajista") & (d < 0),
         (estructura == "alcista") & (d < 0), (estructura == "bajista") & (d > 0)],
        ["a favor", "a favor", "en contra", "en contra"], default="mixta",
    )
    t["or_size_b"] = tercile(t["or_size"])
    t["atr20_b"] = tercile(t["atr20"])
    t["rango_acum_b"] = tercile(t["range_so_far"])
    t["expansion_b"] = tercile(t["expansion_ratio"])
    t["dist_vwap_b"] = tercile(t["dist_vwap_favor"])
    t["rel_volume_b"] = tercile(t["rel_volume"])

    # ---- día completo (solo diagnóstico)
    session = df.index.normalize()
    daily = df.groupby(session).agg(day_high=("high", "max"), day_low=("low", "min"),
                                    day_open=("open", "first"), day_close=("close", "last"))
    daily["day_range"] = daily["day_high"] - daily["day_low"]
    daily["day_eff"] = (daily["day_close"] - daily["day_open"]).abs() / daily["day_range"].replace(0, np.nan)
    daily["day_dir"] = np.sign(daily["day_close"] - daily["day_open"])
    t = t.join(daily[["day_range", "day_eff", "day_dir"]], on=t["entry_time"].dt.normalize())
    t["vol_dia"] = tercile(t["day_range"], ("baja", "media", "alta"))
    t["tipo_dia"] = np.where(t["day_eff"] >= 0.5, "tendencial",
                             np.where(t["day_eff"] <= 0.25, "lateral", "mixto"))
    t["vs_dia"] = np.where(t["day_dir"] * d > 0, "a favor del día", "contra el día")
    return t


# ------------------------------------------------------------------ métricas
def bucket_stats(g: pd.DataFrame) -> dict:
    pnl = g["pnl_net"]
    wins = pnl > 0
    gp, gl = float(pnl[wins].sum()), float(-pnl[pnl < 0].sum())
    ordered = g.sort_values("exit_time")["pnl_net"].cumsum()
    dd = float(-(ordered - ordered.cummax()).min()) if len(g) else 0.0
    exits = g["exit_reason"].value_counts()
    return {
        "trades": len(g),
        "pnl": round(float(pnl.sum()), 2),
        "profit_factor": round(gp / gl, 2) if gl > 0 else (float("inf") if gp > 0 else 0.0),
        "winrate_pct": round(float(wins.mean()) * 100, 1),
        "expr": round(float(g["r_multiple"].mean()), 3),
        "dd_aprox": round(dd, 2),
        "targets": int(exits.get("target", 0) + exits.get("target_gap", 0)),
        "stops": int(exits.get("stop", 0) + exits.get("stop_gap", 0)),
        "session_flatten": int(exits.get("session_flatten", 0)),
    }


CONDITIONS = [
    ("tipo_dia", "Tipo de día (eficiencia, DIAGNÓSTICO)"),
    ("vol_dia", "Volatilidad del día (DIAGNÓSTICO)"),
    ("vs_dia", "A favor / contra el día (DIAGNÓSTICO)"),
    ("expansion_b", "Expansión causal (rango acum./OR, terciles)"),
    ("rango_acum_b", "Rango acumulado hasta la señal (terciles)"),
    ("atr20_b", "ATR-20 previo (terciles)"),
    ("or_size_b", "Rango inicial (terciles)"),
    ("dist_vwap_b", "Distancia a VWAP (terciles)"),
    ("pendiente_vwap", "Pendiente VWAP vs dirección"),
    ("pendiente_ema200", "Pendiente EMA200 vs dirección"),
    ("estructura_previa", "Estructura previa (HH/LL) vs dirección"),
    ("rel_volume_b", "Volumen relativo (terciles)"),
    ("lado", "Long vs Short"),
]


def condition_table(t: pd.DataFrame, dataset: str) -> pd.DataFrame:
    rows = []
    for col, label in CONDITIONS:
        for bucket, g in t.groupby(col, observed=True):
            rows.append({"dataset": dataset, "condicion": label, "bucket": str(bucket),
                         **bucket_stats(g)})
    return pd.DataFrame(rows)


def interaction_lines(t: pd.DataFrame) -> list[str]:
    """expR en el cruce distancia-a-VWAP x expansión causal."""
    out = [f"  {'':<14} " + " ".join(f"{f'exp {e}':>16}" for e in TERCILES)]
    for dist_b in TERCILES:
        cells = []
        for exp_b in TERCILES:
            g = t[(t["dist_vwap_b"] == dist_b) & (t["expansion_b"] == exp_b)]
            cells.append(f"{g['r_multiple'].mean():+.2f}R n={len(g):<3}" if len(g) else "-".center(12))
        out.append(f"  dist {dist_b:<9} " + " ".join(f"{c:>16}" for c in cells))
    return out


def section(t: pd.DataFrame, cond: pd.DataFrame, label: str) -> list[str]:
    rows = cond[cond["condicion"] == label].sort_values("expr")
    out = []
    for _, r in rows.iterrows():
        flag = "  [n chico]" if r["trades"] < 15 else ""
        out.append(f"    {r['bucket']:<16} n={r['trades']:<4} PnL {r['pnl']:>+9.2f} "
                   f"expR {r['expr']:>+7.3f} WR {r['winrate_pct']:>5.1f}% PF {r['profit_factor']:<6} "
                   f"T/S/F {r['targets']}/{r['stops']}/{r['session_flatten']}{flag}")
    return out


def causal_ranking(cond: pd.DataFrame) -> list[str]:
    """Ranking de condiciones CAUSALES por spread de expR (buckets con n>=20)."""
    causal_labels = [lab for col, lab in CONDITIONS if "DIAGNÓSTICO" not in lab]
    rows = []
    for label in causal_labels:
        sub = cond[(cond["condicion"] == label) & (cond["trades"] >= 20)]
        if len(sub) >= 2:
            rows.append((label, sub["expr"].max() - sub["expr"].min(),
                         sub.loc[sub["expr"].idxmax(), "bucket"],
                         sub.loc[sub["expr"].idxmin(), "bucket"]))
    rows.sort(key=lambda x: -x[1])
    return [f"    {i + 1}. {label}: spread {spread:+.3f}R (mejor: {best} / peor: {worst})"
            for i, (label, spread, best, worst) in enumerate(rows[:6])]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    ap.add_argument("--symbol", default="MNQ")
    args = ap.parse_args()

    logger = setup_logger(log_dir=ROOT / "logs", level=logging.WARNING)
    config = Config.from_yaml(args.config)
    contract = config.contract(args.symbol)

    all_trades, all_cond, S = [], [], []
    for tag, rel_path in DATASETS:
        path = ROOT / rel_path
        if not path.exists():
            print(f"AVISO: no existe {rel_path}, se omite")
            continue
        df = filter_to_trade_session(load_ohlcv_csv(path, logger), config.session)
        print(f"[{tag}] corriendo {STRATEGY} y reconstruyendo régimen ...")
        strategy = create_strategy(STRATEGY, config.strategy_params.get(STRATEGY), contract)
        result = BacktestEngine(config, contract, strategy, logger).run(df)
        trades = pd.DataFrame([asdict(x) for x in result.trades])
        trades["entry_time"] = pd.to_datetime(trades["entry_time"])
        trades["exit_time"] = pd.to_datetime(trades["exit_time"])

        ctx = causal_context(strategy.prepare(df))
        t = build_trades_context(trades, ctx, df)
        t.insert(0, "dataset", tag)
        cond = condition_table(t, tag)
        all_trades.append(t)
        all_cond.append(cond)

        S += ["", "=" * 78, f"  DATASET {tag}: {rel_path}",
              f"  {len(t)} trades | PnL {t['pnl_net'].sum():+,.2f} | "
              f"expR {t['r_multiple'].mean():+.3f}", "=" * 78]
        for col, label in CONDITIONS:
            S += ["", f"  -- {label}"] + section(t, cond, label)
        S += ["", "  -- CRUCE distancia a VWAP x expansión causal (expR por celda)"]
        S += interaction_lines(t)
        S += ["", "  -- Ranking de condiciones CAUSALES (spread de expR, n>=20)"]
        S += causal_ranking(cond)

    trades_df = pd.concat(all_trades, ignore_index=True)
    cond_df = pd.concat(all_cond, ignore_index=True)
    out = ROOT / "reports"
    trades_df.to_csv(out / "regime_diagnosis_no_midday.csv", index=False)
    cond_df.to_csv(out / "regime_diagnosis_by_condition.csv", index=False)

    S += ["", "=" * 78, "  NOTAS", "=" * 78,
          "  * Las categorías marcadas DIAGNÓSTICO usan el día completo (información",
          "    posterior a la entrada): describen el régimen, no son filtro operable.",
          "  * Las condiciones causales sí son operables como hipótesis, previa",
          "    validación en datos no usados (2024 o jul-2026+).",
          "  * El dataset A originó las hipótesis de mediodía y distancia: todo corte",
          "    sobre él es in-sample para esas decisiones.",
          "=" * 78]
    summary = "\n".join(S)
    (out / "regime_diagnosis_summary.txt").write_text(summary, encoding="utf-8")
    print(summary)
    print(f"\nArchivos en {out}: regime_diagnosis_no_midday.csv | "
          f"regime_diagnosis_by_condition.csv | regime_diagnosis_summary.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
