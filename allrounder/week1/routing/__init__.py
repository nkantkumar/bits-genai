"""
routing package - Intelligent Model Routing using the Strategy Pattern.
"""

from .base import CHEAP, SMART, RoutingDecision, RoutingStrategy
from .strategies import CostCascadingStrategy, JevRoutingStrategy, LLMJudgeStrategy, RuleBasedStrategy
from .router import SmartRouter, smart_router

__all__ = [
    "CHEAP",
    "SMART",
    "RoutingDecision",
    "RoutingStrategy",
    "RuleBasedStrategy",
    "LLMJudgeStrategy",
    "CostCascadingStrategy",
    "JevRoutingStrategy",
    "SmartRouter",
    "smart_router",
]
