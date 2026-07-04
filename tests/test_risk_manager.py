from datetime import date

from nqbot.config.settings import RiskConfig
from nqbot.risk.manager import RiskManager

D1, D2 = date(2026, 1, 5), date(2026, 1, 6)


def _cfg(**overrides) -> RiskConfig:
    base = dict(
        risk_per_trade_pct=0.5,
        max_daily_loss_pct=2.0,
        max_trades_per_day=99,
        max_consecutive_losses=99,
        max_contracts=10,
        max_stop_points=100.0,
    )
    base.update(overrides)
    return RiskConfig(**base)


def test_daily_loss_lockout_and_reset(make_trade):
    rm = RiskManager(_cfg())
    rm.new_session(D1, 10_000)  # límite diario: $200
    rm.on_trade_closed(make_trade(-150.0))
    assert rm.can_open().allowed
    rm.on_trade_closed(make_trade(-100.0))  # -250 acumulado -> bloqueo
    decision = rm.can_open()
    assert not decision.allowed
    assert decision.reason == "perdida_diaria_maxima"

    rm.new_session(D2, 9_750)  # nueva sesión: se libera
    assert rm.can_open().allowed


def test_max_trades_per_day(make_trade):
    rm = RiskManager(_cfg(max_trades_per_day=2))
    rm.new_session(D1, 10_000)
    rm.on_position_opened()
    rm.on_position_opened()
    decision = rm.can_open()
    assert not decision.allowed
    assert decision.reason == "max_trades_dia"


def test_consecutive_losses_lockout(make_trade):
    rm = RiskManager(_cfg(max_consecutive_losses=2))
    rm.new_session(D1, 100_000)  # límite de pérdida enorme: no interfiere
    rm.on_trade_closed(make_trade(-10.0))
    rm.on_trade_closed(make_trade(+10.0))  # una ganancia corta la racha
    rm.on_trade_closed(make_trade(-10.0))
    assert rm.can_open().allowed
    rm.on_trade_closed(make_trade(-10.0))  # segunda seguida -> bloqueo
    assert not rm.can_open().allowed
    assert rm.can_open().reason == "perdidas_consecutivas"
