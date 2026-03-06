# models_api/model_router.py — Dual-mode AI routing
# Default: Groq gpt-oss-120b for all tasks
# Max Power: browser-agent → GPT (reasoning/intent) + Claude (coding)

from typing import Optional

from core.model_plan_router import get_max_power_target, get_default_model
from models_api.groq_models import groq_model
from models_api.browser_agent_client import browser_agent_call
from logger import app_logger, log_error


# ═══════════════════════════════════════════════════════════════════════
# MAX MODE STATE — toggled per-request by the engine or app.py
# ═══════════════════════════════════════════════════════════════════════

_max_mode_enabled = False


def set_max_mode(enabled: bool) -> None:
    """Enable/disable Max Power mode (browser-agent routing)."""
    global _max_mode_enabled
    _max_mode_enabled = bool(enabled)


def get_max_mode() -> bool:
    """Check if Max Power mode is currently active."""
    return _max_mode_enabled


# ═══════════════════════════════════════════════════════════════════════
# MODEL ROUTER
# ═══════════════════════════════════════════════════════════════════════

class ModelRouter:
    """Route AI calls based on task type and max-mode state.

    Default mode:
        All tasks → Groq gpt-oss-120b

    Max Power mode (toggle ON):
        reasoning → GPT (via browser-agent)
        coding    → Claude (via browser-agent)
        intent    → GPT (via browser-agent)
        Fallback  → Groq if browser-agent fails

    Usage:
        router = ModelRouter()
        result = router.call(task="coding", messages=[...])
    """

    def call(
        self,
        task: str,
        messages: list,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        retries: int = 2,
    ) -> Optional[str]:
        """Call the appropriate model for the given task.

        Args:
            task:        "reasoning", "coding", or "intent"
            messages:    OpenAI-format message list
            temperature: Sampling temperature (used by Groq, not browser-agent)
            max_tokens:  Max output tokens (used by Groq, not browser-agent)
            retries:     Retry attempts (used by Groq, not browser-agent)

        Returns:
            Cleaned response text, or None if all attempts failed.
        """
        # ── Max Power mode: route through browser-agent ──
        if _max_mode_enabled:
            target = get_max_power_target(task)
            app_logger.info(f"[ROUTER] Max Power ON → task={task} → browser-agent/{target}")

            result = browser_agent_call(messages=messages, target=target)
            if result:
                return result

            app_logger.warning(
                f"[ROUTER] browser-agent/{target} failed for task={task}, "
                f"falling back to Groq"
            )

        # ── Default: use Groq for everything ──
        model_name = get_default_model()
        app_logger.info(f"[ROUTER] task={task} → groq/{model_name}")

        result = groq_model(
            model_name=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
        )

        if result:
            return result

        log_error(
            RuntimeError(f"All providers exhausted for task '{task}'"),
            context=f"ModelRouter.call(task={task})",
        )
        return None

    def call_with_system(
        self,
        task: str,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        retries: int = 2,
    ) -> Optional[str]:
        """Convenience: build messages from system + user and call."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ]
        return self.call(task, messages, temperature, max_tokens, retries)


# ═══════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE  (used by Pro engines)
# ═══════════════════════════════════════════════════════════════════════

router = ModelRouter()
