from __future__ import annotations

from datetime import datetime

from src.trading.safety_gates import TradeSafetyGates
from src.utils.database import get_session, TradeRecordModel


def _reset_trade_records() -> None:
    session = get_session()
    try:
        session.query(TradeRecordModel).delete()
        session.commit()
    finally:
        session.close()


def _insert_trade(symbol: str, when: datetime) -> None:
    session = get_session()
    try:
        record = TradeRecordModel(
            symbol=symbol,
            side="BUY",
            quantity=1.0,
            entry_price=1.0,
            stop_loss_price=0.9,
            take_profit_levels=[{"price": 1.1, "size_pct": 1.0}],
            confidence=0.75,
            status="OPEN",
            entry_time=when,
            metadata_payload={"source": "test"},
        )
        session.add(record)
        session.commit()
    finally:
        session.close()


def test_monthly_limit_blocks_second_trade_same_month() -> None:
    _reset_trade_records()

    gates = TradeSafetyGates()
    symbol = "DOGEUSDT"

    ok, reason = gates.check_monthly_trade_limit(symbol)
    assert ok is True
    assert reason is None

    # Insert a trade for this month, then ensure we block the next one.
    now = datetime.utcnow()
    _insert_trade(symbol=symbol, when=now)

    ok, reason = gates.check_monthly_trade_limit(symbol)
    assert ok is False
    assert reason and "Monthly trade limit" in reason


def test_monthly_limit_allows_new_month() -> None:
    _reset_trade_records()

    gates = TradeSafetyGates()
    symbol = "DOGEUSDT"

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Put a trade in the previous month.
    if month_start.month == 1:
        prev_month = month_start.replace(year=month_start.year - 1, month=12)
    else:
        prev_month = month_start.replace(month=month_start.month - 1)

    _insert_trade(symbol=symbol, when=prev_month)

    ok, reason = gates.check_monthly_trade_limit(symbol)
    assert ok is True
    assert reason is None
