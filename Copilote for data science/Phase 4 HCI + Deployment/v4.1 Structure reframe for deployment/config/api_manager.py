# config/api_manager.py
from openai import OpenAI
import os

# Centralized API Client Configuration
# Using hardcoded key and base URL as requested for this phase of optimization.
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

# Model configuration
MODEL_NAME = "openai/gpt-oss-120b:free"

def get_client():
    """Returns the configured OpenAI client."""
    return client

def get_model_name():
    """Returns the model name to be used."""
    return MODEL_NAME
