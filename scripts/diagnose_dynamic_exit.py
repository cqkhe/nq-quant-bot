#!/usr/bin/env python
"""Diagnóstico H002: ¿tiene sentido investigar salidas dinámicas in-trade?

Reconstruye el recorrido INTRA-TRADE de cada operación de un reporte
existente usando los datos 1m: MFE/MAE en múltiplos de R, tiempo hasta
+0.25R/+0.5R/+1R, duración, retorno al VWAP post-entrada y expansión del
rango del día durante el trade. Después responde si los perdedores son
distinguibles de los ganadores DENTRO del trade y a tiempo.

NO corre backtests, NO crea variantes, NO modifica estrategias: lee un
reporte ya generado y los datos limpios.

Uso:
    python scripts/diagnose_dynamic_exit.py \
        --data data/processed/ARCHIVO_clean.csv \
        --report reports/CARPETA (con trades.csv) o CSV de trades

Genera:
    reports/dynamic_exit_diagnosis.csv         una fila por trade con su recorrido
    reports/dynamic_exit_diagnosis_summary.md  respuestas a las preguntas de H002

Notas metodológicas:
  * El recorrido usa high/low de barras 1m entre entry_time y exit_time
    (incluida la barra de salida: aproximación conservadora documentada).
  * La tabla de progreso condiciona a "trades aún abiertos en T con MFE < nivel":
    exactamente la información que tendría una regla de salida en T.
  * Se reporta la CURVA completa de ventanas (10-60 min) sin elegir óptimo:
    elegir el parámetro es trabajo de la ficha H002, con valores redondos.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import logging  # noqa: E402

from nqbot.config.settings import Config                     # noqa: E402
from nqbot.data.loader import load_ohlcv_csv                 # noqa: E402
from nqbot.indicators import session_vwap                    # noqa: E402
from nqbot.utils.logger import setup_logger                  # noqa: E402
from nqbot.utils.sessions import filter_to_trade_session     # noqa: E402

R_LEVELS = (0.25, 0.5, 1.0)
WINDOWS_MIN = (10, 15, 20, 30, 45, 60)


# ------------------------------------------------------------------ reconstrucción
def load_trades(report: Path) -> pd.DataFrame:
    path = report / "trades.csv" if report.is_dir() else report
    trades = pd.read_csv(path, parse_dates=["entry_time", "exit_time"])
    required = {"entry_time", "exit_time", "entry_price", "stop_price", "direction"}
    missing = required - set(trades.columns)
    if missing:
        raise ValueError(f"{path}: faltan columnas {missing}")
    return trades


def rebuild_trade_paths(trades: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    vwap = session_vwap(df)
    session = df.index.normalize()
    range_so_far = df["high"].groupby(session).cummax() - df["low"].groupby(session).cummin()

    rows = []
    for trade in trades.itertuples(index=False):
        d = int(trade.direction)
        r_pts = (trade.entry_price - trade.stop_price) * d
        if r_pts <= 0:
            continue
        seg = df.loc[trade.entry_time: trade.exit_time]
        if seg.empty:
            continue

        if d > 0:
            fav = (seg["high"] - trade.entry_price) / r_pts
            adv = (trade.entry_price - seg["low"]) / r_pts
            back_to_vwap = (seg["low"].iloc[1:] <= vwap.loc[seg.index[1:]]).any()
        else:
            fav = (trade.entry_price - seg["low"]) / r_pts
            adv = (seg["high"] - trade.entry_price) / r_pts
            back_to_vwap = (seg["high"].iloc[1:] >= vwap.loc[seg.index[1:]]).any()

        minutes = (seg.index - trade.entry_time).total_seconds() / 60.0
        row = {
            "entry_time": trade.entry_time, "exit_time": trade.exit_time,
            "direction": d, "exit_reason": trade.exit_reason,
            "pnl_net": trade.pnl_net, "r_multiple": trade.r_multiple,
            "duration_min": round(float(minutes[-1]), 1),
            "mfe_r": round(float(fav.max()), 3),
            "mae_r": round(float(adv.max()), 3),
            "back_to_vwap": bool(back_to_vwap),
            "range_expansion_pts": round(
                float(range_so_far.loc[seg.index[-1]] - range_so_far.loc[seg.index[0]]), 2),
        }
        for level in R_LEVELS:
            hit = fav.to_numpy() >= level
            row[f"min_to_{level}R"] = (
                round(float(minutes[np.argmax(hit)]), 1) if hit.any() else None
            )
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ agregados
def outcome_table(paths: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for reason, g in paths.groupby("exit_reason"):
        reached = {level: g[f"min_to_{level}R"].notna().mean() * 100 for level in R_LEVELS}
        rows.append({
            "salida": reason, "n": len(g),
            "dur_mediana_min": g["duration_min"].median(),
            "mfe_r_mediana": g["mfe_r"].median(),
            "mae_r_mediana": g["mae_r"].median(),
            **{f"pct_alcanza_{level}R": round(reached[level], 1) for level in R_LEVELS},
            "min_a_0.5R_mediana": g["min_to_0.5R"].median(),
        })
    return pd.DataFrame(rows)


def progress_rule_table(paths: pd.DataFrame, level: float) -> pd.DataFrame:
    """Para cada ventana T: trades AÚN ABIERTOS en T, partidos por si ya
    alcanzaron `level` R. Es la vista exacta de una regla de salida en T."""
    col = f"min_to_{level}R"
    rows = []
    for T in WINDOWS_MIN:
        alive = paths[paths["duration_min"] > T]
        if alive.empty:
            continue
        reached = alive[alive[col].notna() & (alive[col] <= T)]
        stalled = alive.drop(reached.index)
        for label, g in (("alcanzó", reached), ("NO alcanzó", stalled)):
            if len(g):
                rows.append({
                    "ventana_min": T, "grupo": f"{label} +{level}R", "n": len(g),
                    "winrate_final_pct": round((g["pnl_net"] > 0).mean() * 100, 1),
                    "r_final_promedio": round(g["r_multiple"].mean(), 3),
                    "pct_termina_en_stop": round(
                        g["exit_reason"].str.startswith("stop").mean() * 100, 1),
                })
    return pd.DataFrame(rows)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="CSV 1m procesado")
    ap.add_argument("--report", required=True,
                    help="Carpeta de reporte (con trades.csv) o CSV de trades")
    ap.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    args = ap.parse_args()

    logger = setup_logger(log_dir=ROOT / "logs", level=logging.WARNING)
    config = Config.from_yaml(args.config)
    df = filter_to_trade_session(load_ohlcv_csv(args.data, logger), config.session)
    trades = load_trades(Path(args.report))
    print(f"Reconstruyendo el recorrido de {len(trades)} trades sobre {len(df):,} barras ...")

    paths = rebuild_trade_paths(trades, df)
    out_csv = ROOT / "reports" / "dynamic_exit_diagnosis.csv"
    paths.to_csv(out_csv, index=False)

    outcomes = outcome_table(paths)
    rule_050 = progress_rule_table(paths, 0.5)
    rule_025 = progress_rule_table(paths, 0.25)

    winners = paths[paths["exit_reason"].str.startswith("target")]
    stops = paths[paths["exit_reason"].str.startswith("stop")]
    flatten = paths[paths["exit_reason"] == "session_flatten"]

    # ---------------- markdown
    L = [
        "# Diagnóstico H002 — salidas dinámicas in-trade",
        "",
        f"- **Trades analizados:** {len(paths)} (reporte: `{args.report}`)",
        f"- **Datos:** `{args.data}`",
        f"- **Período:** {paths['entry_time'].min()} → {paths['entry_time'].max()}",
        "- **Advertencia:** trades de la familia H001 sobre datos YA VISTOS:",
        "  este diagnóstico sirve para DISEÑAR H002, no para validarla.",
        "",
        "## Recorrido por tipo de salida", "",
        outcomes.to_markdown(index=False), "",
        "## Regla hipotética: ¿alcanzó +0.5R dentro de la ventana T?",
        "", "(solo trades aún abiertos en T; es lo que vería una regla de salida en T)", "",
        rule_050.to_markdown(index=False), "",
        "## Lo mismo con umbral +0.25R", "",
        rule_025.to_markdown(index=False), "",
        "## Otras preguntas de la ficha", "",
        f"- **¿Los flatten son trades que no expandieron?** MFE mediana de los "
        f"session_flatten: {flatten['mfe_r'].median():.2f}R | expansión mediana del rango "
        f"del día durante el trade: {flatten['range_expansion_pts'].median():.1f} pts "
        f"(vs {winners['range_expansion_pts'].median():.1f} pts en targets).",
        f"- **¿Volver al VWAP después de entrar anticipa el fallo?** Winrate con retorno "
        f"al VWAP: {(paths[paths['back_to_vwap']]['pnl_net'] > 0).mean() * 100:.1f}% "
        f"(n={int(paths['back_to_vwap'].sum())}) vs sin retorno: "
        f"{(paths[~paths['back_to_vwap']]['pnl_net'] > 0).mean() * 100:.1f}% "
        f"(n={int((~paths['back_to_vwap']).sum())}).",
        f"- **¿La falta de expansión explica pérdidas?** Expansión mediana del rango "
        f"durante el trade — targets: {winners['range_expansion_pts'].median():.1f} pts | "
        f"stops: {stops['range_expansion_pts'].median():.1f} pts | "
        f"flatten: {flatten['range_expansion_pts'].median():.1f} pts.",
        "",
        "## Nota metodológica",
        "",
        "- El recorrido usa high/low de cada barra 1m incluida la de salida.",
        "- La curva de ventanas se reporta COMPLETA a propósito: este documento no",
        "  elige el parámetro. La elección (valores redondos, lejos del óptimo) es",
        "  trabajo de la ficha H002 al pasar a DESIGNED, y su validación exige el",
        "  OOS virgen declarado (jul-2026+ o 2023).",
        "",
    ]
    out_md = ROOT / "reports" / "dynamic_exit_diagnosis_summary.md"
    out_md.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"Archivos: {out_csv} | {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
