#!/usr/bin/env python
"""Importa datos históricos reales al proyecto: data/raw -> data/processed.

Flujo:
  1. Dejar el CSV original del proveedor en data/raw/ (nunca se modifica).
  2. Correr este script: parsea, audita la calidad (mismo motor que el gate
     del backtest), y solo si el veredicto es APTO escribe la versión limpia
     y normalizada en data/processed/.
  3. Backtestear siempre contra data/processed/.

El reporte de auditoría queda junto al archivo procesado como
<nombre>_quality.txt, se apruebe o no.

Uso:
    python scripts/import_data.py --input data/raw/MNQ_2025.csv
    python scripts/import_data.py --input data/raw/MNQ_2025.csv --out data/processed/MNQ_1m.csv

El CSV de entrada debe tener columnas datetime,open,high,low,close,volume
(se aceptan alias comunes, epoch, 'date'+'time' separados y timestamps con
timezone, que se convierten a hora del exchange).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nqbot.config.settings import Config                      # noqa: E402
from nqbot.data.loader import parse_ohlcv_csv                 # noqa: E402
from nqbot.data.quality import DataQualityChecker             # noqa: E402
from nqbot.data.validators import validate_ohlcv              # noqa: E402
from nqbot.utils.logger import setup_logger                   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="CSV original (idealmente en data/raw/)")
    ap.add_argument("--out", help="Destino limpio (default: data/processed/<nombre>_clean.csv)")
    ap.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    ap.add_argument(
        "--force", action="store_true",
        help="Escribe el procesado aunque el veredicto sea NO APTO (solo para debugging)",
    )
    args = ap.parse_args()

    logger = setup_logger(log_dir=ROOT / "logs")
    config = Config.from_yaml(args.config)

    src = Path(args.input)
    out = Path(args.out) if args.out else ROOT / "data" / "processed" / f"{src.stem}_clean.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1) Parseo crudo + auditoría
    df_raw, meta = parse_ohlcv_csv(src, logger, timezone=config.session.timezone)
    report = DataQualityChecker(
        config.session, config.data_quality, calendar=config.calendar, logger=logger
    ).check(df_raw, meta)

    quality_path = out.with_name(f"{out.stem}_quality.txt")
    quality_path.write_text(report.to_text(), encoding="utf-8")
    print(report.to_text())
    print(f"\nReporte de calidad: {quality_path}")

    if report.has_errors and not args.force:
        print("\nIMPORTACION ABORTADA: veredicto NO APTO. Corregir los datos en origen")
        print("(o usar --force solo para debugging).")
        return 4

    # 2) Saneo y escritura normalizada
    df, warnings = validate_ohlcv(df_raw)
    for w in warnings:
        logger.warning("Datos: %s", w)
    df.to_csv(out)
    print(f"\nOK: {len(df):,} barras limpias escritas en {out}")
    print("Backtest sugerido:")
    print(f"  python main.py --mode backtest --symbol MNQ --strategy base_vwap_ema --data {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
