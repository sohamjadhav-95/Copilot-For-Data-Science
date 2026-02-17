# api_config.py -- Centralized API client configuration
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

# Primary model for all tasks (most reliable free model)
MODEL_NAME = "openai/gpt-oss-120b:free"

# Lighter model for intent classification (fallback to MODEL_NAME if unavailable)
MODEL_LITE = "openai/gpt-oss-20b:free"

# Coder model for code generation
MODEL_CODER = "qwen/qwen3-coder:free"
