"""Retry logic with exponential backoff for gRPC operations."""

import logging
import random
import time
from typing import Any, Callable, TypeVar

import grpc

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Retryable gRPC error codes
RETRYABLE_ERRORS = {
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
    grpc.StatusCode.RESOURCE_EXHAUSTED,
    grpc.StatusCode.ABORTED,
    grpc.StatusCode.INTERNAL,  # Sometimes transient
}


def should_retry(error: grpc.RpcError) -> bool:
    """Check if an error should be retried."""
    return error.code() in RETRYABLE_ERRORS


def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate exponential backoff delay with jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds
    """
    delay = min(base_delay * (2 ** attempt), max_delay)
    # Add jitter (random 0-25% of delay)
    jitter = delay * 0.25 * random.random()
    return delay + jitter


def retry_with_backoff(
    func: Callable[[], T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_errors: set[grpc.StatusCode] | None = None,
) -> T:
    """Execute function with retry logic and exponential backoff.

    Args:
        func: Function to execute
        max_attempts: Maximum number of attempts
        base_delay: Base delay for exponential backoff
        max_delay: Maximum delay
        retryable_errors: Set of retryable error codes (defaults to RETRYABLE_ERRORS)

    Returns:
        Function result

    Raises:
        Last exception if all retries fail
    """
    if retryable_errors is None:
        retryable_errors = RETRYABLE_ERRORS

    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return func()
        except grpc.RpcError as e:
            last_exception = e
            if e.code() in retryable_errors and attempt < max_attempts - 1:
                delay = exponential_backoff(attempt, base_delay, max_delay)
                logger.warning(
                    f"Retryable error {e.code()}: {e.details()}. "
                    f"Retrying in {delay:.2f}s (attempt {attempt + 1}/{max_attempts})"
                )
                time.sleep(delay)
            else:
                raise
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                delay = exponential_backoff(attempt, base_delay, max_delay)
                logger.warning(
                    f"Error: {e}. Retrying in {delay:.2f}s (attempt {attempt + 1}/{max_attempts})"
                )
                time.sleep(delay)
            else:
                raise

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry loop exit")
