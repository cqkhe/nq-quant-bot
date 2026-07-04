#!/usr/bin/env python
"""Recorta un CSV OHLCV procesado a un rango de fechas.

Uso típico (armar un tramo out-of-sample que excluya el período in-sample):

    python scripts/filter_data_by_date.py \
        --input data/processed/MNQ_2025_01_2026_06_1m_ninjatrader_combined_clean.csv \
        --start 2025-01-01 --end 2025-11-30 \
        --output data/processed/MNQ_2025_01_2025_11_oos_clean.csv

Ambos extremos son INCLUSIVOS a nivel día: --end 2025-11-30 conserva todas
las barras del 30 de noviembre. Mantiene las columnas originales tal cual.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="CSV procesado de entrada")
    ap.add_argument("--start", required=True, help="Fecha inicial YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", required=True, help="Fecha final YYYY-MM-DD (inclusive, día completo)")
    ap.add_argument("--output", required=True, help="CSV de salida")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"ERROR: no existe {src}")
        return 2

    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end) + pd.Timedelta(days=1)  # incluir el día final completo
    if start >= end:
        print(f"ERROR: rango inválido ({args.start} -> {args.end})")
        return 2

    df = pd.read_csv(src, index_col=0, parse_dates=True)
    df.index.name = df.index.name or "datetime"
    before = len(df)
    out = df[(df.index >= start) & (df.index < end)]
    if out.empty:
        print(f"ERROR: ninguna fila cae en {args.start} -> {args.end} "
              f"(el archivo cubre {df.index[0]} -> {df.index[-1]})")
        return 2

    dst = Path(args.output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(dst)

    print(f"Entrada:  {src.name} ({before:,} filas | {df.index[0]} -> {df.index[-1]})")
    print(f"Filtro:   {args.start} -> {args.end} (inclusive)")
    print(f"Salida:   {dst} ({len(out):,} filas | {out.index[0]} -> {out.index[-1]})")
    print(f"Sesiones: {out.index.normalize().nunique()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
