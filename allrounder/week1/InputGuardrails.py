"""
Input Guardrails Module (allrounder/week1)

Enterprise-grade defensive shields for LLM applications:
1. Prompt Injection & Jailbreak Detection (heuristic & pattern matching)
2. PII (Personally Identifiable Information) Shield (Detection, Masking, or Blocking)
3. Payload Overflow & Token Sanity (character & length limits)
4. Harmful & Toxic Intent Filtering
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class PIIAction(str, Enum):
    MASK = "MASK"       # Redact PII (e.g. [REDACTED_EMAIL]) and allow sanitized prompt
    BLOCK = "BLOCK"     # Reject prompt immediately if any PII is detected


class ViolationType(str, Enum):
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


class InputGuardrails:
    # 1. Prompt Injection & Jailbreak patterns
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

    # 2. PII Patterns
    PII_REGEX = {
        "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
        "PHONE": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "API_KEY": re.compile(r"\b(sk-[a-zA-Z0-9_-]{20,}|ghp_[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16})\b"),
        "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    }

    # 3. Harmful / Toxic Intent Patterns
    TOXIC_PATTERNS = [
        re.compile(r"(?i)\bhow\s+to\s+(make|synthesize|build)\s+(a\s+)?(bomb|explosive|weapon|poison)\b"),
        re.compile(r"(?i)\bwrite\s+(a\s+)?(keylogger|ransomware|trojan|ddos\s+exploit)\b"),
        re.compile(r"(?i)\bexploit\s+cve-\d{4}-\d+\b"),
    ]

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

    def inspect(self, prompt: str) -> GuardrailResult:
        """
        Runs comprehensive input verification.
        Returns a structured GuardrailResult.
        """
        if not prompt or not prompt.strip():
            return GuardrailResult(
                passed=False,
                action="BLOCKED",
                original_prompt=prompt,
                sanitized_prompt=prompt,
                violations=["EMPTY_PROMPT"],
                risk_score=1.0,
                blocked_reason="Prompt cannot be empty.",
            )

        violations: List[str] = []
        pii_found: Dict[str, List[str]] = {}
        risk_score = 0.0
        sanitized = prompt

        # -------------------------------------------------------------
        # Guard 1: Payload Length Check
        # -------------------------------------------------------------
        if len(prompt) > self.max_characters:
            violations.append(ViolationType.LENGTH_OVERFLOW.value)
            return GuardrailResult(
                passed=False,
                action="BLOCKED",
                original_prompt=prompt,
                sanitized_prompt=prompt[: self.max_characters],
                violations=violations,
                risk_score=1.0,
                blocked_reason=f"Prompt exceeds limit of {self.max_characters} characters.",
            )

        # -------------------------------------------------------------
        # Guard 2: Toxicity / Dangerous Intent
        # -------------------------------------------------------------
        if self.enable_toxicity_guard:
            for pattern in self.TOXIC_PATTERNS:
                if pattern.search(prompt):
                    violations.append(ViolationType.TOXICITY.value)
                    return GuardrailResult(
                        passed=False,
                        action="BLOCKED",
                        original_prompt=prompt,
                        sanitized_prompt="",
                        violations=violations,
                        risk_score=1.0,
                        blocked_reason="Harmful or dangerous content request detected.",
                    )

        # -------------------------------------------------------------
        # Guard 3: Prompt Injection / Jailbreak Detection
        # -------------------------------------------------------------
        if self.enable_injection_guard:
            injection_hits = 0
            for pattern in self.INJECTION_PATTERNS:
                if pattern.search(prompt):
                    injection_hits += 1

            if injection_hits > 0:
                risk_score += min(1.0, injection_hits * 0.5)
                violations.append(ViolationType.PROMPT_INJECTION.value)
                return GuardrailResult(
                    passed=False,
                    action="BLOCKED",
                    original_prompt=prompt,
                    sanitized_prompt="",
                    violations=violations,
                    risk_score=risk_score,
                    blocked_reason="Adversarial prompt injection or system prompt override attempt detected.",
                )

        # -------------------------------------------------------------
        # Guard 4: PII Detection & Shield
        # -------------------------------------------------------------
        if self.enable_pii_guard:
            for pii_type, regex in self.PII_REGEX.items():
                matches = regex.findall(prompt)
                if matches:
                    pii_found[pii_type] = matches
                    violations.append(f"{ViolationType.PII_DETECTED.value}:{pii_type}")
                    risk_score += 0.2

            if pii_found:
                if self.pii_action == PIIAction.BLOCK:
                    return GuardrailResult(
                        passed=False,
                        action="BLOCKED",
                        original_prompt=prompt,
                        sanitized_prompt="",
                        violations=violations,
                        pii_entities=pii_found,
                        risk_score=min(1.0, risk_score),
                        blocked_reason=f"PII detected in prompt: {list(pii_found.keys())}.",
                    )
                else:
                    # MASK mode: safely redact PII entities
                    for pii_type, regex in self.PII_REGEX.items():
                        sanitized = regex.sub(f"[REDACTED_{pii_type}]", sanitized)

                    return GuardrailResult(
                        passed=True,
                        action="SANITIZED",
                        original_prompt=prompt,
                        sanitized_prompt=sanitized,
                        violations=violations,
                        pii_entities=pii_found,
                        risk_score=min(1.0, risk_score),
                    )

        # All checks passed cleanly
        return GuardrailResult(
            passed=True,
            action="ALLOWED",
            original_prompt=prompt,
            sanitized_prompt=prompt,
            risk_score=0.0,
        )
