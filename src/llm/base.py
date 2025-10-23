"""Base interfaces for LLM-driven trade decisioning."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Settings
from ..schemas import MarketState, TradeDecision


class LLMDecisionError(RuntimeError):
    """Raised when the LLM fails to produce a valid decision."""


class LLMTrader(ABC):
    """Abstract base class for any LLM adapter."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def decide(self, state: MarketState) -> TradeDecision:
        """Return a trade decision for the provided market state."""


__all__ = ["LLMTrader", "LLMDecisionError"]
