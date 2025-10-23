"""FastAPI application exposing read-only bot status."""
from __future__ import annotations

import logging

from fastapi import FastAPI

from src.config import load_settings
from src.storage import get_recent_trades, init_db

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="Hyperliquid LLM Bot Status")


@app.on_event("startup")
def on_startup() -> None:
    settings = load_settings()
    init_db(settings)
    LOGGER.info("Status API initialised")


@app.get("/status")
def read_status(limit: int = 50) -> dict:
    trades = get_recent_trades(limit=limit)
    return {"status": "ok", "trades": trades, "error": None}
