"""Risk management primitives."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .config import Settings
from .schemas import MarketState

LOGGER = logging.getLogger(__name__)


def position_size(
    *,
    equity: float,
    entry_price: float,
    stop_price: float,
    base_risk_pct: float,
    slippage_bps: float,
) -> float:
    """Return the maximum position size that respects the per-trade risk budget."""

    if stop_price <= 0 or entry_price <= 0:
        raise ValueError("Prices must be positive")
    if abs(entry_price - stop_price) < 1e-9:
        raise ValueError("Stop price cannot equal entry price")
    risk_budget = equity * base_risk_pct
    slippage_allowance = entry_price * (slippage_bps / 10_000)
    risk_per_unit = abs(entry_price - stop_price) + slippage_allowance
    if risk_per_unit <= 0:
        raise ValueError("Invalid risk per unit calculation")
    size = risk_budget / risk_per_unit
    return max(size, 0.0)


def enforce_leverage(size: float, entry_price: float, max_leverage: float, equity: float) -> float:
    """Clamp position size so that notional exposure does not exceed leverage limits."""

    notional = abs(size * entry_price)
    max_notional = max_leverage * equity
    if max_notional <= 0:
        return 0.0
    if notional <= max_notional:
        return size
    clamped_size = max_notional / entry_price
    return clamped_size if size >= 0 else -clamped_size


def calculate_open_risk(size: float, entry_price: float, stop_price: float, equity: float, base_risk_pct: float) -> float:
    """Calculate the open risk contribution of a trade in units of R."""

    risk_budget = equity * base_risk_pct
    if risk_budget <= 0:
        return 0.0
    return (abs(size) * abs(entry_price - stop_price)) / risk_budget


@dataclass
class DailyRiskManager:
    """Track daily kill-switches and cool-off periods."""

    settings: Settings
    kill_switch_triggered: bool = False
    last_reset: datetime = field(default_factory=lambda: datetime.utcnow())
    cool_off: dict[str, datetime] = field(default_factory=dict)
    open_r_by_symbol: dict[str, float] = field(default_factory=dict)

    def reset_if_needed(self, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        if now.date() != self.last_reset.date():
            LOGGER.info("Resetting daily risk counters")
            self.kill_switch_triggered = False
            self.cool_off.clear()
            self.open_r_by_symbol.clear()
            self.last_reset = now

    def register_market_state(self, state: MarketState) -> None:
        if state.daily_pnl_pct <= -self.settings.daily_loss_limit_pct:
            if not self.kill_switch_triggered:
                LOGGER.error(
                    "Daily kill switch triggered: daily PnL %.2f%% <= limit %.2f%%",
                    state.daily_pnl_pct * 100,
                    self.settings.daily_loss_limit_pct * 100,
                )
            self.kill_switch_triggered = True

    def register_stopout(self, symbol: str, now: datetime | None = None) -> None:
        now = now or datetime.utcnow()
        cooldown = timedelta(minutes=self.settings.cool_off_minutes)
        self.cool_off[symbol] = now + cooldown
        LOGGER.warning("Entering cool-off for %s until %s", symbol, self.cool_off[symbol])

    def in_cool_off(self, symbol: str, now: datetime | None = None) -> bool:
        now = now or datetime.utcnow()
        expiry = self.cool_off.get(symbol)
        if not expiry:
            return False
        if now >= expiry:
            self.cool_off.pop(symbol, None)
            return False
        return True

    def can_open_new_position(self, total_open_positions: int) -> bool:
        return total_open_positions < self.settings.max_concurrent_pos

    def can_add_risk(self, symbol: str, proposed_r: float) -> bool:
        current_total = sum(self.open_r_by_symbol.values())
        symbol_current = self.open_r_by_symbol.get(symbol, 0.0)
        return (current_total - symbol_current + proposed_r) <= self.settings.max_open_r_multiple

    def add_open_risk(self, symbol: str, r_multiple: float) -> None:
        self.open_r_by_symbol[symbol] = r_multiple

    def release_open_risk(self, symbol: str) -> None:
        self.open_r_by_symbol.pop(symbol, None)


__all__ = [
    "position_size",
    "enforce_leverage",
    "calculate_open_risk",
    "DailyRiskManager",
]
