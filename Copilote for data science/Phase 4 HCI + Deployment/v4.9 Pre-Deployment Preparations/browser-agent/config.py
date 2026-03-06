"""
Configuration for the Browser Automation Agent.
All settings are loaded from environment variables with sensible defaults.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — override via environment variables or .env file."""

    # ── Server ──────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Browser ─────────────────────────────────────────────
    HEADLESS: bool = True
    SLOW_MO: int = 0
    BROWSER_TYPE: str = "chromium"

    # ── Default Target ───────────────────────────────────────
    # Can be overridden per-request via the 'model' field
    DEFAULT_TARGET: str = "gpt"  # "gpt" | "claude"

    # ── Timeouts (milliseconds) ─────────────────────────────
    NAVIGATION_TIMEOUT_MS: int = 60_000
    RESPONSE_TIMEOUT_MS: int = 120_000
    ELEMENT_TIMEOUT_MS: int = 15_000

    # ── Session / Auth ──────────────────────────────────────
    GPT_STORAGE_STATE_PATH: str = str(
        Path(__file__).parent / "data" / "gpt_storage_state.json"
    )
    CLAUDE_STORAGE_STATE_PATH: str = str(
        Path(__file__).parent / "data" / "claude_storage_state.json"
    )

    # ── Concurrency ─────────────────────────────────────────
    MAX_CONCURRENT_SESSIONS: int = 3

    # ── Retries ─────────────────────────────────────────────
    RETRY_ATTEMPTS: int = 3
    RETRY_BACKOFF_BASE: float = 2.0

    # ── Logging ─────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = str(Path(__file__).parent / "logs" / "agent.log")

    def storage_state_path(self, target: str) -> str:
        """Return the correct storage state path for a given target."""
        if target == "claude":
            return self.CLAUDE_STORAGE_STATE_PATH
        return self.GPT_STORAGE_STATE_PATH

    model_config = {
        "env_prefix": "AGENT_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
