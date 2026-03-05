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
    "reasoning": "mistralai/devstral-2-123b-instruct-2512",   # DAG planning, reports, re-planning
    "coding":    "mistralai/devstral-2-123b-instruct-2512",   # Code generation, step execution
    "intent":    "mistralai/devstral-2-123b-instruct-2512",   # Intent classification, summaries
}

PRO_PROVIDER = "nvidia"   # Provider for Pro/Ultra models


# ═══════════════════════════════════════════════════════════════════════
# HELPERS  (used by ModelRouter and engines — do NOT edit below)
# ═══════════════════════════════════════════════════════════════════════

def get_pro_model(task):
    """Return the Pro/Ultra model for a task type: 'reasoning', 'coding', or 'intent'."""
    return PRO_MODELS.get(task, PRO_MODELS["coding"])


def get_pro_provider():
    """Return the provider for Pro/Ultra models."""
    return PRO_PROVIDER


def get_quickrun_model():
    """Return the Quick Run model name."""
    return QUICKRUN_MODEL


def get_quickrun_provider():
    """Return the Quick Run provider."""
    return QUICKRUN_PROVIDER
