# models_api/model_router.py — Dual-mode AI routing
# Default: Groq gpt-oss-120b for all tasks
# Max Power: Google Gemini API (intent → flash-lite, coding → flash, reasoning → flash+thinking)

from typing import Optional

from core.model_plan_router import get_default_model
from models_api.groq_models import groq_model
from models_api.gemini_models import gemini_call
from logger import app_logger, log_error


# ═══════════════════════════════════════════════════════════════════════
# MAX MODE STATE — toggled per-request by the engine or app.py
# ═══════════════════════════════════════════════════════════════════════

_max_mode_enabled = False


def set_max_mode(enabled: bool) -> None:
    """Enable/disable Max Power mode (Gemini routing)."""
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
        intent    → gemini-2.0-flash-lite  (fastest, near-zero latency)
        coding    → gemini-2.0-flash        (best code gen)
        reasoning → gemini-2.0-flash        (with thinking budget for planning)
        Fallback  → Groq if Gemini fails

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
            temperature: Sampling temperature
            max_tokens:  Max output tokens
            retries:     Retry attempts (Groq fallback)

        Returns:
            Cleaned response text, or None if all attempts failed.
        """
        # ── Max Power mode: route through Gemini API ──
        if _max_mode_enabled:
            app_logger.info(f"[ROUTER] Max Power ON → task={task} → Gemini")
            result = gemini_call(
                task=task,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if result:
                return result
            app_logger.warning(
                f"[ROUTER] Gemini failed for task={task}, falling back to Groq"
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
