# api_config.py -- Dual-Provider API Configuration
# Groq (gpt-oss-120b) is PRIMARY for speed. OpenRouter is FALLBACK only.
import os
from openai import OpenAI

# ═══════════════════════════════════════════════════════════════════════
# PROVIDER CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════════

PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.environ.get(
            "GROQ_API_KEY",
            "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"
        ),
        "models": {
            "primary": "openai/gpt-oss-120b",
            "lite": "openai/gpt-oss-20b",
            "coder": "openai/gpt-oss-120b",
        },
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.environ.get(
            "OPENROUTER_API_KEY",
            "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"
        ),
        "models": {
            # Use FAST non-thinking models for fallback (not qwen3-thinking)
            "primary": "openai/gpt-oss-120b:free",
            "lite": "openai/gpt-oss-20b:free",
            "coder": "openai/gpt-oss-120b:free",
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════
# ACTIVE PROVIDER STATE  (Groq is default / prioritized for speed)
# ═══════════════════════════════════════════════════════════════════════

_active_provider = os.environ.get("API_PROVIDER", "groq")
_client = None


def _build_client(provider_name):
    cfg = PROVIDERS[provider_name]
    return OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])


def get_client():
    global _client
    if _client is None:
        _client = _build_client(_active_provider)
    return _client


def get_model(role="primary"):
    return PROVIDERS[_active_provider]["models"].get(role, PROVIDERS[_active_provider]["models"]["primary"])


def get_active_provider():
    return _active_provider


def switch_provider(provider_name):
    global _active_provider, _client
    provider_name = provider_name.lower().strip()
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider_name}'. Available: {list(PROVIDERS.keys())}")
    _active_provider = provider_name
    _client = _build_client(provider_name)
    return _active_provider


def auto_fallback_on_error():
    global _active_provider, _client
    others = [p for p in PROVIDERS if p != _active_provider]
    if not others:
        return None
    new_provider = others[0]
    _active_provider = new_provider
    _client = _build_client(new_provider)
    return new_provider
