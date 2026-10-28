"""
guardrails/input_guardrails.py - Inbound Guardrail Chain of Responsibility.

Enterprise-grade defensive shields for LLM applications:
1. Prompt Injection & Jailbreak Filter (heuristic & pattern matching)
2. PII (Personally Identifiable Information) Shield Filter (Masking or Blocking)
3. Payload Overflow & Token Sanity Filter (character & length limits)
4. Harmful & Toxic Intent Filtering
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .base import BaseGuardrailFilter, GuardrailAction, GuardrailContext, GuardrailPipeline


class PIIAction(str, Enum):
    MASK = "MASK"       # Redact PII (e.g. [REDACTED_EMAIL]) and allow sanitized prompt
    BLOCK = "BLOCK"     # Reject prompt immediately if any PII is detected


class ViolationType(str, Enum):
    EMPTY_PROMPT = "EMPTY_PROMPT"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    PII_DETECTED = "PII_DETECTED"
    LENGTH_OVERFLOW = "LENGTH_OVERFLOW"
    TOXICITY = "TOXICITY"


@dataclass
class GuardrailResult:
    passed: bool
    action: str  # "ALLOWED", "SANITIZED", or "BLOCKED"
    original_prompt: str
    sanitized_prompt: str
    violations: List[str] = field(default_factory=list)
    pii_entities: Dict[str, List[str]] = field(default_factory=dict)
    risk_score: float = 0.0
    blocked_reason: Optional[str] = None


# -----------------------------------------------------------------------------
# Concrete Filter 1: Payload Length & Sanity Filter
# -----------------------------------------------------------------------------
class PayloadLengthFilter(BaseGuardrailFilter):
    def __init__(self, max_characters: int = 10000, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.max_characters = max_characters

    def process(self, context: GuardrailContext) -> GuardrailContext:
        if not context.current_text or not context.current_text.strip():
            context.block(
                violation=ViolationType.EMPTY_PROMPT.value,
                reason="Prompt cannot be empty.",
                risk_score=1.0,
            )
            return context

        if len(context.current_text) > self.max_characters:
            context.block(
                violation=ViolationType.LENGTH_OVERFLOW.value,
                reason=f"Prompt exceeds max allowed limit of {self.max_characters} characters ({len(context.current_text)} received).",
                risk_score=0.7,
            )
        return context


# -----------------------------------------------------------------------------
# Concrete Filter 2: Prompt Injection & Jailbreak Filter
# -----------------------------------------------------------------------------
class PromptInjectionFilter(BaseGuardrailFilter):
    INJECTION_PATTERNS = [
        re.compile(r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)\b"),
        re.compile(r"(?i)\bdisregard\s+(all\s+)?(safety|system|operational)\s+(rules|guidelines)\b"),
        re.compile(r"(?i)\byou\s+are\s+now\s+(in\s+)?(developer\s+mode|dan|unrestricted|god\s+mode)\b"),
        re.compile(r"(?i)\breveal\s+(your\s+)?(system\s+prompt|secret\s+instructions|api\s+keys?)\b"),
        re.compile(r"(?i)\bprint\s+(your\s+)?(initial|hidden|system)\s+instructions\b"),
        re.compile(r"(?i)\bdo\s+anything\s+now\b"),
        re.compile(r"(?i)<\s*(system|instruction|admin)\s*>"),
        re.compile(r"(?i)\bpretend\s+you\s+have\s+no\s+(morals|filters|rules|constraints)\b"),
    ]

    def process(self, context: GuardrailContext) -> GuardrailContext:
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(context.current_text):
                context.block(
                    violation=ViolationType.PROMPT_INJECTION.value,
                    reason="Prompt contains potential prompt injection or jailbreak pattern.",
                    risk_score=0.95,
                )
                break
        return context


# -----------------------------------------------------------------------------
# Concrete Filter 3: Inbound PII Masking & Redaction Filter
# -----------------------------------------------------------------------------
class PIIMaskingFilter(BaseGuardrailFilter):
    PII_REGEX = {
        "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
        "PHONE": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "API_KEY": re.compile(r"\b(sk-[a-zA-Z0-9_-]{20,}|ghp_[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16})\b"),
        "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    }

    def __init__(self, pii_action: PIIAction = PIIAction.MASK, enabled: bool = True):
        super().__init__(enabled=enabled)
        self.pii_action = pii_action

    def process(self, context: GuardrailContext) -> GuardrailContext:
        detected_pii: Dict[str, List[str]] = {}
        sanitized = context.current_text

        for entity_type, pattern in self.PII_REGEX.items():
            matches = pattern.findall(sanitized)
            if matches:
                detected_pii[entity_type] = matches
                if self.pii_action == PIIAction.BLOCK:
                    context.block(
                        violation=ViolationType.PII_DETECTED.value,
                        reason=f"Inbound PII detected ({entity_type}). Inbound PII blocking is active.",
                        risk_score=0.85,
                    )
                    context.metadata["pii_entities"] = detected_pii
                    return context
                else:
                    # Mask PII with safe placeholder tokens
                    sanitized = pattern.sub(f"[REDACTED_{entity_type}]", sanitized)

        if detected_pii:
            context.sanitize(sanitized, violation=ViolationType.PII_DETECTED.value)
            context.metadata["pii_entities"] = detected_pii
            context.risk_score = max(context.risk_score, 0.4)

        return context


# -----------------------------------------------------------------------------
# Concrete Filter 4: Harmful & Toxic Intent Filter
# -----------------------------------------------------------------------------
class ToxicityFilter(BaseGuardrailFilter):
    TOXIC_PATTERNS = [
        re.compile(r"(?i)\bhow\s+to\s+(?:make|synthesize|build)\s+(?:a|an)?\s*(?:homemade\s+)?(?:bomb|explosive|weapon|poison)\b"),
        re.compile(r"(?i)\bwrite\s+(?:a|an)?\s*(?:keylogger|ransomware|trojan|ddos\s+exploit)\b"),
        re.compile(r"(?i)\bexploit\s+cve-\d{4}-\d+\b"),
    ]

    def process(self, context: GuardrailContext) -> GuardrailContext:
        for pattern in self.TOXIC_PATTERNS:
            if pattern.search(context.current_text):
                context.block(
                    violation=ViolationType.TOXICITY.value,
                    reason="Prompt contains malicious intent, weapons, or malware creation requests.",
                    risk_score=1.0,
                )
                break
        return context


# -----------------------------------------------------------------------------
# Facade: InputGuardrails
# -----------------------------------------------------------------------------
class InputGuardrails:
    """Enterprise Inbound Guardrails Engine using Chain of Responsibility."""

    def __init__(
        self,
        pii_action: PIIAction = PIIAction.MASK,
        max_characters: int = 10000,
        enable_injection_guard: bool = True,
        enable_pii_guard: bool = True,
        enable_toxicity_guard: bool = True,
    ):
        self.pii_action = pii_action
        self.max_characters = max_characters
        self.enable_injection_guard = enable_injection_guard
        self.enable_pii_guard = enable_pii_guard
        self.enable_toxicity_guard = enable_toxicity_guard

        # Assemble the Chain of Responsibility pipeline
        self.pipeline = GuardrailPipeline([
            PayloadLengthFilter(max_characters=self.max_characters),
            PromptInjectionFilter(enabled=self.enable_injection_guard),
            PIIMaskingFilter(pii_action=self.pii_action, enabled=self.enable_pii_guard),
            ToxicityFilter(enabled=self.enable_toxicity_guard),
        ])

    def inspect(self, prompt: str) -> GuardrailResult:
        """Runs the prompt through the Chain of Responsibility pipeline."""
        ctx = self.pipeline.execute(prompt)
        return GuardrailResult(
            passed=ctx.passed,
            action=ctx.action.value,
            original_prompt=ctx.original_text,
            sanitized_prompt=ctx.current_text,
            violations=ctx.violations,
            pii_entities=ctx.metadata.get("pii_entities", {}),
            risk_score=ctx.risk_score,
            blocked_reason=ctx.blocked_reason,
        )


# Default singleton instance
input_guardrails = InputGuardrails()
