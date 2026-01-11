"""Result caching for read-only tool operations."""

import hashlib
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Cache TTL in seconds (default: 5 minutes)
DEFAULT_TTL = 300


class ResultCache:
    """Cache for tool execution results."""

    def __init__(self, default_ttl: int = DEFAULT_TTL, max_size: int = 1000) -> None:
        """Initialize result cache.

        Args:
            default_ttl: Default time-to-live in seconds
            max_size: Maximum number of cached entries
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: dict[str, dict[str, Any]] = {}
        self._access_times: dict[str, float] = {}

    def _make_key(self, tool_name: str, kwargs: dict[str, Any]) -> str:
        """Create cache key from tool name and arguments."""
        # Normalize kwargs by sorting keys and converting to JSON
        normalized = json.dumps(kwargs, sort_keys=True, default=str)
        key_data = f"{tool_name}:{normalized}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def _is_read_only_tool(self, tool_name: str) -> bool:
        """Check if tool is read-only (safe to cache)."""
        read_only_tools = {
            "read_file",
            "web_search",
            "strixdb_search",
            "strixdb_get",
            "strixdb_list",
            "cve_search",
            "get_agent_capabilities",
        }
        return tool_name in read_only_tools

    def get(self, tool_name: str, kwargs: dict[str, Any]) -> Any | None:
        """Get cached result if available and not expired.

        Args:
            tool_name: Name of tool
            kwargs: Tool arguments

        Returns:
            Cached result or None if not found/expired
        """
        if not self._is_read_only_tool(tool_name):
            return None

        key = self._make_key(tool_name, kwargs)
        if key not in self._cache:
            return None

        entry = self._cache[key]
        now = time.time()

        # Check if expired
        if (now - entry["timestamp"]) > entry["ttl"]:
            del self._cache[key]
            if key in self._access_times:
                del self._access_times[key]
            return None

        # Update access time for LRU
        self._access_times[key] = now
        logger.debug(f"Cache hit for {tool_name}")
        return entry["result"]

    def set(
        self, tool_name: str, kwargs: dict[str, Any], result: Any, ttl: int | None = None
    ) -> None:
        """Cache a result.

        Args:
            tool_name: Name of tool
            kwargs: Tool arguments
            result: Result to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if not self._is_read_only_tool(tool_name):
            return

        # Enforce max size (LRU eviction)
        if len(self._cache) >= self.max_size:
            self._evict_lru()

        key = self._make_key(tool_name, kwargs)
        self._cache[key] = {
            "result": result,
            "timestamp": time.time(),
            "ttl": ttl or self.default_ttl,
        }
        self._access_times[key] = time.time()
        logger.debug(f"Cached result for {tool_name}")

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._access_times:
            # Fallback: remove oldest entry by timestamp
            if self._cache:
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k]["timestamp"],
                )
                del self._cache[oldest_key]
            return

        # Remove least recently accessed
        lru_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        del self._cache[lru_key]
        del self._access_times[lru_key]

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._access_times.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        now = time.time()
        valid_entries = sum(
            1
            for entry in self._cache.values()
            if (now - entry["timestamp"]) <= entry["ttl"]
        )

        return {
            "size": len(self._cache),
            "valid_entries": valid_entries,
            "max_size": self.max_size,
            "hit_rate": 0.0,  # Would need to track hits/misses
        }


# Global cache instance
_global_cache: ResultCache | None = None
_cache_lock = None
import threading

_cache_lock = threading.Lock()


def get_cache() -> ResultCache:
    """Get or create global cache instance."""
    global _global_cache
    with _cache_lock:
        if _global_cache is None:
            _global_cache = ResultCache()
        return _global_cache
