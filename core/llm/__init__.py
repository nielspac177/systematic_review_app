"""LLM client module for systematic review application."""

from .base_client import BaseLLMClient, LLMResponse
from .openai_client import OpenAIClient
from .anthropic_client import AnthropicClient
from .cost_tracker import CostTracker, CostEntry, CostEstimate, OperationType, BudgetExceededError
from . import prompts

__all__ = [
    "BaseLLMClient",
    "LLMResponse",
    "OpenAIClient",
    "AnthropicClient",
    "CostTracker",
    "CostEntry",
    "CostEstimate",
    "OperationType",
    "BudgetExceededError",
    "prompts",
]


def get_llm_client(provider: str, api_key: str, model: str = None) -> BaseLLMClient:
    """
    Factory function to get appropriate LLM client.

    Args:
        provider: "openai" or "anthropic"
        api_key: API key for the provider
        model: Optional model name (uses default if not provided)

    Returns:
        Configured LLM client
    """
    if provider.lower() == "openai":
        return OpenAIClient(api_key=api_key, model=model or "gpt-4o")
    elif provider.lower() == "anthropic":
        return AnthropicClient(api_key=api_key, model=model or "claude-3-5-sonnet-20241022")
    else:
        raise ValueError(f"Unknown provider: {provider}. Choose 'openai' or 'anthropic'")
