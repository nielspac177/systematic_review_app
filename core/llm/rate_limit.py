"""Rate limiting and retry logic for LLM API calls.

This module provides:
- Token-per-minute (TPM) throttling with a rolling window
- Exponential backoff with jitter for rate limit errors
- Graceful handling of transient API errors

Environment Variables:
- OPENAI_TPM_LIMIT: Tokens per minute limit (default: 30000)
- OPENAI_MAX_RETRIES: Maximum retry attempts (default: 6)
- OPENAI_BACKOFF_BASE_MS: Base backoff in milliseconds (default: 250)
- OPENAI_BACKOFF_CAP_MS: Maximum backoff in milliseconds (default: 8000)
"""

import os
import re
import time
import random
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Callable, TypeVar, Any
from functools import wraps

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add handler if none exists
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    # TPM throttling - default to 90,000 (Tier 1 limit for GPT-4o)
    # Users can override via env var if they hit limits
    tpm_limit: int = field(default_factory=lambda: int(os.getenv("OPENAI_TPM_LIMIT", "90000")))

    # Retry settings
    max_retries: int = field(default_factory=lambda: int(os.getenv("OPENAI_MAX_RETRIES", "6")))
    backoff_base_ms: int = field(default_factory=lambda: int(os.getenv("OPENAI_BACKOFF_BASE_MS", "250")))
    backoff_cap_ms: int = field(default_factory=lambda: int(os.getenv("OPENAI_BACKOFF_CAP_MS", "8000")))

    # Jitter range (0.0 to 1.0 multiplier)
    jitter_factor: float = 0.5

    # Window duration for rolling token count (seconds)
    window_seconds: int = 60


# Global config instance
_config: Optional[RateLimitConfig] = None


def get_config() -> RateLimitConfig:
    """Get or create the global rate limit config."""
    global _config
    if _config is None:
        _config = RateLimitConfig()
    return _config


def set_tpm_limit(limit: int) -> None:
    """Set the TPM limit at runtime."""
    get_config().tpm_limit = limit
    logger.info(f"TPM limit set to {limit}")


# =============================================================================
# TOKEN ESTIMATION
# =============================================================================

def estimate_tokens_heuristic(text: str) -> int:
    """
    Estimate token count using a simple heuristic.

    Approximation: ~4 characters per token for English text.
    This is a fallback when tiktoken is not available.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    # Rough heuristic: 4 chars per token, with some overhead
    return max(1, len(text) // 4)


def estimate_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Estimate token count, using tiktoken if available.

    Args:
        text: Text to estimate tokens for
        model: Model name for tokenizer selection

    Returns:
        Estimated token count
    """
    try:
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        logger.debug("tiktoken not available, using heuristic estimation")
        return estimate_tokens_heuristic(text)
    except Exception as e:
        logger.warning(f"Token estimation error: {e}, using heuristic")
        return estimate_tokens_heuristic(text)


def estimate_request_tokens(messages: list[dict], max_tokens: int = 1000, model: str = "gpt-4o") -> int:
    """
    Estimate total tokens for a chat completion request.

    Args:
        messages: List of message dicts
        max_tokens: Maximum output tokens
        model: Model name

    Returns:
        Estimated total tokens (input + potential output)
    """
    # Estimate input tokens
    input_tokens = 0
    for msg in messages:
        content = msg.get("content", "")
        input_tokens += estimate_tokens(content, model)
        # Add overhead for message structure (~4 tokens per message)
        input_tokens += 4

    # Add base overhead
    input_tokens += 3  # Every request has some overhead

    # Total = input + expected output (use max_tokens as upper bound)
    return input_tokens + max_tokens


# =============================================================================
# ROLLING WINDOW TOKEN TRACKER
# =============================================================================

