# core/model_plan_router.py — Centralized model configuration
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  CHANGE MODEL IDs HERE — this is the ONLY file you need to edit    ║
# ╚══════════════════════════════════════════════════════════════════════╝

# ═══════════════════════════════════════════════════════════════════════
# QUICK RUN MODEL  (used by Normal Engine for all plans by default)
# ═══════════════════════════════════════════════════════════════════════

QUICKRUN_MODEL    = "openai/gpt-oss-120b"     # Groq-hosted model for Quick Run
QUICKRUN_PROVIDER = "groq"                     # Provider for Quick Run

# ═══════════════════════════════════════════════════════════════════════
# PRO / ULTRA MODELS  (used in Pro Mode + Ultra Quick Run "High Tier")
# ═══════════════════════════════════════════════════════════════════════
# >>> PUT YOUR MODEL IDs BELOW — swap anytime <<<

PRO_MODELS = {
    # ── Reasoning: GLM-5 with thinking enabled ──────────────────────────
    "reasoning": {
        "model":            "z-ai/glm5",
        "reasoning":        True,
        "extra_body": {
            "chat_template_kwargs": {
                "enable_thinking": True,
                "clear_thinking":  False,
            },
        },
    },
    # ── Coding: GLM-4.7 — reasoning OFF, standard completion ────────────
    "coding": {
        "model":            "z-ai/glm4.7",
        "reasoning":        False,
        "extra_body":       None,
    },
    # ── Intent: Nemotron-3-Nano-30B with thinking enabled ───────────────
    "intent": {
        "model":            "nvidia/nemotron-3-nano-30b-a3b",
        "reasoning":        True,
        "extra_body": {
            "reasoning_budget": 8192,
            "chat_template_kwargs": {
                "enable_thinking": True,
            },
        },
    },
}

PRO_PROVIDER = "nvidia"   # Provider for Pro/Ultra models


# ═══════════════════════════════════════════════════════════════════════
# HELPERS  (used by ModelRouter and engines — do NOT edit below)
# ═══════════════════════════════════════════════════════════════════════

def get_pro_model_config(task: str) -> dict:
    """Return the full config dict for a task: 'reasoning', 'coding', or 'intent'."""
    return PRO_MODELS.get(task, PRO_MODELS["coding"])


def get_pro_model(task: str) -> str:
    """Return just the model ID for a task."""
    return get_pro_model_config(task)["model"]


def get_pro_provider() -> str:
    """Return the provider for Pro/Ultra models."""
    return PRO_PROVIDER


def get_quickrun_model() -> str:
    """Return the Quick Run model name."""
    return QUICKRUN_MODEL


def get_quickrun_provider() -> str:
    """Return the Quick Run provider."""
    return QUICKRUN_PROVIDER
