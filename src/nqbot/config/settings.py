"""Config Manager.

Carga config/config.yaml a dataclasses tipadas e inmutables. El resto del
código nunca toca dicts crudos: si un parámetro no existe acá, no existe.
Los defaults son deliberadamente conservadores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Configuración inválida o incompleta."""


def _parse_time(value: str | time) -> time:
    if isinstance(value, time):
        return value
    try:
        hh, mm = str(value).strip().split(":")
        return time(int(hh), int(mm))
    except (ValueError, AttributeError) as exc:
        raise ConfigError(f"Hora inválida en config: {value!r} (formato esperado 'HH:MM')") from exc


def _parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ConfigError(f"Fecha inválida en config: {value!r} (formato esperado 'YYYY-MM-DD')") from exc


@dataclass(frozen=True)
class ContractSpec:
    """Especificación de un contrato de futuros (valores del exchange)."""

    symbol: str
    tick_size: float
    point_value: float          # USD por punto entero de índice
    commission_per_side: float  # USD por contrato y por lado

    @property
    def tick_value(self) -> float:
        return self.tick_size * self.point_value

    def round_to_tick(self, price: float) -> float:
        return round(round(price / self.tick_size) * self.tick_size, 10)


@dataclass(frozen=True)
class AccountConfig:
    initial_capital: float = 25_000.0


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade_pct: float = 0.5
    max_daily_loss_pct: float = 2.0
    max_trades_per_day: int = 5
    max_consecutive_losses: int = 3
    max_contracts: int = 10
    max_stop_points: float = 100.0


@dataclass(frozen=True)
class ExecutionConfig:
    slippage_ticks: int = 1
    # Spread bid/ask estimado en ticks: cada fill a MERCADO paga medio spread
    # además del slippage. Las órdenes límite (target) no lo pagan.
    spread_ticks: float = 0.0


@dataclass(frozen=True)
class DataQualityConfig:
    """Umbrales del control de calidad de datos (porcentajes sobre el total).

    Si un problema supera su umbral se convierte en ERROR y el backtest no corre.
    Por debajo del umbral queda como WARNING (el saneador lo repara/descarta).
    """

    max_missing_bars_pct: float = 5.0    # velas faltantes en la ventana activa
    max_duplicate_pct: float = 1.0
    max_nan_pct: float = 1.0
    max_incoherent_pct: float = 0.5      # OHLC imposible / precios no positivos
    max_zero_volume_pct: float = 5.0     # sobre la ventana activa
    max_gap_minutes: int = 5             # gap intra-sesión reportado como evento
    max_bar_return_pct: float = 5.0      # salto barra-a-barra sospechoso (bad tick)
    max_weekend_bars_pct: float = 0.1    # barras espurias de finde toleradas (WARNING);
                                         # por encima sugiere timezone corrida -> ERROR


@dataclass(frozen=True)
class CalendarConfig:
    """Calendario de feriados y sesiones especiales del exchange.

    * no_session:      fechas SIN sesión (exchange cerrado): no se esperan velas.
    * partial_session: fecha -> hora de cierre anticipado (ET). Solo se esperan
                       velas hasta esa hora; el faltante posterior no es error.
    Los sábados y domingos nunca cuentan como sesiones RTH esperadas
    (no hace falta declararlos).
    """

    no_session: frozenset[date] = frozenset()
    partial_session: dict[date, time] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionConfig:
    """Horarios de sesión en hora del exchange (los datos se asumen en ET).

    Sesiones CME Globex para futuros de índices:
      overnight: globex_open (18:00) -> premarket_start (04:00), cruza medianoche
      premarket: premarket_start (04:00) -> rth_start (09:30)
      regular:   rth_start (09:30) -> rth_end (16:00)
      all:       globex_open (18:00) -> globex_close (17:00)
    `trade_session` define en cuál de ellas opera el bot; el resto de los
    datos se filtra antes del backtest.
    """

    timezone: str = "America/New_York"
    globex_open: time = time(18, 0)
    globex_close: time = time(17, 0)
    premarket_start: time = time(4, 0)
    rth_start: time = time(9, 30)
    rth_end: time = time(16, 0)
    trade_session: str = "regular"
    entry_start: time = time(9, 45)
    entry_cutoff: time = time(15, 15)
    flatten_time: time = time(15, 50)

    def trade_window(self) -> tuple[time, time]:
        """(inicio, fin) de la ventana operada. Puede cruzar medianoche."""
        windows = {
            "regular": (self.rth_start, self.rth_end),
            "premarket": (self.premarket_start, self.rth_start),
            "overnight": (self.globex_open, self.premarket_start),
            "all": (self.globex_open, self.globex_close),
        }
        try:
            return windows[self.trade_session]
        except KeyError:
            raise ConfigError(
                f"trade_session inválida: {self.trade_session!r}. Opciones: {sorted(windows)}"
            )


