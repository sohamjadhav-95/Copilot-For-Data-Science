# api_config.py -- Groq API Configuration
# Groq (gpt-oss-120b) is the SOLE provider for default mode.
# GEMINI_API_KEY is used when Max Power mode is enabled.
import os
from openai import OpenAI

# ═══════════════════════════════════════════════════════════════════════
# GEMINI API KEY  (Max Power mode — Google Gemini models)
# ═══════════════════════════════════════════════════════════════════════

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    "AIzaSyBxm9imbaUG9fDUziA5xU66NfXlx2FVtgg"   # fallback key (replace with your own)
)

# ═══════════════════════════════════════════════════════════════════════
# PROVIDER CONFIGURATION
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
}

# ═══════════════════════════════════════════════════════════════════════
# ACTIVE PROVIDER STATE  (Groq is the only provider)
# ═══════════════════════════════════════════════════════════════════════

_active_provider = "groq"
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
    """Switch provider — currently only 'groq' is supported."""
    global _active_provider, _client
    provider_name = provider_name.lower().strip()
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider_name}'. Available: {list(PROVIDERS.keys())}")
    _active_provider = provider_name
    _client = _build_client(provider_name)
    return _active_provider