class TokenBucket:
    """
    Rolling window token budget tracker.

    Maintains a sliding window of token usage to enforce TPM limits.
    Thread-safe for concurrent access.
    """

    def __init__(self, tpm_limit: int, window_seconds: int = 60):
        """
        Initialize token bucket.

        Args:
            tpm_limit: Maximum tokens per minute
            window_seconds: Window duration in seconds
        """
        self.tpm_limit = tpm_limit
        self.window_seconds = window_seconds
        self._usage: deque[tuple[float, int]] = deque()  # (timestamp, tokens)
        self._lock = threading.Lock()

    def _cleanup_old_entries(self, now: float) -> None:
        """Remove entries outside the rolling window."""
        cutoff = now - self.window_seconds
        while self._usage and self._usage[0][0] < cutoff:
            self._usage.popleft()

    def get_current_usage(self) -> int:
        """Get current token usage in the rolling window."""
        with self._lock:
            now = time.time()
            self._cleanup_old_entries(now)
            return sum(tokens for _, tokens in self._usage)

    def get_available_tokens(self) -> int:
        """Get available tokens before hitting the limit."""
        return max(0, self.tpm_limit - self.get_current_usage())

    def wait_for_capacity(self, tokens_needed: int) -> float:
        """
        Wait until there's capacity for the requested tokens.

        Args:
            tokens_needed: Number of tokens needed

        Returns:
            Time waited in seconds
        """
        total_wait = 0.0

        while True:
            with self._lock:
                now = time.time()
                self._cleanup_old_entries(now)
                current_usage = sum(tokens for _, tokens in self._usage)
                available = self.tpm_limit - current_usage

                if available >= tokens_needed:
                    return total_wait

                # Calculate wait time
                if not self._usage:
                    # No entries, shouldn't happen but handle it
                    wait_time = 0.1
                else:
                    # Wait until oldest entry expires
                    oldest_time = self._usage[0][0]
                    wait_time = max(0.1, (oldest_time + self.window_seconds) - now + 0.1)

            logger.info(
                f"TPM throttle: need {tokens_needed} tokens, "
                f"available {available}/{self.tpm_limit}, "
                f"waiting {wait_time:.2f}s"
            )
            time.sleep(wait_time)
            total_wait += wait_time

    def record_usage(self, tokens: int) -> None:
        """
        Record token usage.

        Args:
            tokens: Number of tokens used
        """
        with self._lock:
            now = time.time()
            self._cleanup_old_entries(now)
            self._usage.append((now, tokens))
            logger.debug(f"Recorded {tokens} tokens, total in window: {self.get_current_usage()}")


# Global token bucket instance
_token_bucket: Optional[TokenBucket] = None
_bucket_lock = threading.Lock()


def get_token_bucket() -> TokenBucket:
    """Get or create the global token bucket."""
    global _token_bucket
    with _bucket_lock:
        if _token_bucket is None:
            config = get_config()
            _token_bucket = TokenBucket(config.tpm_limit, config.window_seconds)
        return _token_bucket


def reset_token_bucket() -> None:
    """Reset the global token bucket (useful for testing)."""
    global _token_bucket
    with _bucket_lock:
        config = get_config()
        _token_bucket = TokenBucket(config.tpm_limit, config.window_seconds)


# =============================================================================
# RETRY WITH BACKOFF
# =============================================================================

