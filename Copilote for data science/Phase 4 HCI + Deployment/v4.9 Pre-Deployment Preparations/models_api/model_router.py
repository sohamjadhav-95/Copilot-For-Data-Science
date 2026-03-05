# models_api/model_router.py — Simplified task-based model routing
# Routes AI calls to the correct provider/model based on task type.
import time
from typing import Optional

from core.model_plan_router import (
    get_pro_model, get_pro_provider,
    get_quickrun_model, get_quickrun_provider,
)
from models_api.groq_models import groq_model
from models_api.openrouter_models import openrouter_model
from models_api.nvidia_models import nvidia_model
from logger import app_logger, log_error


# ═══════════════════════════════════════════════════════════════════════
# PROVIDER DISPATCH MAP
# ═══════════════════════════════════════════════════════════════════════

_PROVIDER_FUNCTIONS = {
    "groq": groq_model,
    "openrouter": openrouter_model,
    "nvidia": nvidia_model,
}


# ═══════════════════════════════════════════════════════════════════════
# MODEL ROUTER
# ═══════════════════════════════════════════════════════════════════════

class ModelRouter:
    """Route AI calls based on task type.

    Task types:
        reasoning — DAG planning, final reports, re-planning
        coding    — Code generation, step execution
        intent    — Intent classification, summaries

    Usage:
        router = ModelRouter()
        result = router.call(task="coding", messages=[...])
    """

    def call(
        self,
        task: str,
        messages: list,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        retries: int = 2,
    ) -> Optional[str]:
        """Call a Pro/Ultra model for the given task with provider fallback.

        Args:
            task:        "reasoning", "coding", or "intent"
            messages:    OpenAI-format message list
            temperature: Sampling temperature
            max_tokens:  Max output tokens
            retries:     Retry attempts

        Returns:
            Cleaned response text, or None if all attempts failed.
        """
        model_name = get_pro_model(task)
        provider = get_pro_provider()

        app_logger.info(f"[ROUTER] task={task} → {provider}/{model_name}")

        call_fn = _PROVIDER_FUNCTIONS.get(provider)
        if call_fn:
            result = call_fn(
                model_name=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                retries=retries,
            )
            if result:
                return result
            app_logger.warning(f"[ROUTER] {provider}/{model_name} failed")

        # Fallback: try openrouter with the same model
        if provider != "openrouter":
            fallback_fn = _PROVIDER_FUNCTIONS.get("openrouter")
            if fallback_fn:
                app_logger.info(f"[ROUTER] Falling back to openrouter/{model_name}")
                result = fallback_fn(
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
        max_tokens: int = 2048,
        retries: int = 2,
    ) -> Optional[str]:
        """Convenience: build messages from system + user and call."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        return self.call(task, messages, temperature, max_tokens, retries)


# ═══════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE  (used by Pro engines)
# ═══════════════════════════════════════════════════════════════════════

router = ModelRouter()
