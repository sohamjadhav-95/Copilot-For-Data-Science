# models_api/openrouter_models.py — Unified OpenRouter API wrapper
# Single function interface: openrouter_model(model_name, messages, ...) → str
import re
import time

from openai import OpenAI

from core.config import PROVIDER_CONFIGS
from logger import log_api_call, log_error, app_logger


# ═══════════════════════════════════════════════════════════════════════
# CLIENT SINGLETON
# ═══════════════════════════════════════════════════════════════════════

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        cfg = PROVIDER_CONFIGS["openrouter"]
        _client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])
    return _client


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════

def openrouter_model(
    model_name: str,
    messages: list,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    retries: int = 2,
) -> str | None:
    """Call an OpenRouter-hosted model.  Returns cleaned response text or None.

    Args:
        model_name:  Model identifier (e.g. "qwen/qwen3-235b-a22b-thinking-2507")
        messages:    OpenAI-format message list
        temperature: Sampling temperature
        max_tokens:  Max output tokens
        retries:     Number of retry attempts
    """
    client = _get_client()

    for attempt in range(retries):
        t0 = time.time()
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed = (time.time() - t0) * 1000
            result = completion.choices[0].message.content

            if result and result.strip():
                cleaned = _clean_think_tags(result.strip())
                prompt_preview = _extract_preview(messages)
                log_api_call(
                    "openrouter", model_name,
                    prompt_preview, cleaned[:300],
                    elapsed, status="success",
                )
                return cleaned

            log_api_call("openrouter", model_name, "", "", elapsed, status="empty_response")
            app_logger.warning(f"[OPENROUTER] {model_name}: empty response (attempt {attempt + 1})")

        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            err_str = str(e).lower()
            log_api_call("openrouter", model_name, "", "", elapsed, status="error", error=str(e))
            app_logger.warning(f"[OPENROUTER] {model_name} attempt {attempt + 1} failed: {e}")

            if "rate" in err_str or "429" in err_str or "limit" in err_str:
                wait = 3 * (attempt + 1)
                app_logger.info(f"[OPENROUTER] Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif attempt < retries - 1:
                time.sleep(1)

    log_error(
        RuntimeError(f"OpenRouter {model_name}: all attempts exhausted"),
        context="openrouter_model",
    )
    return None


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _clean_think_tags(text: str) -> str:
    """Remove <think>...</think> tags from thinking/reasoning models."""
    if not text:
        return text
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text


def _extract_preview(messages: list) -> str:
    """Extract a short preview from the last message for logging."""
    if not messages:
        return ""
    last = messages[-1].get("content", "")
    return last[:200] if isinstance(last, str) else str(last)[:200]
