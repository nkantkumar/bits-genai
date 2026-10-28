"""
guardrails/base.py - Base abstractions for Guardrail Interceptor & Chain of Responsibility.

Design Patterns Used:
- Chain of Responsibility Pattern: Sequential inspection filters where each filter
  can inspect, sanitize, enrich, or block the payload before passing it down the chain.
- Interceptor / Filter Pattern: Intercepts inbound user requests and outbound LLM responses.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GuardrailAction(str, Enum):
    ALLOWED = "ALLOWED"
    SANITIZED = "SANITIZED"
    BLOCKED = "BLOCKED"


@dataclass
class GuardrailContext:
    """Carries request/response data through the Chain of Responsibility."""
    original_text: str
    current_text: str
    action: GuardrailAction = GuardrailAction.ALLOWED
    passed: bool = True
    violations: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    blocked_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def block(self, violation: str, reason: str, risk_score: float = 1.0):
        """Halts the chain and flags payload as blocked."""
        self.passed = False
        self.action = GuardrailAction.BLOCKED
        self.violations.append(violation)
        self.blocked_reason = reason
        self.risk_score = max(self.risk_score, risk_score)

    def sanitize(self, new_text: str, violation: Optional[str] = None):
        """Mutates the text in-flight and marks action as SANITIZED."""
        self.current_text = new_text
        if self.action != GuardrailAction.BLOCKED:
            self.action = GuardrailAction.SANITIZED
        if violation and violation not in self.violations:
            self.violations.append(violation)


class BaseGuardrailFilter(ABC):
    """Abstract filter in the Chain of Responsibility."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @abstractmethod
    def process(self, context: GuardrailContext) -> GuardrailContext:
        """Inspects or mutates the context. If blocked, subsequent filters are bypassed."""
        pass


class GuardrailPipeline:
    """Executes a sequential chain of Guardrail filters."""

    def __init__(self, filters: Optional[List[BaseGuardrailFilter]] = None):
        self.filters: List[BaseGuardrailFilter] = filters or []

    def add_filter(self, guard_filter: BaseGuardrailFilter) -> "GuardrailPipeline":
        self.filters.append(guard_filter)
        return self

    def execute(self, text: str, initial_metadata: Optional[Dict[str, Any]] = None) -> GuardrailContext:
        context = GuardrailContext(
            original_text=text,
            current_text=text,
            metadata=initial_metadata or {},
        )
        for flt in self.filters:
            if not flt.enabled:
                continue
            context = flt.process(context)
            if context.action == GuardrailAction.BLOCKED:
                # Chain of Responsibility: Terminate immediately upon blocker
                break
        return context
