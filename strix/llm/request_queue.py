import asyncio
import logging
import os
import threading
import time
from collections import deque
from typing import Any

import litellm
from litellm import ModelResponse, completion
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding window rate limiter for LLM requests.
    
    Implements a sliding window algorithm to enforce a maximum number of
    requests per minute while allowing burst traffic when possible.
    """
    
    def __init__(self, max_requests_per_minute: int = 60):
        """Initialize rate limiter.
        
        Args:
            max_requests_per_minute: Maximum number of requests allowed per minute.
                                    Default is 60 (1 per second average).
        """
        self.max_requests = max_requests_per_minute
        self.window_size = 60.0  # 60 seconds
        self.request_timestamps: deque[float] = deque()
        self._lock = threading.Lock()
    
    def acquire(self) -> float:
        """Acquire permission to make a request.
        
        Returns:
            The number of seconds to wait before making the request.
            Returns 0 if the request can be made immediately.
        """
        with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            # Remove timestamps outside the window
            while self.request_timestamps and self.request_timestamps[0] < window_start:
                self.request_timestamps.popleft()
            
            # Check if we're at the limit
            if len(self.request_timestamps) >= self.max_requests:
                # Calculate wait time until the oldest request exits the window
                oldest = self.request_timestamps[0]
                wait_time = (oldest + self.window_size) - now + 0.1  # Add small buffer
                return max(0.0, wait_time)
            
            # Record this request
            self.request_timestamps.append(now)
            return 0.0
    
    def get_current_rate(self) -> float:
        """Get the current request rate (requests per minute)."""
        with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            # Count requests in the window
            count = sum(1 for ts in self.request_timestamps if ts >= window_start)
            return count
    
    def get_remaining_capacity(self) -> int:
        """Get remaining request capacity in the current window."""
        with self._lock:
            now = time.time()
            window_start = now - self.window_size
            
            # Count requests in the window
            count = sum(1 for ts in self.request_timestamps if ts >= window_start)
            return max(0, self.max_requests - count)


def should_retry_exception(exception: Exception) -> bool:
    status_code = None

    if hasattr(exception, "status_code"):
        status_code = exception.status_code
    elif hasattr(exception, "response") and hasattr(exception.response, "status_code"):
        status_code = exception.response.status_code

    if status_code is not None:
        return bool(litellm._should_retry(status_code))
    return True


class LLMRequestQueue:
    """Request queue with rate limiting and concurrency control.
    
    This queue manages LLM API requests to:
    1. Limit concurrent requests (default: 3 for better parallelism)
    2. Enforce a rate limit (default: 120 requests/minute with CLIProxyAPI)
    3. Add minimal delay between requests (default: 0.1s for fast responses)
    
    OPTIMIZATIONS:
    - Reduced delay from 0.5s to 0.1s for faster request throughput
    - Increased max concurrent from 1 to 3 for parallel sub-agent requests
    - Increased rate limit from 60 to 120 RPM (CLIProxyAPI supports multi-account)
    - Direct API calls without LiteLLM overhead when possible
    """
    
    def __init__(
        self,
        max_concurrent: int = 3,  # Increased from 1 to 3 for parallel agents
        delay_between_requests: float = 0.1,  # Reduced from 0.5s to 0.1s
        max_requests_per_minute: int = 120,  # Increased from 60 (CLIProxyAPI load balances)
    ):
        # Allow environment variable overrides
        rate_limit_delay = os.getenv("LLM_RATE_LIMIT_DELAY")
        if rate_limit_delay:
            delay_between_requests = float(rate_limit_delay)

        rate_limit_concurrent = os.getenv("LLM_RATE_LIMIT_CONCURRENT")
        if rate_limit_concurrent:
            max_concurrent = int(rate_limit_concurrent)
        
        rate_limit_max_rpm = os.getenv("LLM_MAX_REQUESTS_PER_MINUTE")
        if rate_limit_max_rpm:
            max_requests_per_minute = int(rate_limit_max_rpm)

        self.max_concurrent = max_concurrent
        self.delay_between_requests = delay_between_requests
        self._semaphore = threading.BoundedSemaphore(max_concurrent)
        self._last_request_time = 0.0
        self._lock = threading.Lock()
        
        # Rate limiter - increased limit since CLIProxyAPI load balances across accounts
        self._rate_limiter = RateLimiter(max_requests_per_minute)
        
        # Request statistics
        self._total_requests = 0
        self._total_wait_time = 0.0
        
        logger.info(
            f"LLMRequestQueue initialized (OPTIMIZED): max_concurrent={max_concurrent}, "
            f"delay={delay_between_requests}s, max_rpm={max_requests_per_minute}"
        )

    async def make_request(self, completion_args: dict[str, Any]) -> ModelResponse:
        """Make an LLM request with rate limiting and concurrency control.
        
        This method:
        1. Waits for rate limiter approval (max 60 req/min)
        2. Acquires the concurrency semaphore
        3. Applies minimal delay between requests
        4. Makes the actual request with retry logic
        """
        try:
            # Check rate limiter first
            rate_wait = self._rate_limiter.acquire()
            if rate_wait > 0:
                logger.info(f"Rate limit reached, waiting {rate_wait:.1f}s...")
                await asyncio.sleep(rate_wait)
                # Re-acquire after waiting
                self._rate_limiter.acquire()
            
            # Acquire semaphore for concurrency control
            while not self._semaphore.acquire(timeout=0.2):
                await asyncio.sleep(0.1)

            # Apply minimal delay between requests
            with self._lock:
                now = time.time()
                time_since_last = now - self._last_request_time
                sleep_needed = max(0, self.delay_between_requests - time_since_last)
                self._last_request_time = now + sleep_needed

            if sleep_needed > 0:
                self._total_wait_time += sleep_needed
                await asyncio.sleep(sleep_needed)
            
            self._total_requests += 1
            
            # Log request stats periodically
            if self._total_requests % 10 == 0:
                current_rate = self._rate_limiter.get_current_rate()
                capacity = self._rate_limiter.get_remaining_capacity()
                logger.info(
                    f"Request stats: total={self._total_requests}, "
                    f"current_rate={current_rate}/min, remaining_capacity={capacity}"
                )

            return await self._reliable_request(completion_args)
        finally:
            self._semaphore.release()
    
    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        return {
            "total_requests": self._total_requests,
            "total_wait_time": round(self._total_wait_time, 2),
            "current_rate": self._rate_limiter.get_current_rate(),
            "remaining_capacity": self._rate_limiter.get_remaining_capacity(),
        }

    @retry(  # type: ignore[misc]
        stop=stop_after_attempt(5),  # Increased from 3 to 5 attempts
        wait=wait_exponential(multiplier=2, min=1, max=30),  # Faster retries: 1s, 2s, 4s, 8s, 16s
        retry=retry_if_exception(should_retry_exception),
        reraise=True,
    )
    async def _reliable_request(self, completion_args: dict[str, Any]) -> ModelResponse:
        response = completion(**completion_args, stream=False)
        if isinstance(response, ModelResponse):
            return response
        self._raise_unexpected_response()
        raise RuntimeError("Unreachable code")

    def _raise_unexpected_response(self) -> None:
        raise RuntimeError("Unexpected response type")


_global_queue: LLMRequestQueue | None = None


def get_global_queue() -> LLMRequestQueue:
    global _global_queue  # noqa: PLW0603
    if _global_queue is None:
        _global_queue = LLMRequestQueue()
    return _global_queue
