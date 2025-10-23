"""Thin Hyperliquid client wrapper with a dry-run fallback."""
from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass
from typing import Dict

from .config import Settings
from .schemas import OrderIntent

LOGGER = logging.getLogger(__name__)


@dataclass
class Position:
    """In-memory representation of an open position."""

    symbol: str
    size: float = 0.0
    entry_price: float = 0.0

    def is_flat(self) -> bool:
        return abs(self.size) < 1e-9


class HyperliquidClient:
    """Wrap interactions with Hyperliquid with sensible defaults."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._equity = 10_000.0
        self._positions: Dict[str, Position] = {
            symbol: Position(symbol=symbol) for symbol in settings.symbols
        }
        self._last_prices: Dict[str, float] = {
            symbol: 30_000.0 if symbol.upper() == "BTC" else 2_000.0 for symbol in settings.symbols
        }
        LOGGER.debug(
            "Initialized HyperliquidClient in %s mode",
            "dry-run" if settings.dry_run else "live",
        )

    # -- account helpers -------------------------------------------------

    def get_account_equity(self) -> float:
        """Return the currently estimated account equity."""

        return self._equity

    def get_daily_pnl_pct(self) -> float:
        """Return a naive mark-to-market daily PnL percentage."""

        # In dry-run mode we keep this constant. Integrations can override this method.
        return 0.0

    def get_position(self, symbol: str) -> Position:
        """Retrieve the cached position for a symbol."""

        return self._positions[symbol]

    def get_positions(self) -> Dict[str, Position]:
        """Return all tracked positions."""

        return self._positions

    # -- market data -----------------------------------------------------

    def get_last_price(self, symbol: str) -> float:
        """Return a pseudo last price for the requested symbol."""

        base_price = self._last_prices.get(symbol, 1_000.0)
        # Simulate a tiny random walk around the previous close.
        drift = math.sin(time.time() / 60.0) * 0.001
        shock = random.uniform(-0.001, 0.001)
        new_price = max(1.0, base_price * (1 + drift + shock))
        self._last_prices[symbol] = new_price
        return new_price

    def get_recent_prices(self, symbol: str, lookback: int) -> list[float]:
        """Return a synthetic series of recent prices for ATR calculations."""

        prices = [self.get_last_price(symbol)]
        for _ in range(max(lookback - 1, 0)):
            prices.append(self.get_last_price(symbol))
        return prices

    # -- order execution -------------------------------------------------

    def place_order(self, order: OrderIntent) -> None:
        """Execute an order or simply log it when running in dry-run mode."""

        LOGGER.info("Submitting %s order: %s", order.entry_type, order.model_dump())
        if self.settings.dry_run:
            self._apply_fill(order)
            return
        raise NotImplementedError(
            "Live Hyperliquid execution is not implemented in this template."
        )

    def _apply_fill(self, order: OrderIntent) -> None:
        """Rudimentary paper fill handler for dry-run mode."""

        position = self._positions[order.symbol]
        direction = 1 if order.side == "buy" else -1
        fill_price = (
            order.limit_price
            or order.stop_price
            or order.take_profit
            or self.get_last_price(order.symbol)
        )
        size = direction * order.size
        if position.is_flat():
            position.size = size
            position.entry_price = fill_price
        else:
            new_size = position.size + size
            if abs(new_size) < 1e-9:
                pnl = (fill_price - position.entry_price) * position.size
                self._equity += pnl
                LOGGER.info(
                    "Closed position on %s. Realized PnL: %.2f", order.symbol, pnl
                )
                position.size = 0.0
                position.entry_price = 0.0
            else:
                position.entry_price = fill_price
                position.size = new_size


__all__ = ["HyperliquidClient", "Position"]
