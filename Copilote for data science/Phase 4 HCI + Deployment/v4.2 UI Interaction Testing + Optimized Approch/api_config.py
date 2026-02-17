# api_config.py — Centralized API client configuration
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

MODEL_NAME = "openai/gpt-oss-120b:free"
