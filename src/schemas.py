"""Pydantic schemas shared across the trading backend."""
from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
)


class MarketState(BaseModel):
    """Normalized representation of the current market state for a symbol."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    price: float
    atr: float
    timestamp: int
    position_size: float | None = None
    position_entry: float | None = None
    equity: float
    daily_pnl_pct: float = 0.0

    @field_validator("price", "atr", "equity", mode="after")
    @classmethod
    def validate_positive(cls, value: float, info: ValidationInfo) -> float:
        if value < 0:
            raise ValueError(f"{info.field_name} must be non-negative")
        return value


class TradeDecision(BaseModel):
    """Decision payload returned by the language model."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    side: Literal["long", "short", "flat"]
    rationale: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    stop_price: float | None = Field(default=None, gt=0.0)
    take_profit: float | None = Field(default=None, gt=0.0)
    risk_scalar: float = Field(default=1.0, ge=0.0, le=2.0)

    @field_validator("rationale")
    @classmethod
    def rationale_not_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("rationale must not be empty")
        return text

    @field_validator("stop_price", "take_profit")
    @classmethod
    def positive_optional(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("price levels must be positive")
        return value


class OrderIntent(BaseModel):
    """Normalized representation of an order we intend to place."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    side: Literal["buy", "sell"]
    size: float = Field(gt=0)
    entry_type: Literal["market", "limit"]
    limit_price: float | None = None
    stop_price: float | None = None
    take_profit: float | None = None
    reduce_only: bool = False

    @field_validator("limit_price", "stop_price", "take_profit")
    @classmethod
    def positive_price(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("Order prices must be positive if provided")
        return value


def validate_trade_decision_payload(payload: dict) -> TradeDecision:
    """Validate a JSON payload coming back from the LLM."""

    if not isinstance(payload, dict):
        raise ValueError("Trade decision must be an object")
    try:
        return TradeDecision.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - exercised in tests via ValueError
        raise ValueError(str(exc)) from exc


__all__ = [
    "MarketState",
    "TradeDecision",
    "OrderIntent",
    "validate_trade_decision_payload",
]
