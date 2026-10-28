"""
routing/router.py - SmartRouter Context Class for the Strategy Pattern.

Manages strategy execution, client lifecycle, and query execution.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

from .base import CHEAP, SMART, RoutingDecision, RoutingStrategy
from .strategies import CostCascadingStrategy, LLMJudgeStrategy, RuleBasedStrategy

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv()


class SmartRouter:
    """Context class for Routing Strategy pattern."""

    def __init__(
        self,
        strategy: Optional[RoutingStrategy] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.strategy = strategy or RuleBasedStrategy()

        resolved_base_url = (
            base_url
            or os.getenv("NGINX_PROXY_URL")
            or os.getenv("LITELLM_PROXY_URL")
            or os.getenv("AI_GATEWAY_URL")
            or "http://localhost:8080/v1"
        )
        resolved_api_key = (
            api_key
            or os.getenv("LITELLM_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or "sk-dummy"
        )

        self.client = OpenAI(base_url=resolved_base_url, api_key=resolved_api_key)

        # Strategy Registry
        self.available_strategies: Dict[str, RoutingStrategy] = {
            "rules": RuleBasedStrategy(),
            "rule_based": RuleBasedStrategy(),
            "llm": LLMJudgeStrategy(),
            "llm_judge": LLMJudgeStrategy(),
            "cascade": CostCascadingStrategy(),
            "cost_cascading": CostCascadingStrategy(),
        }

    def set_strategy(self, strategy: RoutingStrategy) -> None:
        """Dynamically swap routing strategy at runtime."""
        self.strategy = strategy

    def set_strategy_by_name(self, strategy_name: str) -> None:
        """Select strategy by string identifier."""
        name_clean = strategy_name.lower().strip()
        if name_clean in self.available_strategies:
            self.strategy = self.available_strategies[name_clean]
        else:
            raise ValueError(f"Unknown routing strategy: {strategy_name}")

    def route(self, prompt: str, strategy_name: Optional[str] = None) -> RoutingDecision:
        """Executes the chosen or configured routing strategy."""
        strat = self.available_strategies.get(strategy_name.lower().strip()) if strategy_name else self.strategy
        if not strat:
            strat = self.strategy
        return strat.route(prompt, client=self.client)

    # --- Convenience and Backward Compatibility Helpers ---
    def classify_by_rules(self, prompt: str) -> str:
        return RuleBasedStrategy().route(prompt).selected_model

    def classify_by_llm(self, prompt: str) -> str:
        return LLMJudgeStrategy().route(prompt, client=self.client).selected_model

    def ask_with_cascade(self, prompt: str) -> Tuple[str, str]:
        """
        Attempts cheap model first; cascades to smart model if cheap model expresses uncertainty.
        """
        prompt_with_instructions = (
            prompt
            + "\n\n(If you are unsure, have low confidence, or believe this task requires advanced analysis, "
            "include the exact token [UNCERTAIN] in your answer.)"
        )
        try:
            r = self.client.chat.completions.create(
                model=CHEAP,
                messages=[{"role": "user", "content": prompt_with_instructions}],
            )
            ans = r.choices[0].message.content or ""
            if "[UNCERTAIN]" in ans:
                r2 = self.client.chat.completions.create(
                    model=SMART,
                    messages=[{"role": "user", "content": prompt}],
                )
                return r2.choices[0].message.content or "", SMART
            return ans, CHEAP
        except Exception:
            # Fallback to smart model if cheap fails
            r2 = self.client.chat.completions.create(
                model=SMART,
                messages=[{"role": "user", "content": prompt}],
            )
            return r2.choices[0].message.content or "", SMART


# Default instance
smart_router = SmartRouter()
