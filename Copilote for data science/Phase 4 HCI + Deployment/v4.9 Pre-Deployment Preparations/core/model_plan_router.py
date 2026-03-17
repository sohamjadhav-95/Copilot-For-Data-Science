# core/model_plan_router.py — Centralized model configuration
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  CHANGE MODEL IDs HERE — this is the ONLY file you need to edit    ║
# ╚══════════════════════════════════════════════════════════════════════╝

# ═══════════════════════════════════════════════════════════════════════
# DEFAULT MODEL  (used by both Quick Run and Workflow for all users)
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_MODEL    = "openai/gpt-oss-120b"   # Groq-hosted model for all modes
DEFAULT_PROVIDER = "groq"                  # Provider for default mode

# Aliases for backward compatibility
QUICKRUN_MODEL    = DEFAULT_MODEL
QUICKRUN_PROVIDER = DEFAULT_PROVIDER

# ═══════════════════════════════════════════════════════════════════════
# MAX POWER MODEL TARGETS  (Google Gemini API)
# Activated when Pro/Ultra users enable the Max Power toggle.
# ═══════════════════════════════════════════════════════════════════════

MAX_POWER_MODELS = {
    "intent":    "gemini-2.0-flash-lite",  # fastest — near-zero latency for classification
    "coding":    "gemini-2.0-flash",        # best code generation accuracy
    "reasoning": "gemini-2.0-flash",        # planning (with thinking budget)
}


# ═══════════════════════════════════════════════════════════════════════
# HELPERS  (used by ModelRouter and engines — do NOT edit below)
# ═══════════════════════════════════════════════════════════════════════

def get_max_power_model(task: str) -> str:
    """Return the Gemini model ID for a Max Power task."""
    return MAX_POWER_MODELS.get(task, "gemini-2.0-flash")


def get_default_model() -> str:
    """Return the default model name (Groq)."""
    return DEFAULT_MODEL


def get_default_provider() -> str:
    """Return the default provider."""
    return DEFAULT_PROVIDER


# Legacy aliases (keep for backward compat with pro_engine.py etc.)
def get_pro_model(task: str) -> str:
    """Return the model ID for a task. In default mode, always returns the Groq model."""
    return DEFAULT_MODEL

def get_pro_model_config(task: str) -> dict:
    """Return config dict for a task. Default mode uses Groq for all tasks."""
    return {
        "model": DEFAULT_MODEL,
        "reasoning": False,
        "extra_body": None,
    }

def get_pro_provider() -> str:
    """Return the provider. Always Groq in default mode."""
    return DEFAULT_PROVIDER

def get_quickrun_model() -> str:
    """Return the Quick Run model name."""
    return DEFAULT_MODEL

def get_quickrun_provider() -> str:
    """Return the Quick Run provider."""
    return DEFAULT_PROVIDER
