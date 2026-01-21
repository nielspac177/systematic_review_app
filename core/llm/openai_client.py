"""OpenAI LLM client implementation with simple retry on rate limit."""

import json
import time
import logging
import re
from typing import Optional

from openai import OpenAI, RateLimitError, APIError

from .base_client import BaseLLMClient, LLMResponse

# Configure logging
logger = logging.getLogger(__name__)

# Pricing per 1M tokens (as of 2024)
OPENAI_PRICING = {
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


def parse_retry_after(error_message: str) -> float:
    """Parse retry delay from error message."""
    # Pattern: "try again in Xms" or "try again in Xs"
    match = re.search(r'try again in (\d+(?:\.\d+)?)(ms|s)', str(error_message), re.IGNORECASE)
    if match:
        value = float(match.group(1))
        unit = match.group(2).lower()
        if unit == 'ms':
            return value / 1000.0
        return value
    return 5.0  # Default 5 second wait


class OpenAIClient(BaseLLMClient):
    """OpenAI API client - simple and fast with retry on rate limit."""

    SUPPORTED_MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4-turbo-preview",
        "gpt-4",
        "gpt-3.5-turbo",
    ]

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        """Initialize OpenAI client."""
        super().__init__(api_key, model)
        if model not in self.SUPPORTED_MODELS:
            raise ValueError(f"Model {model} not supported. Choose from: {self.SUPPORTED_MODELS}")
        self.client = OpenAI(api_key=api_key)
        self._tokenizer = None

    @property
    def tokenizer(self):
        """Lazy load tokenizer with fallback."""
        if self._tokenizer is None:
            try:
                import tiktoken
                try:
                    self._tokenizer = tiktoken.encoding_for_model(self.model)
                except KeyError:
                    self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                self._tokenizer = None
        return self._tokenizer

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        json_mode: bool = False,
        max_retries: int = 5,
    ) -> LLMResponse:
        """
        Send a chat completion request to OpenAI.

        Automatically retries on rate limit errors with appropriate delays.
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_error = None

        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)

                content = response.choices[0].message.content
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens
                cost = self.estimate_cost(input_tokens, output_tokens)

                return LLMResponse(
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    model=self.model,
                )

            except RateLimitError as e:
                last_error = e
                wait_time = parse_retry_after(str(e))

                if attempt < max_retries:
                    logger.warning(f"Rate limit hit. Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Rate limit: max retries ({max_retries}) exceeded")
                    raise

            except APIError as e:
                last_error = e
                if attempt < max_retries and e.status_code in [500, 502, 503, 529]:
                    wait_time = min(2 ** attempt, 30)  # Exponential backoff, max 30s
                    logger.warning(f"API error {e.status_code}. Waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                else:
                    raise

        if last_error:
            raise last_error

    def chat_safe(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        json_mode: bool = False,
        fallback_content: Optional[str] = None,
    ) -> LLMResponse:
        """
        Send a chat request with graceful error handling.
        Returns fallback response on failure instead of raising.
        """
        try:
            return self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )
        except Exception as e:
            logger.error(f"API call failed: {e}")

            if fallback_content is None:
                if json_mode:
                    fallback_content = json.dumps({
                        "error": "unable_to_screen",
                        "decision": "included",
                        "reason": f"API error: {str(e)[:100]}",
                        "reason_category": "other",
                        "confidence": 0.0,
                    })
                else:
                    fallback_content = f"Error: {str(e)[:200]}"

            return LLMResponse(
                content=fallback_content,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost=0.0,
                model=self.model,
            )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for given token counts."""
        pricing = OPENAI_PRICING.get(self.model, OPENAI_PRICING["gpt-4o"])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        if self.tokenizer is not None:
            return len(self.tokenizer.encode(text))
        else:
            return max(1, len(text) // 4)

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    @property
    def supported_models(self) -> list[str]:
        return self.SUPPORTED_MODELS
