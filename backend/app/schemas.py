"""Pydantic request/response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SnapshotRequest(BaseModel):
    codes: list[str] = Field(
        ...,
        min_length=1,
        description="Stock codes e.g. HK.00700, US.AAPL",
        examples=[["HK.00700", "US.AAPL"]],
    )


class KlineRequest(BaseModel):
    code: str = Field(..., examples=["HK.00700"])
    num: int = Field(60, ge=1, le=500)
    ktype: str = Field("K_DAY", description="K_1M / K_5M / K_DAY / K_WEEK ...")


class AIConfig(BaseModel):
    provider: str = Field("ollama", description="ollama | openai | deepseek | anthropic | gemini | custom")
    api_key: str | None = Field(None, description="API key (not needed for Ollama)")
    base_url: str | None = Field(None, description="Override provider base URL")
    model: str | None = Field(None, description="Override model name")
    temperature: float = Field(0.4, ge=0, le=2)
    max_tokens: int = Field(2048, ge=64, le=8192)


class AnalyzeRequest(BaseModel):
    codes: list[str] = Field(default_factory=list, description="Codes for snapshot")
    include_kline: bool = True
    kline_code: str | None = Field(None, description="Primary code for K-line; defaults to first code")
    kline_num: int = 30
    kline_type: str = "K_DAY"
    question: str | None = None
    language: str = "zh-TW"
    ai: AIConfig = Field(default_factory=AIConfig)
    # Optional: pass pre-fetched market data instead of querying OpenD again
    market_data: dict[str, Any] | list[Any] | None = None


class TestAIRequest(BaseModel):
    ai: AIConfig = Field(default_factory=AIConfig)


class OpenDConfigRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 11111
