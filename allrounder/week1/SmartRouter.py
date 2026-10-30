"""
SmartRouter.py - Backward Compatibility Shim.
All implementations have been reorganized into the `routing/` package following
the Strategy Design Pattern.
"""

import sys
from pathlib import Path

WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from routing import (
    CHEAP,
    SMART,
    CostCascadingStrategy,
    JevRoutingStrategy,
    LLMJudgeStrategy,
    RoutingDecision,
    RoutingStrategy,
    RuleBasedStrategy,
    SmartRouter,
    smart_router,
)

# Function handles for legacy scripts
classify_by_rules = smart_router.classify_by_rules
classify_by_llm = smart_router.classify_by_llm
ask_with_cascade = smart_router.ask_with_cascade

__all__ = [
    "CHEAP",
    "SMART",
    "CostCascadingStrategy",
    "JevRoutingStrategy",
    "LLMJudgeStrategy",
    "RoutingDecision",
    "RoutingStrategy",
    "RuleBasedStrategy",
    "SmartRouter",
    "smart_router",
    "classify_by_rules",
    "classify_by_llm",
    "ask_with_cascade",
]

if __name__ == "__main__":
    prompts = [
        "What is the capital of France?",
        "Refactor this Python code to be async:\n```python\ndef fetch(): pass\n```",
    ]
    print("=" * 70)
    print(" Testing SmartRouter (Strategy Pattern)")
    print("=" * 70)
    for p in prompts:
        decision = smart_router.route(p)
        print(f"\nPrompt: \"{p[:40]}...\"")
        print(f" -> Model:    {decision.selected_model}")
        print(f" -> Strategy: {decision.strategy_name}")
        print(f" -> Reason:   {decision.reason}")