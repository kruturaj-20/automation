"""
LLM Provider Factory / Router.
"""

from __future__ import annotations

from src.core.config import LLMConfig
from .base import LLMProvider
from .gemini_provider import GeminiProvider


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    """Factory function for external LLM providers."""
    provider_name = config.default_provider.lower()

    if provider_name == "gemini":
        return GeminiProvider(
            api_key=config.api_key,
            model=config.model,
            temperature=config.temperature,
        )
    # Future providers: "claude", "openai"
    return GeminiProvider(api_key=config.api_key)
