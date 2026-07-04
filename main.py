#!/usr/bin/env python
"""Punto de entrada CLI de nqbot.

Uso típico:
    python main.py --mode backtest --symbol MNQ --strategy base_vwap_ema --data data/processed/MNQ_1m.csv

Modos:
    backtest  simula la estrategia sobre datos históricos (único modo activo)
    paper     paper trading — pendiente de implementación
    live      deshabilitado por diseño (doble llave LIVE_TRADING)

Antes de cada backtest se audita la calidad de los datos y se escribe
reports/data_quality_report.txt. Si el veredicto es NO APTO, el backtest
no corre (exit code 4).

Exit codes: 0 ok | 2 error de uso/config/datos | 3 guarda de ejecución real |
            4 datos no aptos para backtest
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from nqbot.backtesting.engine import BacktestEngine           # noqa: E402
from nqbot.backtesting.metrics import compute_metrics         # noqa: E402
from nqbot.backtesting.report import format_summary, save_report  # noqa: E402
from nqbot.config.settings import AccountConfig, Config, ConfigError  # noqa: E402
from nqbot.data.loader import DataLoadError, parse_ohlcv_csv  # noqa: E402
from nqbot.data.quality import SEV_ERROR, DataQualityChecker  # noqa: E402
from nqbot.data.validators import DataValidationError, validate_ohlcv  # noqa: E402
from nqbot.strategies.registry import available_strategies, create_strategy  # noqa: E402
from nqbot.utils.logger import setup_logger                   # noqa: E402
from nqbot.utils.sessions import filter_to_trade_session      # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="nqbot", description="Bot cuantitativo para futuros NQ/MNQ")
    p.add_argument("--mode", choices=("backtest", "paper", "live"), default="backtest")
    p.add_argument("--symbol", default="MNQ", help="Símbolo definido en config (NQ, MNQ)")
    p.add_argument("--strategy", default="base_vwap_ema",
                   help=f"Estrategia: {', '.join(available_strategies())}")
    p.add_argument("--data", help="CSV OHLCV histórico (requerido en backtest)")
    p.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    p.add_argument("--capital", type=float, help="Override del capital inicial de la config")
    p.add_argument("--reports-dir", default=str(ROOT / "reports"))
    p.add_argument(
        "--ignore-data-quality", action="store_true",
        help="Corre el backtest aunque los datos sean NO APTOS (solo para debugging)",
    )
    return p.parse_args(argv)


def run_quality_gate(args: argparse.Namespace, config: Config, logger) -> "pd.DataFrame | None":
    """Audita los datos y escribe data_quality_report.txt. None si no son aptos."""
    df_raw, meta = parse_ohlcv_csv(args.data, logger, timezone=config.session.timezone)
    quality = DataQualityChecker(
        config.session, config.data_quality, calendar=config.calendar, logger=logger
    ).check(df_raw, meta)

    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    quality_path = reports_dir / "data_quality_report.txt"
    quality_path.write_text(quality.to_text(), encoding="utf-8")

    logger.info("Calidad de datos: %s | reporte: %s", quality.verdict, quality_path)
    for issue in quality.issues:
        level = logging.ERROR if issue.severity == SEV_ERROR else logging.WARNING
        logger.log(level, "Calidad [%s]: %s", issue.code, issue.message)

    if quality.has_errors and not args.ignore_data_quality:
        logger.error(
            "Backtest ABORTADO: los datos no superan las validaciones mínimas. "
            "Detalle en %s. (--ignore-data-quality lo omite, solo para debugging)",
            quality_path,
        )
        return None
    if quality.has_errors:
        logger.warning("--ignore-data-quality activo: continuando con datos NO APTOS")
    return df_raw


def run_backtest(args: argparse.Namespace, config: Config, logger) -> int:
    if not args.data:
        logger.error("--data es obligatorio en modo backtest")
        return 2
    contract = config.contract(args.symbol)

    # 1) Gate de calidad: sin APTO no hay backtest
    df_raw = run_quality_gate(args, config, logger)
    if df_raw is None:
        return 4

    # 2) Saneo + recorte a la ventana de sesión operada
    df, warnings = validate_ohlcv(df_raw)
    for w in warnings:
        logger.warning("Datos: %s", w)
    df = filter_to_trade_session(df, config.session)
    if df.empty:
        logger.error("No quedaron barras dentro de la sesión '%s'", config.session.trade_session)
        return 2
    logger.info(
        "Datos listos: %d barras en sesión '%s' | %s -> %s",
        len(df), config.session.trade_session, df.index[0], df.index[-1],
    )

    strategy = create_strategy(args.strategy, config.strategy_params.get(args.strategy), contract)

    engine = BacktestEngine(config, contract, strategy, logger)
    result = engine.run(df)
    metrics = compute_metrics(result)

    print()
    print(format_summary(result, metrics))
    folder = save_report(result, metrics, args.reports_dir)
    logger.info("Reporte completo guardado en: %s", folder)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger = setup_logger(log_dir=ROOT / "logs")

    try:
        config = Config.from_yaml(args.config)
        if args.capital:
            config = replace(config, account=AccountConfig(initial_capital=args.capital))

        if args.mode == "backtest":
            return run_backtest(args, config, logger)

        if args.mode == "paper":
            logger.error(
                "Paper trading (fase 2) todavía no está implementado. "
                "El flujo del proyecto es: backtest -> paper -> live."
            )
            return 2

        # mode == "live": la guarda de doble llave aborta salvo habilitación explícita
        from nqbot.execution.broker import LiveBroker
        LiveBroker(config)
        return 2  # inalcanzable hoy: LiveBroker siempre lanza

    except (ConfigError, DataLoadError, DataValidationError, ValueError) as exc:
        logger.error("%s", exc)
        return 2
    except (RuntimeError, NotImplementedError) as exc:
        logger.error("%s", exc)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
