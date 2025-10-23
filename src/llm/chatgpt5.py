"""Adapter for a GPT-5 style JSON-constrained trading model."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

import httpx

from ..schemas import TradeDecision, validate_trade_decision_payload
from ..strategy import prompts
from .base import LLMDecisionError, LLMTrader

LOGGER = logging.getLogger(__name__)


class ChatGPT5Trader(LLMTrader):
    """LLM adapter that enforces a strict JSON schema."""

    MODEL_NAME = "gpt-5-trader"
    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self.api_key = settings.llm_api_key
        self._client: httpx.Client | None = None
        if self.api_key:
            self._client = httpx.Client(timeout=30.0)

    def decide(self, state) -> TradeDecision:
        if not self.api_key:
            return TradeDecision(
                symbol=state.symbol,
                side="flat",
                rationale="LLM API key not configured; staying flat.",
                confidence=0.0,
                risk_scalar=0.0,
            )

        payload = self._build_payload(state)
        try:
            response_json = self._call_model(payload)
            decision = validate_trade_decision_payload(response_json)
            return decision
        except (json.JSONDecodeError, LLMDecisionError, ValueError) as exc:
            LOGGER.error("LLM decision failed: %s", exc)
            raise LLMDecisionError(str(exc)) from exc

    def _build_payload(self, state) -> Dict[str, Any]:
        return {
            "model": self.MODEL_NAME,
            "messages": [
                {"role": "system", "content": prompts.SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": prompts.render_market_state(state),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

    def _call_model(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._client is None:
            raise LLMDecisionError("HTTP client not initialised")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = self._client.post(self.API_URL, headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMDecisionError("Malformed response from GPT-5 endpoint") from exc
        return json.loads(content)


__all__ = ["ChatGPT5Trader"]