@dataclass(frozen=True)
class Config:
    account: AccountConfig = field(default_factory=AccountConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    data_quality: DataQualityConfig = field(default_factory=DataQualityConfig)
    calendar: CalendarConfig = field(default_factory=CalendarConfig)
    contracts: dict[str, ContractSpec] = field(default_factory=dict)
    strategy_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    live_trading: bool = False
    source_path: str | None = None

    def contract(self, symbol: str) -> ContractSpec:
        try:
            return self.contracts[symbol.upper()]
        except KeyError:
            known = ", ".join(sorted(self.contracts)) or "(ninguno)"
            raise ConfigError(f"Contrato {symbol!r} no definido en config. Definidos: {known}")

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        path = Path(path)
        if not path.exists():
            raise ConfigError(f"No existe el archivo de configuración: {path}")
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

        contracts = {
            sym.upper(): ContractSpec(
                symbol=sym.upper(),
                tick_size=float(spec["tick_size"]),
                point_value=float(spec["point_value"]),
                commission_per_side=float(spec.get("commission_per_side", 0.0)),
            )
            for sym, spec in (raw.get("contracts") or {}).items()
        }

        sess = raw.get("session") or {}
        session = SessionConfig(
            timezone=sess.get("timezone", SessionConfig.timezone),
            globex_open=_parse_time(sess.get("globex_open", SessionConfig.globex_open)),
            globex_close=_parse_time(sess.get("globex_close", SessionConfig.globex_close)),
            premarket_start=_parse_time(sess.get("premarket_start", SessionConfig.premarket_start)),
            rth_start=_parse_time(sess.get("rth_start", SessionConfig.rth_start)),
            rth_end=_parse_time(sess.get("rth_end", SessionConfig.rth_end)),
            trade_session=str(sess.get("trade_session", SessionConfig.trade_session)).lower(),
            entry_start=_parse_time(sess.get("entry_start", SessionConfig.entry_start)),
            entry_cutoff=_parse_time(sess.get("entry_cutoff", SessionConfig.entry_cutoff)),
            flatten_time=_parse_time(sess.get("flatten_time", SessionConfig.flatten_time)),
        )
        session.trade_window()  # valida trade_session al cargar, no en medio del run

        cal_raw = raw.get("calendar") or {}
        calendar = CalendarConfig(
            no_session=frozenset(_parse_date(d) for d in (cal_raw.get("no_session") or [])),
            partial_session={
                _parse_date(day): _parse_time(end)
                for day, end in (cal_raw.get("partial_session") or {}).items()
            },
        )

        return cls(
            account=AccountConfig(**(raw.get("account") or {})),
            risk=RiskConfig(**(raw.get("risk") or {})),
            execution=ExecutionConfig(**(raw.get("execution") or {})),
            session=session,
            data_quality=DataQualityConfig(**(raw.get("data_quality") or {})),
            calendar=calendar,
            contracts=contracts,
            strategy_params=raw.get("strategy") or {},
            live_trading=bool(raw.get("live_trading", False)),
            source_path=str(path),
        )
