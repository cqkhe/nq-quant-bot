#!/usr/bin/env python
"""Diagnóstico de edge de no_midday: ¿dónde pierde y dónde funciona?

Corre la variante sobre el dataset indicado, reconstruye el estado del
mercado en la barra de señal de cada trade (los mismos indicadores causales
que la estrategia vio) y agrega contexto de sesión. Después corta la
performance por condición para localizar las fuentes de pérdida.

Genera:
    reports/edge_diagnosis_no_midday.csv     cada trade con su contexto completo
    reports/edge_diagnosis_by_condition.csv  métricas por condición y bucket
    reports/edge_diagnosis_summary.txt       respuestas a las preguntas de edge

Notas metodológicas:
  * Features de barra de señal (dist. a VWAP, pendientes, stop, volumen
    relativo, rango inicial): causales, conocidas al momento de entrar.
  * Features de DÍA COMPLETO (rango del día, eficiencia direccional): usan
    información posterior a la entrada. Sirven para DIAGNÓSTICO de regímenes;
    un filtro operable necesitaría la versión intradía conocida en el momento.
  * Todo corte condicional sobre este dataset genera HIPÓTESIS, no filtros:
    cualquier filtro derivado de acá debe validarse en datos no usados.

Solo diagnóstico: no modifica estrategia, parámetros ni motor.

Uso:
    python scripts/diagnose_edge.py --data data/processed/MNQ_2025_01_2025_11_oos_clean.csv
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
DOW = {0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 4: "viernes"}
TERCILE_LABELS = ("bajo", "medio", "alto")


def tercile(series: pd.Series, labels=TERCILE_LABELS) -> pd.Series:
    try:
        return pd.qcut(series, 3, labels=labels)
    except ValueError:  # sin variación suficiente
        return pd.Series(["medio"] * len(series), index=series.index)


def build_trade_context(trades: pd.DataFrame, prepared: pd.DataFrame,
                        df: pd.DataFrame) -> pd.DataFrame:
    """Une cada trade con el estado del mercado en su barra de señal."""
    t = trades.copy()
    t["signal_time"] = t["entry_time"] - pd.Timedelta(minutes=1)

    # indicadores causales adicionales sobre el df preparado
    ctx = prepared.copy()
    ctx["dist_vwap"] = ctx["close"] - ctx["vwap"]
    ctx["vwap_slope"] = ctx["vwap"].diff(10)
    ctx["ema200_slope"] = ctx["ema_trend"].diff(30)
    ctx["or_size"] = ctx["or_high"] - ctx["or_low"]

    cols = ["dist_vwap", "vwap_slope", "ema200_slope", "or_size", "rel_volume",
            "vwap", "ema_trend", "close"]
    joined = ctx[cols].reindex(t["signal_time"])
    joined.index = t.index
    t = pd.concat([t, joined], axis=1)

    # contexto de sesión (día completo: solo para diagnóstico de régimen)
    session = df.index.normalize()
    daily = df.groupby(session).agg(
        day_high=("high", "max"), day_low=("low", "min"),
        day_open=("open", "first"), day_close=("close", "last"),
    )
    daily["day_range"] = daily["day_high"] - daily["day_low"]
    daily["day_efficiency"] = (
        (daily["day_close"] - daily["day_open"]).abs() / daily["day_range"].replace(0, np.nan)
    )
    daily["day_direction"] = np.sign(daily["day_close"] - daily["day_open"])
    t = t.join(daily[["day_range", "day_efficiency", "day_direction"]],
               on=t["entry_time"].dt.normalize())

    # ---- features derivadas (relativas a la dirección del trade)
    d = t["direction"]
    t["lado"] = d.map({1: "long", -1: "short"})
    t["hora"] = t["entry_time"].dt.hour.map(lambda h: f"{h:02d}h")
    t["franja"] = np.where(t["entry_time"].dt.hour < 12, "mañana", "tarde")
    t["dia_semana"] = t["entry_time"].dt.dayofweek.map(DOW)
    t["mes"] = t["entry_time"].dt.to_period("M").astype(str)
    t["stop_pts"] = (t["entry_price"] - t["stop_price"]) * d
    t["dist_vwap_favor"] = t["dist_vwap"] * d          # >0 siempre (por diseño)
    t["vwap_slope_dir"] = t["vwap_slope"] * d          # >0 = pendiente a favor
    t["ema200_slope_dir"] = t["ema200_slope"] * d
    t["sobre_vwap"] = np.where(t["dist_vwap"] * d > 0, "a favor", "en contra")
    t["sobre_ema200"] = np.where((t["close"] - t["ema_trend"]) * d > 0, "a favor", "en contra")
    t["pendiente_vwap"] = np.where(t["vwap_slope_dir"] > 0, "a favor", "en contra")
    t["pendiente_ema200"] = np.where(t["ema200_slope_dir"] > 0, "a favor", "en contra")
    t["dia_tendencia"] = np.where(
        t["day_efficiency"] >= 0.5, "tendencia",
        np.where(t["day_efficiency"] <= 0.25, "lateral/chop", "mixto"),
    )
    t["dia_con_trade"] = np.where(t["day_direction"] * d > 0, "a favor del día", "contra el día")

    # buckets data-driven (terciles del propio dataset)
    t["rango_dia_b"] = tercile(t["day_range"])
    t["stop_pts_b"] = tercile(t["stop_pts"])
    t["dist_vwap_b"] = tercile(t["dist_vwap_favor"])
    t["rel_volume_b"] = tercile(t["rel_volume"])
    t["or_size_b"] = tercile(t["or_size"])
    return t


CONDITIONS = [
    ("lado", "Long vs Short"),
    ("hora", "Hora de entrada"),
    ("franja", "Mañana vs tarde"),
    ("dia_semana", "Día de la semana"),
    ("mes", "Mes"),
    ("rango_dia_b", "Volatilidad del día (rango, terciles)"),
    ("dia_tendencia", "Tipo de día (eficiencia direccional)"),
    ("dia_con_trade", "Trade a favor / contra la dirección del día"),
    ("or_size_b", "Tamaño del rango inicial (terciles)"),
    ("dist_vwap_b", "Distancia a VWAP en la entrada (terciles)"),
    ("pendiente_vwap", "Pendiente del VWAP vs dirección"),
    ("pendiente_ema200", "Pendiente de la EMA200 vs dirección"),
    ("sobre_vwap", "Precio vs VWAP (dirección)"),
    ("sobre_ema200", "Precio vs EMA200 (dirección)"),
    ("stop_pts_b", "Tamaño del stop (terciles)"),
    ("rel_volume_b", "Volumen relativo en la entrada (terciles)"),
    ("exit_reason", "Tipo de salida"),
]


def condition_stats(t: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, label in CONDITIONS:
        for bucket, g in t.groupby(col, observed=True):
            pnl = g["pnl_net"]
            wins = pnl > 0
            gp = float(pnl[wins].sum())
            gl = float(-pnl[pnl < 0].sum())
            rows.append({
                "condicion": label,
                "bucket": str(bucket),
                "trades": len(g),
                "pnl": round(float(pnl.sum()), 2),
                "expr": round(float(g["r_multiple"].mean()), 3),
                "winrate_pct": round(float(wins.mean()) * 100, 1),
                "profit_factor": round(gp / gl, 2) if gl > 0 else float("inf"),
            })
    return pd.DataFrame(rows)


def bucket_range(t: pd.DataFrame, col: str, bucket_col: str) -> str:
    parts = []
    for label in TERCILE_LABELS:
        seg = t.loc[t[bucket_col] == label, col]
        if len(seg):
            parts.append(f"{label}: {seg.min():.1f}-{seg.max():.1f}")
    return " | ".join(parts)


def build_summary(t: pd.DataFrame, cond: pd.DataFrame, data_file: str) -> str:
    total_pnl = float(t["pnl_net"].sum())

    def table(label: str) -> pd.DataFrame:
        return cond[cond["condicion"] == label].sort_values("expr")

    def fmt(df_: pd.DataFrame) -> list[str]:
        out = []
        for _, r in df_.iterrows():
            flag = "  [n chico]" if r["trades"] < 15 else ""
            out.append(f"    {r['bucket']:<18} n={r['trades']:<4} PnL {r['pnl']:>+9.2f} "
                       f"expR {r['expr']:>+7.3f} WR {r['winrate_pct']:>5.1f}% "
                       f"PF {r['profit_factor']}{flag}")
        return out

    losers = cond[(cond["pnl"] < 0) & (cond["trades"] >= 15)].sort_values("pnl").head(6)

    L = [
        "=" * 76,
        "  DIAGNÓSTICO DE EDGE — no_midday | dataset out-of-sample 2025",
        f"  Dataset: {data_file}",
        f"  Trades: {len(t)} | PnL total: {total_pnl:+,.2f} | "
        f"expR: {t['r_multiple'].mean():+.3f} | winrate: {(t['pnl_net'] > 0).mean() * 100:.1f}%",
        "=" * 76, "",
        "-" * 76,
        "  PRINCIPALES FUENTES DE PÉRDIDA (buckets con n>=15, ordenados por PnL)",
        "-" * 76,
    ]
    for _, r in losers.iterrows():
        L.append(f"    {r['condicion']} = {r['bucket']:<16} n={r['trades']:<4} "
                 f"PnL {r['pnl']:>+9.2f}  expR {r['expr']:>+7.3f}")

    sections = [
        ("Long vs Short", "LONG vs SHORT"),
        ("Mañana vs tarde", "MAÑANA vs TARDE"),
        ("Hora de entrada", "POR HORA"),
        ("Volatilidad del día (rango, terciles)", "VOLATILIDAD DEL DÍA"),
        ("Tipo de día (eficiencia direccional)", "TENDENCIA vs LATERAL"),
        ("Trade a favor / contra la dirección del día", "A FAVOR / CONTRA EL DÍA"),
        ("Pendiente de la EMA200 vs dirección", "PENDIENTE EMA200"),
        ("Pendiente del VWAP vs dirección", "PENDIENTE VWAP"),
        ("Distancia a VWAP en la entrada (terciles)", "DISTANCIA A VWAP"),
        ("Tamaño del stop (terciles)", "TAMAÑO DEL STOP"),
        ("Volumen relativo en la entrada (terciles)", "VOLUMEN RELATIVO"),
        ("Tamaño del rango inicial (terciles)", "RANGO INICIAL"),
        ("Tipo de salida", "TIPO DE SALIDA"),
        ("Mes", "POR MES"),
        ("Día de la semana", "POR DÍA DE LA SEMANA"),
    ]
    for label, title in sections:
        L += ["", "-" * 76, f"  {title}", "-" * 76] + fmt(table(label))

    L += [
        "",
        "-" * 76, "  RANGOS DE LOS TERCILES (para leer los buckets)", "-" * 76,
        f"    rango del día (pts):   {bucket_range(t, 'day_range', 'rango_dia_b')}",
        f"    stop (pts):            {bucket_range(t, 'stop_pts', 'stop_pts_b')}",
        f"    dist. a VWAP (pts):    {bucket_range(t, 'dist_vwap_favor', 'dist_vwap_b')}",
        f"    volumen relativo:      {bucket_range(t, 'rel_volume', 'rel_volume_b')}",
        f"    rango inicial (pts):   {bucket_range(t, 'or_size', 'or_size_b')}",
        "",
        "-" * 76, "  NOTAS", "-" * 76,
        "  * 'sobre_vwap' y 'sobre_ema200' son 'a favor' en el 100% de los casos",
        "    por diseño de la estrategia (son condiciones del setup).",
        "  * Las features de día completo (rango, eficiencia) usan información",
        "    posterior a la entrada: válidas para diagnóstico, no como filtro",
        "    operable directo.",
        "  * Todo corte de este análisis es una HIPÓTESIS a validar en datos",
        "    no usados (2026+ o 2024). No convertir en filtro sin esa prueba.",
        "=" * 76,
    ]
    return "\n".join(L)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=str(ROOT / "data" / "processed" /
                                          "MNQ_2025_01_2025_11_oos_clean.csv"))
    ap.add_argument("--symbol", default="MNQ")
    ap.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    args = ap.parse_args()

    logger = setup_logger(log_dir=ROOT / "logs", level=logging.WARNING)
    config = Config.from_yaml(args.config)
    contract = config.contract(args.symbol)
    df = load_ohlcv_csv(args.data, logger)
    df = filter_to_trade_session(df, config.session)

    print(f"corriendo {STRATEGY} y reconstruyendo contexto por trade ...")
    strategy = create_strategy(STRATEGY, config.strategy_params.get(STRATEGY), contract)
    result = BacktestEngine(config, contract, strategy, logger).run(df)
    trades = pd.DataFrame([asdict(x) for x in result.trades])
    trades["entry_time"] = pd.to_datetime(trades["entry_time"])
    trades["exit_time"] = pd.to_datetime(trades["exit_time"])
    if trades.empty:
        print("Sin trades: nada que diagnosticar.")
        return 2

    prepared = strategy.prepare(df)
    enriched = build_trade_context(trades, prepared, df)
    cond = condition_stats(enriched)

    out_dir = ROOT / "reports"
    enriched.drop(columns=["signal_time"]).to_csv(out_dir / "edge_diagnosis_no_midday.csv", index=False)
    cond.to_csv(out_dir / "edge_diagnosis_by_condition.csv", index=False)

    summary = build_summary(enriched, cond, args.data)
    (out_dir / "edge_diagnosis_summary.txt").write_text(summary, encoding="utf-8")
    print()
    print(summary)
    print(f"\nArchivos: edge_diagnosis_no_midday.csv | edge_diagnosis_by_condition.csv | "
          f"edge_diagnosis_summary.txt (en {out_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
