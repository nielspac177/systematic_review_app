"""Anthropic Claude LLM client implementation."""

import json
from typing import Optional

import anthropic

from .base_client import BaseLLMClient, LLMResponse


# Pricing per 1M tokens (as of 2024)
ANTHROPIC_PRICING = {
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-opus-latest": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}


class AnthropicClient(BaseLLMClient):
    """Anthropic API client for Claude models."""

    SUPPORTED_MODELS = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-latest",
        "claude-3-opus-20240229",
        "claude-3-opus-latest",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]

    # Average characters per token for Claude (approximation)
    CHARS_PER_TOKEN = 4.0

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize Anthropic client.

        Args:
            api_key: Anthropic API key
            model: Model to use (default: claude-3-5-sonnet-20241022)
        """
        super().__init__(api_key, model)
        if model not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Model {model} not supported. Choose from: {self.SUPPORTED_MODELS}"
            )
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        json_mode: bool = False
    ) -> LLMResponse:
        """
        Send a message request to Anthropic Claude.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            json_mode: If True, request JSON-formatted response

        Returns:
            LLMResponse with content, token counts, and cost
        """
        # Extract system message if present
        system_message = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                chat_messages.append(msg)

        # If json_mode, add instruction to system message
        if json_mode:
            json_instruction = (
                "\n\nYou must respond with valid JSON only. "
                "Do not include any text outside the JSON object."
            )
            if system_message:
                system_message += json_instruction
            else:
                system_message = json_instruction.strip()

        kwargs = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_message:
            kwargs["system"] = system_message

        response = self.client.messages.create(**kwargs)

        content = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens
        cost = self.estimate_cost(input_tokens, output_tokens)

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=cost,
            model=self.model,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for given token counts.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        pricing = ANTHROPIC_PRICING.get(
            self.model, ANTHROPIC_PRICING["claude-3-5-sonnet-20241022"]
        )
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for a text string.

        Note: Claude doesn't have a public tokenizer, so we estimate
        based on character count. This is an approximation.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated number of tokens
        """
        # Use character-based estimation
        return int(len(text) / self.CHARS_PER_TOKEN)

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "Anthropic"

    @property
    def supported_models(self) -> list[str]:
        """Return list of supported models."""
        return self.SUPPORTED_MODELS
