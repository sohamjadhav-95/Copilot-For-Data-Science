# models_api/nvidia_models.py — NVIDIA API wrapper
# Supports both standard completion and streaming reasoning models (GLM-5, Nemotron).
import re
import time

from openai import OpenAI

from logger import log_api_call, log_error, app_logger


# ═══════════════════════════════════════════════════════════════════════
# CLIENT SINGLETON
# ═══════════════════════════════════════════════════════════════════════

_client = None

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_API_KEY  = "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"


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)
    return _client


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════

def nvidia_model(
    model_name: str,
    messages: list,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    retries: int = 2,
    extra_body: dict | None = None,
    use_reasoning: bool = False,
) -> str | None:
    """Call an NVIDIA-hosted model.

    For reasoning models (use_reasoning=True), uses streaming to collect
    reasoning_content chain-of-thought + final content, returns only content.
    For standard models, uses non-streaming completion.

    Args:
        model_name:    Model identifier (e.g. 'z-ai/glm4.7')
        messages:      OpenAI-format message list
        temperature:   Sampling temperature
        max_tokens:    Max output tokens
        retries:       Number of retry attempts
        extra_body:    Extra kwargs forwarded to the NVIDIA API (e.g. enable_thinking)
        use_reasoning: If True, stream response and strip reasoning_content

    Returns:
        Cleaned final response text, or None on failure.
    """
    client = _get_client()

    kwargs: dict = dict(
        model=model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if extra_body:
        kwargs["extra_body"] = extra_body

    for attempt in range(retries):
        t0 = time.time()
        try:
            if use_reasoning:
                result = _call_streaming(client, kwargs)
            else:
                result = _call_standard(client, kwargs)

            elapsed = (time.time() - t0) * 1000

            if result and result.strip():
                cleaned = _clean_think_tags(result.strip())
                prompt_preview = _extract_preview(messages)
                log_api_call(
                    "nvidia", model_name,
                    prompt_preview, cleaned[:300],
                    elapsed, status="success",
                )
                return cleaned

            elapsed = (time.time() - t0) * 1000
            log_api_call("nvidia", model_name, "", "", elapsed, status="empty_response")
            app_logger.warning(f"[NVIDIA] {model_name}: empty response (attempt {attempt + 1})")

        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            err_str = str(e).lower()
            log_api_call("nvidia", model_name, "", "", elapsed, status="error", error=str(e))
            app_logger.warning(f"[NVIDIA] {model_name} attempt {attempt + 1} failed: {e}")

            if "rate" in err_str or "429" in err_str or "limit" in err_str:
                wait = 3 * (attempt + 1)
                app_logger.info(f"[NVIDIA] Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif attempt < retries - 1:
                time.sleep(1)

    log_error(RuntimeError(f"NVIDIA {model_name}: all attempts exhausted"), context="nvidia_model")
    return None


# ═══════════════════════════════════════════════════════════════════════
# INTERNAL CALL STRATEGIES
# ═══════════════════════════════════════════════════════════════════════

def _call_standard(client: OpenAI, kwargs: dict) -> str | None:
    """Non-streaming call — used for coding model (GLM-4.7)."""
    completion = client.chat.completions.create(**kwargs)
    return completion.choices[0].message.content


def _call_streaming(client: OpenAI, kwargs: dict) -> str | None:
    """Streaming call — captures reasoning_content + content separately.

    Reasoning content (chain-of-thought) is logged at DEBUG level but not
    returned to the caller. Only the final content is returned.
    """
    content_parts: list[str] = []
    reasoning_parts: list[str] = []

    stream = client.chat.completions.create(**kwargs, stream=True)

    for chunk in stream:
        if not getattr(chunk, "choices", None):
            continue
        if not chunk.choices or getattr(chunk.choices[0], "delta", None) is None:
            continue

        delta = chunk.choices[0].delta

        # Capture internal reasoning (chain-of-thought) — not returned
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            reasoning_parts.append(reasoning)

        # Capture final output content
        if getattr(delta, "content", None) is not None:
            content_parts.append(delta.content)

    final_content = "".join(content_parts).strip()

    if reasoning_parts:
        reasoning_text = "".join(reasoning_parts)
        app_logger.debug(f"[NVIDIA] Reasoning tokens: {len(reasoning_text)} chars")

    return final_content if final_content else None


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _clean_think_tags(text: str) -> str:
    """Remove <think>...</think> tags from thinking models."""
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
