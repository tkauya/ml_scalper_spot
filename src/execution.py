"""Order construction and execution helpers."""
from __future__ import annotations

import logging
from typing import Optional

from .config import Settings
from .hl_client import HyperliquidClient
from .risk import calculate_open_risk, enforce_leverage, position_size
from .schemas import MarketState, OrderIntent, TradeDecision
from .storage import log_trade_intent

LOGGER = logging.getLogger(__name__)


def _default_stop(decision: TradeDecision, state: MarketState) -> float:
    atr_buffer = max(state.atr, state.price * 0.001)
    if decision.side == "long":
        return max(0.01, state.price - atr_buffer)
    if decision.side == "short":
        return state.price + atr_buffer
    raise ValueError("Unsupported side for stop computation")


def _default_take_profit(decision: TradeDecision, state: MarketState, stop_price: float) -> float:
    risk_per_unit = abs(state.price - stop_price)
    if decision.side == "long":
        return state.price + 2 * risk_per_unit
    return max(0.01, state.price - 2 * risk_per_unit)


def decision_to_order(
    decision: TradeDecision,
    state: MarketState,
    settings: Settings,
) -> Optional[OrderIntent]:
    """Convert an LLM trade decision into an executable order intent."""

    if decision.side == "flat":
        LOGGER.debug("LLM requested flat position for %s", decision.symbol)
        return None

    stop_price = decision.stop_price or _default_stop(decision, state)
    if decision.side == "long" and stop_price >= state.price:
        stop_price = _default_stop(decision, state)
    if decision.side == "short" and stop_price <= state.price:
        stop_price = _default_stop(decision, state)

    take_profit = decision.take_profit or _default_take_profit(decision, state, stop_price)

    raw_size = position_size(
        equity=state.equity,
        entry_price=state.price,
        stop_price=stop_price,
        base_risk_pct=settings.base_risk_pct,
        slippage_bps=settings.slippage_bps,
    )
    size_multiplier = max(decision.risk_scalar, 0.0)
    proposed_size = raw_size * size_multiplier
    if proposed_size <= 0:
        LOGGER.info("Risk scalar resulted in zero size for %s", decision.symbol)
        return None

    signed_size = proposed_size if decision.side == "long" else -proposed_size
    signed_size = enforce_leverage(signed_size, state.price, settings.max_leverage, state.equity)
    if abs(signed_size) < 1e-9:
        LOGGER.warning("Order on %s blocked by leverage clamp", decision.symbol)
        return None

    side = "buy" if signed_size > 0 else "sell"
    order = OrderIntent(
        symbol=decision.symbol,
        side=side,
        size=abs(signed_size),
        entry_type="market",
        stop_price=stop_price,
        take_profit=take_profit,
        reduce_only=False,
    )
    return order


def submit_order(
    order: OrderIntent,
    decision: TradeDecision,
    state: MarketState,
    settings: Settings,
    client: HyperliquidClient,
) -> float:
    """Submit an order and return the open risk multiple."""

    open_risk = calculate_open_risk(
        size=order.size,
        entry_price=state.price,
        stop_price=order.stop_price or state.price,
        equity=state.equity,
        base_risk_pct=settings.base_risk_pct,
    )

    log_trade_intent(
        symbol=order.symbol,
        side=order.side,
        size=order.size,
        entry_price=state.price,
        stop_price=order.stop_price,
        take_profit=order.take_profit,
        rationale=decision.rationale,
        confidence=decision.confidence,
    )

    try:
        client.place_order(order)
    except NotImplementedError:
        LOGGER.error("Live execution not implemented; run in DRY_RUN=1 mode.")
        raise
    return open_risk


__all__ = ["decision_to_order", "submit_order"]
