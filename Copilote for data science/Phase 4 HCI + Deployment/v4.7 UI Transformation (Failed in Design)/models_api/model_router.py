# models_api/model_router.py — Centralized model routing with tier-based selection
# All AI calls in the system should go through ModelRouter.call()
import time
from typing import Optional

from core.config import MODEL_TIERS, PROVIDER_PRIORITY, PROVIDER_CONFIGS
from models_api.groq_models import groq_model
from models_api.openrouter_models import openrouter_model
from logger import app_logger, log_error


# ═══════════════════════════════════════════════════════════════════════
# PROVIDER DISPATCH MAP
# ═══════════════════════════════════════════════════════════════════════

_PROVIDER_FUNCTIONS = {
    "groq": groq_model,
    "openrouter": openrouter_model,
}


# ═══════════════════════════════════════════════════════════════════════
# MODEL ROUTER
# ═══════════════════════════════════════════════════════════════════════

class ModelRouter:
    """Route AI calls to the appropriate provider and model based on tier.

    Tiers:
        heavy  — DAG planning, final reports, re-planning  (qwen3-235b-thinking)
        mid    — Code generation, step execution             (gpt-oss-120b)
        light  — Intent classification, complexity detection  (gpt-oss-20b)

    Usage:
        router = ModelRouter()
        result = router.call("mid", messages=[...], temperature=0.2)
    """

    def call(
        self,
        tier: str,
        messages: list,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        retries: int = 2,
    ) -> Optional[str]:
        """Call a model at the specified tier with automatic provider fallback.

        Args:
            tier:        "heavy", "mid", or "light"
            messages:    OpenAI-format message list
            temperature: Sampling temperature
            max_tokens:  Max output tokens
            retries:     Retry attempts per provider

        Returns:
            Cleaned response text, or None if all providers failed.
        """
        if tier not in MODEL_TIERS:
            raise ValueError(f"Unknown model tier '{tier}'. Available: {list(MODEL_TIERS.keys())}")

        tier_config = MODEL_TIERS[tier]
        providers = PROVIDER_PRIORITY.get(tier, ["groq", "openrouter"])

        for provider in providers:
            model_name = tier_config.get(provider)
            if not model_name:
                app_logger.debug(f"[ROUTER] Tier '{tier}' not available on {provider}, skipping")
                continue

            call_fn = _PROVIDER_FUNCTIONS.get(provider)
            if not call_fn:
                app_logger.warning(f"[ROUTER] No dispatch function for provider '{provider}'")
                continue

            app_logger.info(f"[ROUTER] {tier} → {provider}/{model_name}")
            result = call_fn(
                model_name=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                retries=retries,
            )
            if result:
                return result

            app_logger.warning(f"[ROUTER] {provider}/{model_name} failed, trying next provider...")

        log_error(
            RuntimeError(f"All providers exhausted for tier '{tier}'"),
            context=f"ModelRouter.call(tier={tier})",
        )
        return None

    def call_with_system(
        self,
        tier: str,
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
        return self.call(tier, messages, temperature, max_tokens, retries)

    def get_model_info(self, tier: str) -> dict:
        """Return the model name and provider that would be used for a tier."""
        if tier not in MODEL_TIERS:
            return {"tier": tier, "error": "unknown tier"}
        tier_config = MODEL_TIERS[tier]
        providers = PROVIDER_PRIORITY.get(tier, [])
        for provider in providers:
            model_name = tier_config.get(provider)
            if model_name:
                return {"tier": tier, "provider": provider, "model": model_name}
        return {"tier": tier, "error": "no available provider"}


# ═══════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════

router = ModelRouter()