def parse_retry_after(error_message: str) -> Optional[float]:
    """
    Parse retry delay from error message.

    Looks for patterns like:
    - "Please try again in 500ms"
    - "Please try again in 1.5s"
    - "Retry-After: 2"

    Args:
        error_message: Error message string

    Returns:
        Retry delay in seconds, or None if not found
    """
    # Pattern: "try again in Xms" or "try again in Xs"
    match = re.search(r'try again in (\d+(?:\.\d+)?)(ms|s)', error_message, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        unit = match.group(2).lower()
        if unit == 'ms':
            return value / 1000.0
        return value

    # Pattern: "Retry-After: X"
    match = re.search(r'Retry-After:\s*(\d+(?:\.\d+)?)', error_message, re.IGNORECASE)
    if match:
        return float(match.group(1))

    return None


def calculate_backoff(attempt: int, config: Optional[RateLimitConfig] = None) -> float:
    """
    Calculate exponential backoff with jitter.

    Formula: min(cap, base * 2^attempt) * (1 + random * jitter_factor)

    Args:
        attempt: Current attempt number (0-indexed)
        config: Rate limit config

    Returns:
        Backoff duration in seconds
    """
    if config is None:
        config = get_config()

    # Exponential backoff
    backoff_ms = min(
        config.backoff_cap_ms,
        config.backoff_base_ms * (2 ** attempt)
    )

    # Add jitter
    jitter = random.uniform(0, config.jitter_factor)
    backoff_ms *= (1 + jitter)

    return backoff_ms / 1000.0


def is_retryable_error(exception: Exception) -> bool:
    """
    Check if an exception is retryable.

    Args:
        exception: The exception to check

    Returns:
        True if the error is retryable
    """
    # Import OpenAI exceptions dynamically to avoid import errors
    try:
        from openai import RateLimitError, APITimeoutError, APIConnectionError, InternalServerError

        if isinstance(exception, RateLimitError):
            return True
        if isinstance(exception, APITimeoutError):
            return True
        if isinstance(exception, APIConnectionError):
            return True
        if isinstance(exception, InternalServerError):
            return True
    except ImportError:
        pass

    # Check by error code/message for generic handling
    error_str = str(exception).lower()
    if '429' in error_str or 'rate limit' in error_str:
        return True
    if 'timeout' in error_str:
        return True
    if '500' in error_str or '502' in error_str or '503' in error_str:
        return True

    return False


T = TypeVar('T')


def with_retry(
    func: Callable[..., T],
    *args,
    config: Optional[RateLimitConfig] = None,
    **kwargs
) -> T:
    """
    Execute a function with retry logic.

    Args:
        func: Function to execute
        *args: Positional arguments for func
        config: Rate limit config
        **kwargs: Keyword arguments for func

    Returns:
        Result from func

    Raises:
        The last exception if all retries are exhausted
    """
    if config is None:
        config = get_config()

    last_exception: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if not is_retryable_error(e):
                logger.warning(f"Non-retryable error: {e}")
                raise

            if attempt >= config.max_retries:
                logger.error(f"Max retries ({config.max_retries}) exceeded")
                raise

            # Check for server-suggested retry delay
            error_str = str(e)
            server_delay = parse_retry_after(error_str)

            if server_delay is not None:
                delay = server_delay
                logger.info(f"Using server-suggested delay: {delay:.2f}s")
            else:
                delay = calculate_backoff(attempt, config)

            logger.warning(
                f"Retry {attempt + 1}/{config.max_retries}: {type(e).__name__}, "
                f"waiting {delay:.2f}s"
            )
            time.sleep(delay)

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected state in retry logic")


# =============================================================================
# COMBINED THROTTLE + RETRY WRAPPER
# =============================================================================

def throttled_api_call(
    func: Callable[..., T],
    estimated_tokens: int,
    *args,
    config: Optional[RateLimitConfig] = None,
    skip_throttle: bool = False,
    **kwargs
) -> T:
    """
    Execute an API call with TPM throttling and retry logic.

    Args:
        func: The API function to call
        estimated_tokens: Estimated tokens for this request
        *args: Positional arguments for func
        config: Rate limit config
        skip_throttle: If True, skip TPM throttling (still uses retry logic)
        **kwargs: Keyword arguments for func

    Returns:
        Result from func
    """
    if config is None:
        config = get_config()

    bucket = get_token_bucket()

    # Wait for capacity (unless skipped)
    if not skip_throttle:
        wait_time = bucket.wait_for_capacity(estimated_tokens)
        if wait_time > 0:
            logger.info(f"Throttle wait completed: {wait_time:.2f}s")

    # Execute with retry
    result = with_retry(func, *args, config=config, **kwargs)

    # Record usage (actual tokens will be different, but we use estimate for throttling)
    bucket.record_usage(estimated_tokens)

    return result


def direct_api_call(
    func: Callable[..., T],
    *args,
    config: Optional[RateLimitConfig] = None,
    **kwargs
) -> T:
    """
    Execute an API call with retry logic but NO throttling.

    Use this for single/infrequent requests like criteria generation
    where TPM throttling would just add unnecessary delay.

    Args:
        func: The API function to call
        *args: Positional arguments for func
        config: Rate limit config
        **kwargs: Keyword arguments for func

    Returns:
        Result from func
    """
    if config is None:
        config = get_config()

    # Just retry logic, no TPM throttling
    return with_retry(func, *args, config=config, **kwargs)


# =============================================================================
# DECORATOR VERSION
# =============================================================================

def rate_limited(estimate_tokens_func: Optional[Callable[..., int]] = None):
    """
    Decorator for rate-limited API calls.

    Args:
        estimate_tokens_func: Optional function to estimate tokens from args/kwargs

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Estimate tokens
            if estimate_tokens_func:
                estimated = estimate_tokens_func(*args, **kwargs)
            else:
                # Default estimate
                estimated = 1000

            return throttled_api_call(func, estimated, *args, **kwargs)

        return wrapper
    return decorator


# =============================================================================
# CONCURRENCY CONTROL
# =============================================================================

class APICallSemaphore:
    """
    Semaphore for limiting concurrent API calls.

    Prevents parallel calls from Streamlit reruns.
    """

    _instance: Optional['APICallSemaphore'] = None
    _lock = threading.Lock()

    def __new__(cls, max_concurrent: int = 1):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._semaphore = threading.Semaphore(max_concurrent)
                cls._instance._max_concurrent = max_concurrent
            return cls._instance

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire the semaphore."""
        return self._semaphore.acquire(timeout=timeout)

    def release(self) -> None:
        """Release the semaphore."""
        self._semaphore.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


def get_api_semaphore(max_concurrent: int = 1) -> APICallSemaphore:
    """Get the global API call semaphore."""
    return APICallSemaphore(max_concurrent)
