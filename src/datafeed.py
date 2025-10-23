"""Market data utilities for the trading bot."""
from __future__ import annotations

import time
from collections import deque
from statistics import mean
from typing import Deque, Dict

from .config import Settings
from .hl_client import HyperliquidClient, Position
from .schemas import MarketState


class MarketDataFeed:
    """Fetch and normalize market data for downstream consumers."""

    def __init__(self, client: HyperliquidClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self._history: Dict[str, Deque[float]] = {
            symbol: deque(maxlen=max(settings.atr_lookback * 5, 20))
            for symbol in settings.symbols
        }

    def _compute_atr(self, symbol: str, latest_price: float) -> float:
        history = self._history[symbol]
        history.append(latest_price)
        if len(history) < 2:
            return max(latest_price * 0.01, 1.0)
        true_ranges = []
        previous = history[0]
        for price in list(history)[1:]:
            true_ranges.append(abs(price - previous))
            previous = price
        window = true_ranges[-self.settings.atr_lookback :]
        if not window:
            return max(latest_price * 0.01, 1.0)
        return max(mean(window), latest_price * 0.001)

    def build_market_state(self, symbol: str, position: Position) -> MarketState:
        price = self.client.get_last_price(symbol)
        atr = self._compute_atr(symbol, price)
        timestamp = int(time.time() * 1000)
        equity = self.client.get_account_equity()
        daily_pnl_pct = self.client.get_daily_pnl_pct()
        return MarketState(
            symbol=symbol,
            price=price,
            atr=atr,
            timestamp=timestamp,
            position_size=position.size if not position.is_flat() else None,
            position_entry=position.entry_price if not position.is_flat() else None,
            equity=equity,
            daily_pnl_pct=daily_pnl_pct,
        )


__all__ = ["MarketDataFeed"]
