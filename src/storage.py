"""Persistence layer backed by SQLite via SQLAlchemy."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List

import pandas as pd
from sqlalchemy import Date, DateTime, Float, Integer, String, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import Settings

LOGGER = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    side: Mapped[str] = mapped_column(String)
    size: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    rationale: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "side": self.side,
            "size": self.size,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "take_profit": self.take_profit,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "status": self.status,
            "rationale": self.rationale,
            "confidence": self.confidence,
        }


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_date: Mapped[datetime] = mapped_column(Date, default=datetime.utcnow)
    name: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[float] = mapped_column(Float)


_ENGINE: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def init_db(settings: Settings) -> None:
    """Initialise the SQLite database and create tables if needed."""

    global _ENGINE, _SessionFactory
    if _ENGINE is not None:
        return
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    _ENGINE = create_engine(settings.database_url, echo=False, future=True, connect_args=connect_args)
    Base.metadata.create_all(_ENGINE)
    _SessionFactory = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False, future=True)
    LOGGER.info("Database initialised at %s", settings.database_url)


@contextmanager
def session_scope() -> Iterable[Session]:
    if _SessionFactory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        LOGGER.exception("Database error: %s", exc)
        raise
    finally:
        session.close()


def log_trade_intent(
    *,
    symbol: str,
    side: str,
    size: float,
    entry_price: float,
    stop_price: float | None,
    take_profit: float | None,
    rationale: str,
    confidence: float,
) -> None:
    """Persist an order intent before sending it to the exchange."""

    with session_scope() as session:
        trade = Trade(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            stop_price=stop_price,
            take_profit=take_profit,
            rationale=rationale,
            confidence=confidence,
        )
        session.add(trade)


def record_fill(trade_id: int, exit_price: float, pnl: float) -> None:
    """Update a trade with fill information."""

    with session_scope() as session:
        trade = session.get(Trade, trade_id)
        if trade is None:
            LOGGER.error("Trade %s not found for fill update", trade_id)
            return
        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.status = "closed"


def get_recent_trades(limit: int = 50) -> List[Dict[str, Any]]:
    with session_scope() as session:
        stmt = select(Trade).order_by(Trade.timestamp.desc()).limit(limit)
        trades = session.scalars(stmt).all()
    return [trade.as_dict() for trade in trades]


def record_metric(name: str, value: float, metric_date: datetime | None = None) -> None:
    metric_date = metric_date or datetime.utcnow()
    with session_scope() as session:
        metric = Metric(name=name, value=value, metric_date=metric_date.date())
        session.add(metric)


def closed_trades_dataframe() -> pd.DataFrame:
    """Return closed trades as a pandas DataFrame."""

    with session_scope() as session:
        stmt = select(Trade).where(Trade.status == "closed")
        trades = session.scalars(stmt).all()
    if not trades:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "symbol",
                "side",
                "size",
                "entry_price",
                "exit_price",
                "pnl",
                "rationale",
                "confidence",
            ]
        )
    records = [
        {
            "timestamp": trade.timestamp,
            "symbol": trade.symbol,
            "side": trade.side,
            "size": trade.size,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "pnl": trade.pnl,
            "rationale": trade.rationale,
            "confidence": trade.confidence,
            "stop_price": trade.stop_price,
            "take_profit": trade.take_profit,
        }
        for trade in trades
        if trade.exit_price is not None and trade.pnl is not None
    ]
    return pd.DataFrame.from_records(records)


__all__ = [
    "init_db",
    "log_trade_intent",
    "record_fill",
    "get_recent_trades",
    "record_metric",
    "closed_trades_dataframe",
]
