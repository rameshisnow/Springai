"""SQLite-backed persistence helpers for trading records."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config.settings import config
from src.utils.logger import logger

Base = declarative_base()
_engine = None
_SessionLocal = None
_engine_url: Optional[str] = None


class TradeRecordModel(Base):
    """Persistent trade record stored in SQLite."""

    __tablename__ = "trade_records"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(4), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss_price = Column(Float, nullable=True)
    take_profit_levels = Column(JSON, nullable=True)
    confidence = Column(Float, default=0.0)
    status = Column(String(20), default="OPEN")
    profit_loss = Column(Float, default=0.0)
    pnl_percent = Column(Float, default=0.0)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    metadata_payload = Column(JSON, default={})


def configure_database(database_url: Optional[str] = None):
    """Initialize the engine and session maker."""
    global _engine, _SessionLocal, _engine_url

    target_url = database_url or config.DATABASE_URL
    connect_args: Dict[str, Any] = {}

    if target_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    if _engine is None or target_url != _engine_url:
        _engine = create_engine(target_url, future=True, connect_args=connect_args)
        _engine_url = target_url
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, future=True)
    Base.metadata.create_all(_engine)


def get_session():
    """Return a new SQLAlchemy session."""
    if _SessionLocal is None:
        configure_database()
    return _SessionLocal()


def log_trade_entry(
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float,
    stop_loss_price: float,
    take_profit_levels: Optional[List[Dict[str, Any]]],
    confidence: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Insert a new trade record."""
    session = get_session()
    try:
        record = TradeRecordModel(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_levels=take_profit_levels,
            confidence=confidence,
            entry_time=datetime.utcnow(),
            metadata_payload=metadata or {},
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        logger.info(f"Persisted trade record #{record.id} for {symbol}")
        return record.id
    except SQLAlchemyError as exc:
        logger.error(f"Failed to persist trade entry for {symbol}: {exc}")
        session.rollback()
        return None
    finally:
        session.close()


def update_trade_exit(
    record_id: int,
    exit_price: float,
    pnl: float,
    pnl_percent: float,
    status: str = "CLOSED",
    reason: str = "",
) -> Optional[TradeRecordModel]:
    """Update an existing trade record with exit details."""
    session = get_session()
    try:
        record = session.get(TradeRecordModel, record_id)
        if not record:
            logger.warning(f"Trade record #{record_id} not found for update")
            return None

        record.exit_price = exit_price
        record.exit_time = datetime.utcnow()
        record.profit_loss = pnl
        record.pnl_percent = pnl_percent
        record.status = status
        metadata_payload = dict(record.metadata_payload or {})
        metadata_payload.update({"exit_reason": reason})
        record.metadata_payload = metadata_payload

        session.commit()
        session.refresh(record)
        logger.info(f"Updated trade record #{record.id} with exit data")
        return record
    except SQLAlchemyError as exc:
        logger.error(f"Failed to update trade record #{record_id}: {exc}")
        session.rollback()
        return None
    finally:
        session.close()


def get_recent_trades(limit: int = 20) -> List[TradeRecordModel]:
    """Return most recent trades."""
    session = get_session()
    try:
        stmt = select(TradeRecordModel).order_by(TradeRecordModel.entry_time.desc()).limit(limit)
        results = session.execute(stmt).scalars().all()
        return results
    finally:
        session.close()


# Initialize database at import time
configure_database()
