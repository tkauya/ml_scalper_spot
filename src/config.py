"""Configuration utilities for the Hyperliquid LLM bot."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    hl_account_address: str = Field(..., alias="HL_ACCOUNT_ADDRESS")
    hl_secret_key: str = Field(..., alias="HL_SECRET_KEY")
    hl_network: str = Field("testnet", alias="HL_NETWORK")

    bot_symbols: List[str] = Field(..., alias="BOT_SYMBOLS")
    base_risk_pct: float = Field(..., alias="BASE_RISK_PCT")
    daily_loss_limit_pct: float = Field(..., alias="DAILY_LOSS_LIMIT_PCT")
    max_concurrent_pos: int = Field(..., alias="MAX_CONCURRENT_POS")
    max_leverage: float = Field(..., alias="MAX_LEVERAGE")

    dry_run: bool = Field(default=False, alias="DRY_RUN")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    cool_off_minutes: int = Field(default=15, alias="COOL_OFF_MINUTES")
    max_open_r_multiple: float = Field(default=2.0, alias="MAX_OPEN_R_MULTIPLE")
    slippage_bps: float = Field(default=5.0, alias="SLIPPAGE_BPS")
    atr_lookback: int = Field(default=14, alias="ATR_LOOKBACK")
    ml_gate_path: str = Field(default="models/win1R_gate.pkl", alias="ML_GATE_PATH")
    database_url: str = Field(default="sqlite:///hyperliquid_llm_bot.db", alias="DATABASE_URL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    @field_validator("bot_symbols", mode="before")
    @classmethod
    def split_symbols(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            symbols = [item.strip().upper() for item in value.split(",") if item.strip()]
            if not symbols:
                raise ValueError("BOT_SYMBOLS cannot be empty")
            return symbols
        if isinstance(value, list) and value:
            return [str(item).upper() for item in value]
        raise ValueError("BOT_SYMBOLS must contain at least one symbol")

    @field_validator("hl_network")
    @classmethod
    def validate_network(cls, value: str) -> str:
        network = value.lower()
        if network not in {"mainnet", "testnet"}:
            raise ValueError("HL_NETWORK must be either 'mainnet' or 'testnet'")
        return network

    @property
    def symbols(self) -> list[str]:
        """Return the configured trading symbols."""
        return self.bot_symbols


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load application settings once and cache the result."""

    load_dotenv(override=False)
    settings = Settings()
    return settings


__all__ = ["Settings", "load_settings"]
