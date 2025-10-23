import math

import pytest

from src.config import Settings
from src.execution import decision_to_order
from src.risk import enforce_leverage, position_size
from src.schemas import MarketState, TradeDecision, validate_trade_decision_payload


@pytest.fixture
def settings() -> Settings:
    return Settings.model_validate(
        {
            "HL_ACCOUNT_ADDRESS": "0xabc",
            "HL_SECRET_KEY": "secret",
            "HL_NETWORK": "testnet",
            "BOT_SYMBOLS": "BTC",
            "BASE_RISK_PCT": 0.02,
            "DAILY_LOSS_LIMIT_PCT": 0.05,
            "MAX_CONCURRENT_POS": 2,
            "MAX_LEVERAGE": 5,
            "DRY_RUN": True,
        }
    )


def test_position_size_basic():
    size = position_size(
        equity=10_000,
        entry_price=100.0,
        stop_price=95.0,
        base_risk_pct=0.02,
        slippage_bps=5.0,
    )
    expected = (10_000 * 0.02) / (5.0 + 100.0 * 0.0005)
    assert size == pytest.approx(expected, rel=1e-5)


def test_enforce_leverage_clamps_long_and_short():
    assert enforce_leverage(200, 100, 1, 5_000) == pytest.approx(50.0)
    assert enforce_leverage(-200, 100, 1, 5_000) == pytest.approx(-50.0)


def test_decision_to_order_defaults_and_leverage(settings: Settings):
    state = MarketState(
        symbol="BTC",
        price=100.0,
        atr=2.0,
        timestamp=1,
        equity=10_000.0,
        daily_pnl_pct=0.0,
    )

    decision = TradeDecision(
        symbol="BTC",
        side="long",
        rationale="Test entry",
        confidence=0.8,
        risk_scalar=1.0,
    )

    order = decision_to_order(decision, state, settings)
    assert order is not None
    assert order.side == "buy"
    assert order.stop_price is not None and order.stop_price < state.price
    assert order.take_profit is not None and order.take_profit > state.price
    # leverage cap of 5 should not trigger here
    expected_stop = state.price - state.atr
    expected_tp = state.price + 2 * (state.price - expected_stop)
    assert order.stop_price == pytest.approx(expected_stop, rel=1e-6)
    assert order.take_profit == pytest.approx(expected_tp, rel=1e-6)

    # Ensure leverage clamp activates when exposure is too high
    aggressive = Settings.model_validate(
        {
            "HL_ACCOUNT_ADDRESS": "0xabc",
            "HL_SECRET_KEY": "secret",
            "HL_NETWORK": "testnet",
            "BOT_SYMBOLS": "BTC",
            "BASE_RISK_PCT": 0.5,
            "DAILY_LOSS_LIMIT_PCT": 0.05,
            "MAX_CONCURRENT_POS": 2,
            "MAX_LEVERAGE": 1,
            "DRY_RUN": True,
        }
    )
    aggressive_order = decision_to_order(decision, state, aggressive)
    assert aggressive_order is not None
    max_notional = aggressive.max_leverage * state.equity
    assert aggressive_order.size * state.price == pytest.approx(max_notional, rel=1e-6)

    flat_decision = TradeDecision(
        symbol="BTC",
        side="flat",
        rationale="No trade",
        confidence=0.0,
        risk_scalar=0.0,
    )
    assert decision_to_order(flat_decision, state, settings) is None


def test_trade_decision_schema_validation():
    payload = {
        "symbol": "ETH",
        "side": "short",
        "rationale": "Momentum down",
        "confidence": 0.6,
        "risk_scalar": 1.0,
    }
    decision = validate_trade_decision_payload(payload)
    assert decision.side == "short"

    payload_bad = dict(payload)
    payload_bad["confidence"] = 5
    with pytest.raises(ValueError):
        validate_trade_decision_payload(payload_bad)
