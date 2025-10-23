"""Prompt templates shared by strategy adapters."""
from __future__ import annotations

from textwrap import dedent

from ..schemas import MarketState

SYSTEM_PROMPT = dedent(
    """
    You are GPT-5, a disciplined derivative swing trader for the Hyperliquid testnet.
    You must respond with a single JSON object matching the provided schema.
    Do not include any commentary outside the JSON. Never break risk constraints.
    """
)

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "side": {"type": "string", "enum": ["long", "short", "flat"]},
        "rationale": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "stop_price": {"type": "number"},
        "take_profit": {"type": "number"},
        "risk_scalar": {"type": "number", "minimum": 0, "maximum": 2},
    },
    "required": ["symbol", "side", "rationale", "confidence", "risk_scalar"],
    "additionalProperties": False,
}


def render_market_state(state: MarketState) -> str:
    """Render the market state as a textual instruction."""

    return dedent(
        f"""
        Provide a trading decision for symbol {state.symbol}.
        Current price: {state.price:.2f}
        ATR ({state.symbol}): {state.atr:.4f}
        Position size: {state.position_size or 0.0}
        Position entry: {state.position_entry or 0.0}
        Account equity: {state.equity:.2f}
        Daily PnL pct: {state.daily_pnl_pct:.4f}

        Respond with JSON exactly matching this schema:
        {JSON_SCHEMA}
        """
    ).strip()


__all__ = ["SYSTEM_PROMPT", "JSON_SCHEMA", "render_market_state"]
