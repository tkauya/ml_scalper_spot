"""Strategy routing and ML gating logic."""
from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np

from ..config import Settings
from ..schemas import MarketState, TradeDecision
from ..llm.chatgpt5 import ChatGPT5Trader

LOGGER = logging.getLogger(__name__)


class MLGate:
    """Simple classifier-based gate for trade decisions."""

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self.model = None
        if model_path.exists():
            try:
                self.model = joblib.load(model_path)
                LOGGER.info("Loaded ML gate from %s", model_path)
            except Exception as exc:  # pragma: no cover - load errors are rare
                LOGGER.error("Failed to load ML gate: %s", exc)
                self.model = None

    def apply(self, decision: TradeDecision, state: MarketState) -> TradeDecision:
        if self.model is None or decision.side == "flat":
            return decision
        features = np.array(
            [
                state.price,
                state.atr,
                decision.confidence,
                decision.risk_scalar,
            ]
        ).reshape(1, -1)
        try:
            proba = float(self.model.predict_proba(features)[0][1])
        except Exception as exc:  # pragma: no cover - safety belt
            LOGGER.error("ML gate inference failed: %s", exc)
            return decision
        if proba < 0.4:
            LOGGER.info("ML gate rejected trade on %s (p=%.2f)", decision.symbol, proba)
            return TradeDecision(
                symbol=decision.symbol,
                side="flat",
                rationale=f"Rejected by ML gate (p={proba:.2f})",
                confidence=decision.confidence,
                stop_price=decision.stop_price,
                take_profit=decision.take_profit,
                risk_scalar=0.0,
            )
        if proba < 0.6:
            LOGGER.info("ML gate scaling trade on %s (p=%.2f)", decision.symbol, proba)
            return TradeDecision(
                symbol=decision.symbol,
                side=decision.side,
                rationale=decision.rationale + " | scaled by ML gate",
                confidence=decision.confidence,
                stop_price=decision.stop_price,
                take_profit=decision.take_profit,
                risk_scalar=max(decision.risk_scalar * 0.5, 0.1),
            )
        LOGGER.debug("ML gate accepted trade on %s (p=%.2f)", decision.symbol, proba)
        return decision


class StrategyController:
    """Route market states through the active decision stack."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.primary_model = ChatGPT5Trader(settings)
        self.ml_gate = MLGate(Path(settings.ml_gate_path))

    def decide(self, state: MarketState) -> TradeDecision:
        decision = self.primary_model.decide(state)
        return self.ml_gate.apply(decision, state)


__all__ = ["StrategyController", "MLGate"]
