# Hyperliquid LLM Bot

**Warning: always run on Hyperliquid testnet before considering mainnet deployment.**

This repository contains a production-focused Python backend for an automated trading bot that delegates idea generation to a pluggable language model, enforces strict risk controls, tracks results in SQLite, exposes a read-only status API, and ships with a lightweight machine learning gate for filtering trades.

## 60-second quickstart (testnet)

```bash
cp .env.example .env  # populate with your testnet keys
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
make run  # loops in DRY_RUN mode until you provide a live execution adapter
```

The default configuration keeps the LLM disabled when no API key is present, so the bot safely stays flat.

## Environment configuration

Update `.env` with your Hyperliquid credentials, trading parameters, and optional overrides:

- `HL_ACCOUNT_ADDRESS`, `HL_SECRET_KEY`, `HL_NETWORK`
- Symbol list and risk guardrails (`BOT_SYMBOLS`, `BASE_RISK_PCT`, `DAILY_LOSS_LIMIT_PCT`, `MAX_CONCURRENT_POS`, `MAX_LEVERAGE`)
- Optional knobs: `SLIPPAGE_BPS`, `COOL_OFF_MINUTES`, `ML_GATE_PATH`, `DRY_RUN`

Environment variables are validated on startup; missing values abort the process with a clear error.

## Running the bot

```bash
make run
```

The loop fetches synthetic data in dry-run mode, requests a trade decision, enforces position sizing, and logs intents into SQLite (`hyperliquid_llm_bot.db`).

To expose the read-only status API:

```bash
make api  # serves GET /status via FastAPI
```

## Risk controls

Key protections implemented in `src/risk.py` and `src/execution.py`:

- Per-trade risk sizing via `position_size` (risk budget = `BASE_RISK_PCT * equity`).
- Automatic default stops and 2R take-profits when the LLM omits levels.
- Leverage clamp on every order (`MAX_LEVERAGE`).
- Max concurrent position enforcement (`MAX_CONCURRENT_POS`).
- Aggregate open risk limit (`MAX_OPEN_R_MULTIPLE`, default 2R).
- Daily kill-switch triggered by `DAILY_LOSS_LIMIT_PCT`.
- Cool-off period after stop-outs.
- All intents logged to SQLite before submission for full auditability.

## Swapping in a real GPT client

`ChatGPT5Trader` wraps a JSON-only GPT-style endpoint. To plug in another provider, implement `LLMTrader.decide()` (see `src/llm/base.py`) and wire it into `StrategyController`. Example pseudocode:

```python
from src.llm.base import LLMTrader
from src.schemas import MarketState, TradeDecision

class MyCustomTrader(LLMTrader):
    def decide(self, state: MarketState) -> TradeDecision:
        payload = {...}  # build provider-specific request
        response = call_provider(payload)
        parsed = validate_trade_decision_payload(response)
        return parsed
```

Then update `StrategyController` to instantiate `MyCustomTrader` instead of `ChatGPT5Trader`.

## Machine-learning gate

`train_ml.py` reads closed trades, labels outcomes that achieved at least +1R, and trains a tiny `GradientBoostingClassifier`. To train:

```bash
python train_ml.py
```

When a gate model exists (default path `models/win1R_gate.pkl`), every LLM decision passes through `MLGate`: low probabilities (<0.4) are skipped, mid-confidence trades are scaled down, and strong signals flow through unchanged.

## Observability

All lifecycle events log via the standard library logger. Metrics and trades are persisted in SQLite (`src/storage.py`), and `src/evaluator.py` can compute running performance summaries for reporting or dashboards.

## Tests, linting, and formatting

```bash
make test   # pytest
make lint   # ruff
make fmt    # black + isort
```

## Development checklist

- Ensure `.env` never contains mainnet credentials during development.
- Keep `DRY_RUN=1` until you have a verified Hyperliquid execution adapter.
- Re-run `python train_ml.py` whenever you accumulate new closed trades to refresh the risk gate.

Happy (testnet) trading!
