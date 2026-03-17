# models_api/gemini_models.py — Google Gemini API client
# Used by ModelRouter for Max Power mode.
#
# Task → Model mapping:
#   intent    → gemini-2.0-flash-lite  (fastest, near-zero latency)
#   coding    → gemini-2.0-flash        (best code generation)
#   reasoning → gemini-2.0-flash        (with thinking=LOW for planning)
#
# API key is read from GEMINI_API_KEY env var or api_config.GEMINI_API_KEY.

from __future__ import annotations

import os
import re
from typing import List, Dict, Optional

from logger import app_logger, log_error

# ═══════════════════════════════════════════════════════════════════════
# API KEY
# ═══════════════════════════════════════════════════════════════════════

# Imported lazily below to avoid circular imports at module load time.
def _get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        try:
            from api_config import GEMINI_API_KEY  # type: ignore
            key = GEMINI_API_KEY
        except ImportError:
            pass
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Add it to api_config.py or set the env var."
        )
    return key


# ═══════════════════════════════════════════════════════════════════════
# MODEL IDs
# ═══════════════════════════════════════════════════════════════════════

GEMINI_INTENT_MODEL    = "gemini-3.1-flash-lite-preview"   # fastest — intent classification
GEMINI_CODING_MODEL    = "gemini-3-flash-preview"         # best code gen
GEMINI_REASONING_MODEL = "gemini-3-flash-preview"         # planning (thinking budget)


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _messages_to_gemini(messages: List[Dict[str, str]]) -> tuple[str, str]:
    """
    Convert OpenAI-format messages to (system_instruction, user_prompt).

    Gemini uses a dedicated system_instruction field (string) and a separate
    user prompt.  We extract the system message and concatenate the rest.
    """
    system_parts = []
    user_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
        elif role == "user":
            user_parts.append(content)
        elif role == "assistant":
            user_parts.append(f"[Previous response]\n{content}")
    return "\n\n".join(system_parts), "\n\n".join(user_parts)


def _clean_think_tags(text: str) -> str:
    """Strip <think>…</think> blocks from thinking models."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ═══════════════════════════════════════════════════════════════════════
# GEMINI CALLERS
# ═══════════════════════════════════════════════════════════════════════

def _gemini_intent(messages: List[Dict[str, str]], temperature: float = 0.1) -> Optional[str]:
    """Intent classification — uses flash-lite for near-zero latency."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=_get_api_key())
        system_instr, user_prompt = _messages_to_gemini(messages)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=512,
            system_instruction=system_instr or None,
        )

        response = client.models.generate_content(
            model=GEMINI_INTENT_MODEL,
            contents=user_prompt,
            config=config,
        )
        text = response.text
        if text and text.strip():
            return _clean_think_tags(text.strip())
        return None
    except Exception as e:
        log_error(e, context="gemini_intent")
        return None


def _gemini_coding(messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 8192) -> Optional[str]:
    """Code generation — uses gemini-2.0-flash for best logic + library knowledge."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=_get_api_key())
        system_instr, user_prompt = _messages_to_gemini(messages)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instr or None,
        )

        response = client.models.generate_content(
            model=GEMINI_CODING_MODEL,
            contents=user_prompt,
            config=config,
        )
        text = response.text
        if text and text.strip():
            return _clean_think_tags(text.strip())
        return None
    except Exception as e:
        log_error(e, context="gemini_coding")
        return None


def _gemini_reasoning(messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 8192) -> Optional[str]:
    """Reasoning / planning — uses gemini-2.0-flash with thinking enabled for deeper planning."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=_get_api_key())
        system_instr, user_prompt = _messages_to_gemini(messages)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instr or None,
            thinking_config=types.ThinkingConfig(
                thinking_budget=1024,   # lightweight thinking pass for planning
            ),
        )

        response = client.models.generate_content(
            model=GEMINI_REASONING_MODEL,
            contents=user_prompt,
            config=config,
        )

        # Collect only non-thought parts as the final answer
        final_parts = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, "thought") and part.thought:
                continue   # skip internal reasoning
            if part.text:
                final_parts.append(part.text)

        result = "\n".join(final_parts).strip()
        if result:
            return _clean_think_tags(result)
        # Fallback: use .text if parts approach gave nothing
        if response.text and response.text.strip():
            return _clean_think_tags(response.text.strip())
        return None
    except Exception as e:
        log_error(e, context="gemini_reasoning")
        return None


# ═══════════════════════════════════════════════════════════════════════
# UNIFIED ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

def gemini_call(
    task: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 8192,
) -> Optional[str]:
    """Route call to the appropriate Gemini model based on task type.

    Args:
        task:        "intent", "coding", or "reasoning"
        messages:    OpenAI-format message list (system + user)
        temperature: Sampling temperature
        max_tokens:  Max output tokens

    Returns:
        Response text, or None if the call failed.
    """
    app_logger.info(f"[GEMINI] task={task} → model={_task_to_model(task)}")

    if task == "intent":
        return _gemini_intent(messages, temperature=temperature)
    elif task == "coding":
        return _gemini_coding(messages, temperature=temperature, max_tokens=max_tokens)
    elif task == "reasoning":
        return _gemini_reasoning(messages, temperature=temperature, max_tokens=max_tokens)
    else:
        # Default unknown tasks to coding model
        app_logger.warning(f"[GEMINI] Unknown task '{task}', defaulting to coding model")
        return _gemini_coding(messages, temperature=temperature, max_tokens=max_tokens)


def _task_to_model(task: str) -> str:
    return {
        "intent":    GEMINI_INTENT_MODEL,
        "coding":    GEMINI_CODING_MODEL,
        "reasoning": GEMINI_REASONING_MODEL,
    }.get(task, GEMINI_CODING_MODEL)
