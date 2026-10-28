"""
caching/base.py - Base abstractions for Cache-Aside Pattern.

Design Patterns Used:
- Cache-Aside Pattern: Application first inspects cache (exact hash, then semantic vector).
  If found (Cache Hit), returns immediately without invoking LLM.
  If missing (Cache Miss), queries the model and asynchronously saves the entry to cache.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import numpy as np


@dataclass
class CacheEntry:
    prompt: str
    response: str
    model: str
    embedding: np.ndarray
    created_at: float
    hit_count: int = 0


class BaseCache(ABC):
    """Abstract interface for Cache-Aside implementations."""

    @abstractmethod
    def get(self, prompt: str, model: str = "cheap") -> Tuple[Optional[str], str, float]:
        """
        Looks up response in cache.
        Returns:
            (cached_response, hit_type, similarity_score)
            hit_type: "EXACT_MATCH", "SEMANTIC_MATCH", or "CACHE_MISS"
        """
        pass

    @abstractmethod
    def set(self, prompt: str, response: str, model: str = "cheap") -> None:
        """Stores a prompt-response pair in the cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Flushes the cache."""
        pass

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Returns cache telemetry & metrics."""
        pass
