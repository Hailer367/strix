"""Circuit breaker pattern for preventing cascade failures."""

import logging
import threading
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker to prevent cascade failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        success_threshold: int = 2,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds before attempting to close circuit
            success_threshold: Successes needed in half-open to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._lock = threading.Lock()

    def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            RuntimeError: If circuit is open
            Original exception: If function fails
        """
        with self._lock:
            # Check if circuit should transition
            if self._state == CircuitState.OPEN:
                if self._last_failure_time and (time.time() - self._last_failure_time) >= self.timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise RuntimeError(
                        f"Circuit breaker is OPEN. Service unavailable. "
                        f"Will retry after {self.timeout}s timeout."
                    )

        # Execute function
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

    def _record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker CLOSED - service recovered")
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def _record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        f"Circuit breaker OPENED after {self._failure_count} failures"
                    )

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
            }

    def reset(self) -> None:
        """Manually reset circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            logger.info("Circuit breaker manually reset")


# Global circuit breakers per server
_circuit_breakers: dict[str, CircuitBreaker] = {}
_breaker_lock = threading.Lock()


def get_circuit_breaker(server_url: str) -> CircuitBreaker:
    """Get or create circuit breaker for a server."""
    with _breaker_lock:
        if server_url not in _circuit_breakers:
            _circuit_breakers[server_url] = CircuitBreaker()
        return _circuit_breakers[server_url]
