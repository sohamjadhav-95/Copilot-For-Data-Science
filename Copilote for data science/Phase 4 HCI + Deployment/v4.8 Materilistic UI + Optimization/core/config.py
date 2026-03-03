# core/config.py — Centralized configuration for Data Science Copilot
# Extends the root config.py with Pro Mode settings and model tier definitions.
import os

# ═══════════════════════════════════════════════════════════════════════
# BASE PATHS  (derived from project root)
# ═══════════════════════════════════════════════════════════════════════

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Re-export legacy config values so other modules can import from one place
SECRET_KEY = os.environ.get("SECRET_KEY", "ds-copilot-secret-key-change-in-production")
SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(PROJECT_ROOT, 'database', 'copilot.db')}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, "uploads")
MODIFIED_FOLDER = os.path.join(PROJECT_ROOT, "modified_files")
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
JWT_EXPIRY_HOURS = 24


# ═══════════════════════════════════════════════════════════════════════
# PRO MODE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

# Dataset size limit for Pro Mode (rows).  User is warned above this threshold.
PRO_MAX_ROWS = int(os.environ.get("PRO_MAX_ROWS", 500_000))
PRO_MAX_CONTENT_LENGTH = int(os.environ.get("PRO_MAX_CONTENT_LENGTH", 100 * 1024 * 1024))  # 100 MB

# DAG execution limits
PRO_MAX_DAG_NODES = 20          # maximum nodes in a single DAG plan
PRO_NODE_RETRY_LIMIT = 1        # retry once on failure
PRO_EXECUTION_TIMEOUT = 300     # seconds per node execution
PRO_MAX_REPLAN_COUNT = 2        # hard cap — prevents infinite replan loops
PRO_MAX_ARTIFACT_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB per artifact (e.g. chart PNG)
PRO_MAX_ARTIFACTS = 20          # max artifacts stored before pruning oldest
PRO_MAX_HISTORY_ENTRIES = 100   # cap execution history list length



# ═══════════════════════════════════════════════════════════════════════
# MODEL TIERS — used by ModelRouter
# ═══════════════════════════════════════════════════════════════════════

MODEL_TIERS = {
    "heavy": {
        "description": "Heavy reasoning model — DAG planning, final reports, re-planning",
        "groq": None,  # Groq does not host this model
        "openrouter": "openai/gpt-oss-120b",
    },
    "mid": {
        "description": "Mid-tier model — code generation, step execution",
        "groq": "openai/gpt-oss-120b",
        "openrouter": "openai/gpt-oss-120b",
    },
    "light": {
        "description": "Light model — intent classification, complexity detection",
        "groq": "openai/gpt-oss-20b",
        "openrouter": "openai/gpt-oss-20b",
    },
}

# Provider priority: which provider to try first per tier
PROVIDER_PRIORITY = {
    "heavy": ["openrouter"],           # only available on OpenRouter
    "mid":   ["groq", "openrouter"],   # Groq preferred for speed
    "light": ["groq", "openrouter"],   # Groq preferred for speed
}


# ═══════════════════════════════════════════════════════════════════════
# PROVIDER CREDENTIALS
# ═══════════════════════════════════════════════════════════════════════

PROVIDER_CONFIGS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.environ.get(
            "GROQ_API_KEY",
            "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"
        ),
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.environ.get(
            "OPENROUTER_API_KEY",
            "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"
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════
# DATASET PROFILER SETTINGS
# ═══════════════════════════════════════════════════════════════════════

PROFILER_SAMPLE_THRESHOLD = 10_000   # rows above which sampling is used
PROFILER_SAMPLE_SIZE = 5_000         # number of rows to sample
PROFILER_CORRELATION_THRESHOLD = 0.7 # min |r| for high-correlation pairs
PROFILER_ID_UNIQUE_RATIO = 0.95      # unique ratio to flag potential ID columns
PROFILER_MAX_SAMPLE_VALUES = 5       # max sample values per column
