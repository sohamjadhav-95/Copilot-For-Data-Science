"""
Pydantic models for API request/response validation.
"""
from typing import Literal
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    prompt: str = Field(
        ..., min_length=1, max_length=32_000,
        description="The prompt to send.",
        examples=["Explain quantum computing in simple terms."],
    )
    model: Literal["gpt", "claude"] = Field(
        default="gpt",
        description="Which model/site to target: 'gpt' (ChatGPT) or 'claude' (Claude.ai).",
    )


class ChatResponse(BaseModel):
    success: bool = True
    prompt: str
    response: str
    model: str
    duration_ms: int


class SessionResponse(BaseModel):
    success: bool = True
    message: str
    target: str
    storage_state_path: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    headless: bool
    max_concurrent: int
    available_models: list[str] = ["gpt", "claude"]
