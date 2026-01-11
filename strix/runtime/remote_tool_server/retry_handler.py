"""Retry logic with exponential backoff for HTTP/gRPC operations.

This module provides gRPC-agnostic retry functionality that works with
both HTTP and gRPC transports.
"""

import logging
import random
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Retryable HTTP status codes
RETRYABLE_HTTP_STATUS_CODES = {
    408,  # Request Timeout
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}

# Retryable exception patterns
RETRYABLE_ERROR_PATTERNS = [
    "timeout",
    "connection reset",
    "connection refused",
    "connection closed",
    "unavailable",
    "service unavailable",
    "temporarily unavailable",
    "resource exhausted",
    "deadline exceeded",
]


def should_retry_exception(error: Exception) -> bool:
    """Check if an exception should be retried.
    
    Works with both HTTP errors and general exceptions.
    """
    error_str = str(error).lower()
    
    # Check for retryable patterns in error message
    for pattern in RETRYABLE_ERROR_PATTERNS:
        if pattern in error_str:
            return True
    
    # Check for HTTP status code errors
    if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
        return error.response.status_code in RETRYABLE_HTTP_STATUS_CODES
    
    return False


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
    retryable_check: Callable[[Exception], bool] | None = None,
) -> T:
    """Execute function with retry logic and exponential backoff.

    Args:
        func: Function to execute
        max_attempts: Maximum number of attempts
        base_delay: Base delay for exponential backoff
        max_delay: Maximum delay
        retryable_check: Custom function to check if error is retryable

    Returns:
        Function result

    Raises:
        Last exception if all retries fail
    """
    if retryable_check is None:
        retryable_check = should_retry_exception

    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            last_exception = e
            
            # Check if we should retry
            is_retryable = False
            try:
                is_retryable = retryable_check(e)
            except Exception:
                pass  # If check fails, treat as non-retryable
            
            if is_retryable and attempt < max_attempts - 1:
                delay = exponential_backoff(attempt, base_delay, max_delay)
                logger.warning(
                    f"Retryable error: {type(e).__name__}: {str(e)[:100]}. "
                    f"Retrying in {delay:.2f}s (attempt {attempt + 1}/{max_attempts})"
                )
                time.sleep(delay)
            else:
                raise

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry loop exit")


# Backward compatibility: provide gRPC-specific functions only if grpc is installed
try:
    import grpc
    
    # Retryable gRPC error codes
    RETRYABLE_GRPC_CODES = {
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.DEADLINE_EXCEEDED,
        grpc.StatusCode.RESOURCE_EXHAUSTED,
        grpc.StatusCode.ABORTED,
        grpc.StatusCode.INTERNAL,
    }
    
    def should_retry_grpc(error: grpc.RpcError) -> bool:
        """Check if a gRPC error should be retried."""
        return error.code() in RETRYABLE_GRPC_CODES
    
except ImportError:
    # gRPC not installed - provide stub
    RETRYABLE_GRPC_CODES = set()
    
    def should_retry_grpc(error: Any) -> bool:
        """Stub for when gRPC is not installed."""
        return False
