"""
orchestration/state.py - Execution States, Risk Levels, and Command Models for FSM & HITL.

Design Patterns Used:
- Finite State Machine (FSM) / State Pattern: Explicit lifecycle states of a request.
- Command Pattern: PendingAction encapsulates a paused request with its context and executable payload.
"""

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionState(str, Enum):
    RECEIVED = "RECEIVED"
    GUARDING_INPUT = "GUARDING_INPUT"
    CHECKING_CACHE = "CHECKING_CACHE"
    ROUTING_INTENT = "ROUTING_INTENT"
    EXECUTING_RAG = "EXECUTING_RAG"
    EXECUTING_TOOL = "EXECUTING_TOOL"
    AWAITING_HITL_APPROVAL = "AWAITING_HITL_APPROVAL"
    GUARDING_OUTPUT = "GUARDING_OUTPUT"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class ExecutionStrategy(str, Enum):
    DIRECT_LLM = "DIRECT_LLM"
    RAG_AUTOMATED = "RAG_AUTOMATED"
    RAG_HUMAN_IN_THE_LOOP = "RAG_HUMAN_IN_THE_LOOP"
    TOOL_CALL = "TOOL_CALL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class PendingAction:
    """Command Object for paused Human-in-the-Loop actions."""
    action_id: str
    user_prompt: str
    model: str
    strategy: ExecutionStrategy
    risk_level: RiskLevel
    reason: str
    proposed_queries: List[str]
    target_docs: List[str]
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending, approved, modified, rejected
    decision: Optional[str] = None
    modified_query: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["strategy"] = self.strategy.value
        d["risk_level"] = self.risk_level.value
        return d
