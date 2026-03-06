# models_api/browser_agent_client.py — HTTP client for browser-agent FastAPI server
# Sends prompts to GPT/Claude via the browser-agent automation gateway.
# Used when Max Power mode is enabled (Pro/Ultra users).

import requests
from typing import Optional, List, Dict
from logger import app_logger, log_error

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

BROWSER_AGENT_URL = "http://localhost:8000"
CHAT_TIMEOUT = 180  # seconds — browser automation can be slow
HEALTH_TIMEOUT = 5


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _messages_to_prompt(messages: List[Dict[str, str]]) -> str:
    """Convert OpenAI-format messages list into a single prompt string."""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            parts.append(f"[SYSTEM INSTRUCTIONS]\n{content}\n")
        elif role == "user":
            parts.append(f"[USER]\n{content}\n")
        elif role == "assistant":
            parts.append(f"[ASSISTANT]\n{content}\n")
    return "\n".join(parts).strip()


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════

def check_agent_health() -> bool:
    """Check if the browser-agent server is running and responsive."""
    try:
        resp = requests.get(f"{BROWSER_AGENT_URL}/health", timeout=HEALTH_TIMEOUT)
        return resp.status_code == 200
    except Exception:
        return False


def browser_agent_call(
    messages: List[Dict[str, str]],
    target: str = "gpt",
    timeout: int = CHAT_TIMEOUT,
) -> Optional[str]:
    """Send a prompt to GPT or Claude via the browser-agent.

    Args:
        messages: OpenAI-format message list
        target:   "gpt" or "claude"
        timeout:  Request timeout in seconds

    Returns:
        Response text, or None if the call failed.
    """
    prompt = _messages_to_prompt(messages)
    if not prompt:
        app_logger.warning("[BROWSER-AGENT] Empty prompt — skipping")
        return None

    app_logger.info(f"[BROWSER-AGENT] Sending to {target} ({len(prompt)} chars)")

    try:
        resp = requests.post(
            f"{BROWSER_AGENT_URL}/chat",
            json={"prompt": prompt, "model": target},
            timeout=timeout,
        )

        if resp.status_code != 200:
            detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            app_logger.error(f"[BROWSER-AGENT] {target} returned {resp.status_code}: {detail}")
            return None

        data = resp.json()
        response_text = data.get("response", "")
        duration = data.get("duration_ms", 0)

        if not response_text or not response_text.strip():
            app_logger.warning(f"[BROWSER-AGENT] {target} returned empty response")
            return None

        app_logger.info(f"[BROWSER-AGENT] {target} responded ({duration:.0f}ms, {len(response_text)} chars)")
        return response_text.strip()

    except requests.ConnectionError:
        app_logger.warning(
            f"[BROWSER-AGENT] Cannot connect to {BROWSER_AGENT_URL} — "
            f"is the browser-agent server running?"
        )
        return None
    except requests.Timeout:
        app_logger.warning(f"[BROWSER-AGENT] {target} request timed out after {timeout}s")
        return None
    except Exception as e:
        log_error(e, context=f"browser_agent_call(target={target})")
        return None


def init_session(target: str = "gpt") -> Optional[str]:
    """Trigger interactive login for a target (opens headed browser).

    Call this once to log into GPT/Claude. The session will be saved
    and reused automatically for all future requests.

    Returns:
        Storage state path on success, or None on failure.
    """
    try:
        app_logger.info(f"[BROWSER-AGENT] Initiating login for {target}...")
        resp = requests.post(
            f"{BROWSER_AGENT_URL}/session/init",
            params={"target": target},
            timeout=300,  # 5 min — user needs time to log in
        )
        if resp.status_code == 200:
            data = resp.json()
            app_logger.info(f"[BROWSER-AGENT] Login saved: {data.get('storage_state_path')}")
            return data.get("storage_state_path")
        else:
            app_logger.error(f"[BROWSER-AGENT] Login failed: {resp.text}")
            return None
    except Exception as e:
        log_error(e, context=f"init_session(target={target})")
        return None
