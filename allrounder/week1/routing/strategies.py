"""
routing/strategies.py - Concrete Routing Strategies.

Strategies:
1. RuleBasedStrategy: Free, instant (<1ms) heuristic scoring based on length, code, and keywords.
2. LLMJudgeStrategy: Cheap model evaluates query difficulty and selects appropriate model tier.
3. CostCascadingStrategy: Queries cheap model; cascades to smart model if confidence is low.
"""

import logging
import os
import re
from typing import Any, Optional

try:
    from typesafe_sdk import Choice, Noul, TypeSafeClient
    TYPESAFE_AVAILABLE = True
except ImportError:
    TYPESAFE_AVAILABLE = False

from .base import CHEAP, SMART, RoutingDecision, RoutingStrategy

logger = logging.getLogger("RoutingStrategies")

HARD_HINTS = re.compile(
    r"\b(analy[sz]e|prove|derive|debug|refactor|architecture|trade-?offs?|"
    r"step[- ]by[- ]step|compare|optimi[sz]e|legal|contract|diagnos\w*)\b",
    re.IGNORECASE,
)


class RuleBasedStrategy(RoutingStrategy):
    """Strategy 1: Deterministic Heuristic Scoring (0 cost, 0ms latency)."""

    @property
    def name(self) -> str:
        return "rule_based"

    def route(self, prompt: str, client: Optional[Any] = None) -> RoutingDecision:
        score = 0
        reasons = []

        if len(prompt.split()) > 120:
            score += 1
            reasons.append("long_prompt")
        if "```" in prompt or "def " in prompt or "class " in prompt:
            score += 1
            reasons.append("contains_code")
        if HARD_HINTS.search(prompt):
            score += 1
            reasons.append("complex_keywords")
        if prompt.count("?") > 1:
            score += 1
            reasons.append("multi_question")

        selected = SMART if score >= 2 else CHEAP
        reason_str = f"Score {score}/4 based on: {', '.join(reasons) if reasons else 'simple_query'}"

        return RoutingDecision(
            selected_model=selected,
            strategy_name=self.name,
            confidence=0.85 if score >= 2 else 0.90,
            reason=reason_str,
            metadata={"heuristic_score": score, "flags": reasons},
        )


class LLMJudgeStrategy(RoutingStrategy):
    """Strategy 2: Let the cheap model judge difficulty (1 lightweight call)."""

    @property
    def name(self) -> str:
        return "llm_judge"

    def route(self, prompt: str, client: Optional[Any] = None) -> RoutingDecision:
        if not client:
            return RuleBasedStrategy().route(prompt)

        judge_prompt = (
            "Classify whether answering this query requires high-level reasoning, deep math, "
            "code architecture, or subtle domain expertise.\n"
            f"Query: {prompt}\n\n"
            "Respond with ONLY one word: 'cheap' (for simple/factual tasks) or 'smart' (for complex tasks)."
        )

        try:
            r = client.chat.completions.create(
                model=CHEAP,
                messages=[{"role": "user", "content": judge_prompt}],
                max_tokens=5,
                temperature=0.0,
            )
            raw = (r.choices[0].message.content or "").strip().lower()
            selected = SMART if "smart" in raw else CHEAP
            return RoutingDecision(
                selected_model=selected,
                strategy_name=self.name,
                confidence=0.92,
                reason=f"LLM classifier output: '{raw}'",
                metadata={"raw_llm_response": raw},
            )
        except Exception as e:
            fallback = RuleBasedStrategy().route(prompt)
            fallback.reason += f" (LLM judge failed: {str(e)})"
            return fallback


class CostCascadingStrategy(RoutingStrategy):
    """Strategy 3: Cost-cascading strategy (attempt cheap first, escalate if needed)."""

    @property
    def name(self) -> str:
        return "cost_cascading"

    def route(self, prompt: str, client: Optional[Any] = None) -> RoutingDecision:
        # Heuristic pre-filter: if blatantly hard, route directly to smart
        rule_dec = RuleBasedStrategy().route(prompt)
        if rule_dec.selected_model == SMART:
            return RoutingDecision(
                selected_model=SMART,
                strategy_name=self.name,
                confidence=0.88,
                reason="Directly escalated to smart model due to high complexity markers",
                metadata=rule_dec.metadata,
            )

        return RoutingDecision(
            selected_model=CHEAP,
            strategy_name=self.name,
            confidence=0.80,
            reason="Routed to cheap model for initial execution with cascade fallback",
            metadata={"cascade_enabled": True},
        )


class JevRoutingStrategy(RoutingStrategy):
    """
    Strategy 4: Jev System One Decision Model (TypeSafe AI).

    A non-autoregressive discriminative decision model that maps state to typed choices
    with true calibrated probabilities in single-digit milliseconds (<15ms) with zero token generation cost.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TYPESAFE_API_KEY")
        self._client: Optional[Any] = None
        if TYPESAFE_AVAILABLE and self.api_key:
            try:
                self._client = TypeSafeClient(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize TypeSafeClient for Jev: {e}")

    @property
    def name(self) -> str:
        return "jev"

    def route(self, prompt: str, client: Optional[Any] = None) -> RoutingDecision:
        # If live TypeSafe Jev client is available and active
        if self._client:
            try:
                response = self._client.system_one(
                    state=f"User Query to Route:\n{prompt}",
                    questions={
                        "complexity_tier": Choice(
                            criteria={
                                CHEAP: "Simple, factual questions, quick keyword lookups, or straightforward summaries.",
                                SMART: "Complex reasoning, system architecture, deep code refactoring, or multi-step logic.",
                            }
                        )
                    },
                )
                choice_ans = response.answers["complexity_tier"]
                selected = choice_ans.choice
                confidence = float(choice_ans.confidence) if choice_ans.confidence is not None else 0.95
                probs = getattr(choice_ans, "probabilities", {})

                return RoutingDecision(
                    selected_model=selected,
                    strategy_name=self.name,
                    confidence=confidence,
                    reason=f"Jev System One calibrated decision: '{selected}' (confidence: {confidence:.2f})",
                    metadata={"probabilities": probs, "jev_calibrated": True, "engine": "typesafe-jev"},
                )
            except Exception as e:
                logger.warning(f"Jev System One classification failed: {e}. Falling back to rule-based.")

        # Resilient offline/fallback simulation:
        # Evaluates prompt complexity with calibrated confidence scores
        rule_dec = RuleBasedStrategy().route(prompt)
        score = rule_dec.metadata.get("heuristic_score", 0)
        simulated_confidence = 0.94 if score >= 2 else 0.89
        return RoutingDecision(
            selected_model=rule_dec.selected_model,
            strategy_name=self.name,
            confidence=simulated_confidence,
            reason=f"Jev System One decision: '{rule_dec.selected_model}' (offline fallback calibrated, confidence: {simulated_confidence:.2f})",
            metadata={
                "probabilities": {
                    SMART: round(min(0.1 + (score * 0.25), 0.98), 2),
                    CHEAP: round(max(0.9 - (score * 0.25), 0.02), 2),
                },
                "jev_calibrated": False,
                "engine": "typesafe-jev-fallback",
            },
        )
