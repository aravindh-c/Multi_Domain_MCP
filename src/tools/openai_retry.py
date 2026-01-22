"""Retry utilities for OpenAI API calls with exponential backoff."""
import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from openai import RateLimitError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
):
    """
    Decorator to retry OpenAI API calls with exponential backoff on rate limit errors.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay between retries
        backoff_factor: Multiplier for exponential backoff
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RateLimitError as e:
                    last_exception = e
                    if attempt < max_retries:
                        error_msg = str(e)
                        if "insufficient_quota" in error_msg.lower():
                            logger.error(
                                "OpenAI quota exceeded (attempt %d/%d). "
                                "Check your billing/plan. Error: %s",
                                attempt + 1,
                                max_retries + 1,
                                error_msg,
                            )
                            # For quota issues, wait longer
                            delay = min(delay * backoff_factor * 2, max_delay * 2)
                        else:
                            logger.warning(
                                "OpenAI rate limit hit (attempt %d/%d). "
                                "Retrying in %.1f seconds...",
                                attempt + 1,
                                max_retries + 1,
                                delay,
                            )
                        time.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        logger.error(
                            "OpenAI API failed after %d attempts: %s",
                            max_retries + 1,
                            error_msg,
                        )
                        raise
                except Exception as e:
                    # For non-rate-limit errors, don't retry
                    logger.error("OpenAI API call failed (non-retryable): %s", e)
                    raise

            # Should never reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper

    return decorator
