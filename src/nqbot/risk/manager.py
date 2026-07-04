"""Risk Manager — máquina de estados de riesgo por sesión.

Controles (todos configurables en config.yaml):
  * Pérdida máxima diaria: % del equity al abrir la sesión. Al excederse
    en PnL realizado, bloqueo hasta la próxima sesión.
  * Máximo de entradas por sesión.
  * Racha máxima de pérdidas consecutivas -> bloqueo por el resto del día.

El bloqueo solo impide ABRIR posiciones nuevas: una posición ya abierta
sigue gobernada por su stop/target/flatten. Cada bloqueo se loguea una vez.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from ..backtesting.models import Trade
from ..config.settings import RiskConfig


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str = "ok"


class RiskManager:
    def __init__(self, cfg: RiskConfig, logger: logging.Logger | None = None) -> None:
        self.cfg = cfg
        self.log = logger or logging.getLogger("nqbot")
        self._session: date | None = None
        self._daily_loss_limit: float = 0.0
        self._daily_realized: float = 0.0
        self._entries_today: int = 0
        self._consecutive_losses: int = 0
        self._lock_reason: str | None = None

    # ------------------------------------------------------------------ estado
    @property
    def locked(self) -> bool:
        return self._lock_reason is not None

    @property
    def daily_realized(self) -> float:
        return self._daily_realized

    # ------------------------------------------------------------------ eventos
    def new_session(self, session_date: date, session_start_equity: float) -> None:
        """Reset diario. El límite de pérdida se fija sobre el equity de apertura."""
        self._session = session_date
        self._daily_loss_limit = session_start_equity * self.cfg.max_daily_loss_pct / 100.0
        self._daily_realized = 0.0
        self._entries_today = 0
        self._consecutive_losses = 0
        self._lock_reason = None

    def on_position_opened(self) -> None:
        self._entries_today += 1

    def on_trade_closed(self, trade: Trade) -> None:
        self._daily_realized += trade.pnl_net
        if trade.pnl_net < 0:
            self._consecutive_losses += 1
        elif trade.pnl_net > 0:
            self._consecutive_losses = 0

        if self._daily_realized <= -self._daily_loss_limit:
            self._lock("perdida_diaria_maxima",
                       f"PnL diario {self._daily_realized:+.2f} <= -{self._daily_loss_limit:.2f}")
        elif self._consecutive_losses >= self.cfg.max_consecutive_losses:
            self._lock("perdidas_consecutivas",
                       f"{self._consecutive_losses} pérdidas seguidas")

    # ------------------------------------------------------------------ consulta
    def can_open(self) -> RiskDecision:
        if self._lock_reason is not None:
            return RiskDecision(False, self._lock_reason)
        if self._entries_today >= self.cfg.max_trades_per_day:
            self._lock("max_trades_dia", f"{self._entries_today} entradas hoy")
            return RiskDecision(False, "max_trades_dia")
        return RiskDecision(True)

    # ------------------------------------------------------------------ interno
    def _lock(self, reason: str, detail: str) -> None:
        if self._lock_reason is None:
            self._lock_reason = reason
            self.log.warning(
                "RIESGO [%s]: BLOQUEO hasta la próxima sesión — %s (%s)",
                self._session, reason, detail,
            )
