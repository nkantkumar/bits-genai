"""
routing/base.py - Base abstractions for Smart Routing using the Strategy Pattern.

Design Patterns Used:
- Strategy Pattern: Encapsulates routing algorithms (Rule-based Heuristic, LLM Judge, Cost Cascading)
  behind a common interface, allowing dynamic algorithm selection at runtime.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

CHEAP = "cheap"
SMART = "smart"


@dataclass
class RoutingDecision:
    selected_model: str  # "cheap" or "smart"
    strategy_name: str
    confidence: float = 1.0
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class RoutingStrategy(ABC):
    """Abstract Strategy interface for routing prompts."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def route(self, prompt: str, client: Optional[Any] = None) -> RoutingDecision:
        """Determines whether to route to 'cheap' or 'smart' model."""
        pass
